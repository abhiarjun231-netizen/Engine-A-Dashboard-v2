"""
engine_c.py
Parthsarthi Capital - Phase 3, Item 3.8
ENGINE C - THE ORCHESTRATOR (wires Modules 1-7 into one engine).

The integration step for the Value Warriors engine. The seven
Engine C modules each do one job; this file runs them as a single
daily pipeline.

One daily cycle of Engine C:
  1. GUARD     - Risk Layer 4: is the upload fresh and well-formed?
  2. SCREEN    - load the C2 value screener
  3. HELD POSITIONS - for each open position, run:
        thesis-break check (Module 2B)
        PE-expansion booking check (Module 2A)
        churn check if it left the screen (Module 7)
        quarterly re-underwrite if due (Module 6)
        lifecycle stage (Module 2)
  4. CANDIDATES - for each screen stock not held, run:
        value conviction scoring (Module 1)
        ranking & rotation if portfolio is full (Module 5)
  5. REPORT    - a clear summary of every decision with reason string.

This orchestrator produces decisions; it does not place trades.
"""

import os
from datetime import datetime

from data_guard import guard
from engine_c_conviction import load_screener, score_stock, sector_exposure
from engine_c_lifecycle import stage_for_holding
from engine_c_booking import check_booking
from engine_c_thesis import check_thesis
from engine_c_ranking import evaluate_rotation, MAX_POSITIONS
from engine_c_reunderwrite import reunderwrite
from engine_c_churn import handle_churn


class EngineC:
    """The Value Warriors engine - orchestrates Modules 1-7."""

    def __init__(self, engine_a_score=55):
        self.engine_a_score = engine_a_score
        self.decisions = []
        self.report_lines = []

    def _log(self, line):
        self.report_lines.append(line)

    def run_cycle(self, screener_csv, held_positions=None,
                  bd_tickers=None, file_date=None):
        """
        Run one daily Engine C cycle.

        held_positions - list of dicts:
          {ticker, entry_price, current_price, entry_pe, current_pe,
           piotroski, roe, debt_equity, sector, months_held,
           days_since_review, tranches_booked, conviction,
           on_screen(bool)}
        bd_tickers - set of tickers also in B/D screeners
        """
        held_positions = held_positions or []
        bd_tickers = bd_tickers or set()

        self._log('=' * 64)
        self._log(f'ENGINE C - VALUE WARRIORS  |  cycle {datetime.now():%Y-%m-%d %H:%M}')
        self._log(f'Engine A score {self.engine_a_score}')
        self._log('=' * 64)

        # ---- Step 1: data guard ----
        g = guard(screener_csv, file_date=file_date)
        self._log(f'\n[1] DATA GUARD: {g.banner()}')
        if not g.passed:
            self._log('    Cycle halted - the system does not act on bad data.')
            return self._finish()

        # ---- Step 2: load screen ----
        rows = load_screener(screener_csv)
        screen_tickers = set(rows.keys())
        held_tickers = {p['ticker'] for p in held_positions}
        self._log(f'[2] SCREEN: {len(rows)} stocks on the C2 value screen')

        # ---- Step 3: held positions ----
        self._log(f'\n[3] HELD POSITIONS ({len(held_positions)}):')
        if not held_positions:
            self._log('    none')
        for p in held_positions:
            tk = p['ticker']
            on_screen = p.get('on_screen', tk in screen_tickers)
            booked = set(p.get('tranches_booked', []))

            # 3a. thesis-break check (Module 2B) - Path B
            th = check_thesis(tk, p['entry_price'], p['current_price'],
                              p.get('piotroski'), p.get('roe'),
                              p.get('debt_equity'), self.engine_a_score,
                              p.get('months_held', 0),
                              booking_triggered=bool(booked))
            if th.verdict == 'EXIT':
                self.decisions.append(th)
                self._log(f'  {tk:13} EXIT (Module 2B - thesis break)  {th.rule}')
                continue

            # 3b. PE-expansion booking (Module 2A) - Path A
            bk = check_booking(tk, p.get('entry_pe'), p.get('current_pe'),
                               tranches_booked=booked)
            if bk.verdict == 'BOOK-THIRD':
                self.decisions.append(bk)
                fully = any(k == 'Position after' and 'fully' in v
                            for k, v in bk.facts)
                tag = 'fully exited' if fully else 'tranche booked'
                self._log(f'  {tk:13} BOOK-THIRD (Module 2A - {tag})')
                continue

            # 3c. churn check (Module 7) - only if it left the screen
            if not on_screen:
                ch = handle_churn(tk, p.get('current_pe'), p['entry_price'],
                                  p['current_price'])
                self.decisions.append(ch)
                self._log(f'  {tk:13} {ch.verdict} (Module 7 - left screen)')
                continue

            # 3d. quarterly re-underwrite if due (Module 6)
            days_review = p.get('days_since_review', 0)
            if days_review >= 90:
                fresh = score_stock(tk, rows[tk], bd_tickers,
                                    sector_exposure(held_positions),
                                    fresh_tickers=set())
                ru = reunderwrite(tk, days_review, fresh.total_score(),
                                  p.get('conviction'))
                self.decisions.append(ru)
                if ru.verdict == 'RE-UNDERWRITE-REVIEW':
                    self._log(f'  {tk:13} RE-UNDERWRITE-REVIEW (Module 6 - '
                              f'flagged, would not buy today)')
                    continue

            # 3e. still healthy - lifecycle stage
            stage, _ = stage_for_holding(p['entry_price'], p['current_price'],
                                         booking_started=bool(booked))
            gain = ((p['current_price'] - p['entry_price'])
                    / p['entry_price'] * 100)
            self.decisions.append(th)   # the HOLD decision from Module 2B
            self._log(f'  {tk:13} HOLD - stage {stage}  (gain {gain:+.1f}%)')

        # ---- Step 4: candidates ----
        sector_pct = sector_exposure(held_positions)
        candidates = [tk for tk in screen_tickers if tk not in held_tickers]
        self._log(f'\n[4] CANDIDATES ({len(candidates)} not held):')

        deploys = []
        for tk in candidates:
            d = score_stock(tk, rows[tk], bd_tickers, sector_pct,
                            fresh_tickers={tk})
            self.decisions.append(d)
            if d.verdict == 'DEPLOY':
                deploys.append((tk, d.total_score()))

        if deploys:
            self._log(f'    {len(deploys)} DEPLOY candidate(s):')
            holdings_for_rank = [
                {'ticker': p['ticker'], 'conviction': p.get('conviction', 7),
                 'stage': 'HELD'} for p in held_positions]
            for tk, sc in sorted(deploys, key=lambda x: -x[1]):
                rot = evaluate_rotation(tk, sc, holdings_for_rank)
                self.decisions.append(rot)
                self._log(f'      {tk:13} conviction {sc}/10 -> {rot.verdict}')
        else:
            self._log('    no DEPLOY candidates this cycle')

        # ---- Step 5: summary ----
        verdicts = {}
        for d in self.decisions:
            verdicts[d.verdict] = verdicts.get(d.verdict, 0) + 1
        self._log('\n[5] CYCLE SUMMARY:')
        for v, n in sorted(verdicts.items()):
            self._log(f'    {v:22} {n}')

        return self._finish()

    def _finish(self):
        self._log('=' * 64)
        return '\n'.join(self.report_lines)


# ---- self-test / live run ----
if __name__ == '__main__':
    print('Running Engine C end-to-end on the live C2 screener...\n')

    csv_path = '/mnt/user-data/uploads/C2_Value_May_16__2026.csv'
    if not os.path.exists(csv_path):
        csv_path = 'C2_Value_May_16__2026.csv'

    # Simulate held positions to exercise Modules 2A/2B/6/7.
    held = [
        # a healthy holding, no booking yet
        {'ticker': 'PTC', 'entry_price': 100, 'current_price': 108,
         'entry_pe': 7, 'current_pe': 8, 'piotroski': 8, 'roe': 18,
         'debt_equity': 0.4, 'sector': 'Utilities', 'months_held': 4,
         'days_since_review': 30, 'tranches_booked': [], 'conviction': 7,
         'on_screen': True},
        # a holding that has re-rated - PE expanded enough to book
        {'ticker': 'SHARDACROP', 'entry_price': 100, 'current_price': 140,
         'entry_pe': 10, 'current_pe': 13.5, 'piotroski': 7, 'roe': 21,
         'debt_equity': 0.3, 'sector': 'Chemicals & Petrochemicals',
         'months_held': 8, 'days_since_review': 40, 'tranches_booked': [],
         'conviction': 7, 'on_screen': True},
        # a holding that left the screen
        {'ticker': 'OLDVALUE', 'entry_price': 100, 'current_price': 132,
         'entry_pe': 12, 'current_pe': 27, 'piotroski': 7, 'roe': 19,
         'debt_equity': 0.5, 'sector': 'Auto', 'months_held': 10,
         'days_since_review': 50, 'tranches_booked': [], 'conviction': 7,
         'on_screen': False},
    ]

    eng = EngineC(engine_a_score=55)
    report = eng.run_cycle(csv_path, held_positions=held,
                           file_date=datetime.now().isoformat())
    print(report)
    print(f'\nTotal decisions generated this cycle: {len(eng.decisions)}')
    print('Every decision carries a full auditable reason string.')
