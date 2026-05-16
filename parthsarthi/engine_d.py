"""
engine_d.py
Parthsarthi Capital - Phase 4, Item 4.6
ENGINE D - THE ORCHESTRATOR (wires Modules 1-5 into one engine).

The integration step for the Compounders engine, and the last
engine of the system. The five Engine D modules each do one job;
this file runs them as a single daily pipeline.

One daily cycle of Engine D:
  1. GUARD      - Risk Layer 4: is the upload fresh and well-formed?
  2. SCREEN     - load the D1 compounder screener
  3. INCUBATING - for each position still in its 90-day incubation:
        assess incubation (Module 2): hold / promote / fail
  4. HELD       - for each fully-held compounder:
        promotion tier (Module 3)
        thesis-break check, tier-aware (Module 4)
        churn check if it left the screen (Module 5)
  5. CANDIDATES - for each screen stock not held/incubating:
        compounder conviction scoring (Module 1)
        a 7+ score begins incubation (Module 2)
  6. REPORT     - a clear summary of every decision with reason string.

This orchestrator produces decisions; it does not place trades.
"""

import os
from datetime import datetime

from data_guard import guard
from engine_d_conviction import load_screener, score_stock, sector_exposure
from engine_d_incubation import begin_incubation, assess_incubation
from engine_d_tiers import tier_for_months
from engine_d_thesis import check_thesis
from engine_d_churn import handle_churn


class EngineD:
    """The Compounders engine - orchestrates Modules 1-5."""

    def __init__(self, engine_a_score=55):
        self.engine_a_score = engine_a_score
        self.decisions = []
        self.report_lines = []

    def _log(self, line):
        self.report_lines.append(line)

    def run_cycle(self, screener_csv, held_positions=None,
                  incubating_positions=None, bc_tickers=None,
                  file_date=None):
        """
        Run one daily Engine D cycle.

        held_positions - list of fully-held compounders:
          {ticker, entry_price, current_price, growth_3y, piotroski,
           roe, debt_equity, peg, sector, months_held,
           soft_breach_streak, on_screen(bool)}
        incubating_positions - list of positions in incubation:
          {ticker, days_incubating, current_conviction, target_value,
           on_screen(bool)}
        bc_tickers - set of tickers also in B/C screeners
        """
        held_positions = held_positions or []
        incubating_positions = incubating_positions or []
        bc_tickers = bc_tickers or set()

        self._log('=' * 64)
        self._log(f'ENGINE D - COMPOUNDERS  |  cycle {datetime.now():%Y-%m-%d %H:%M}')
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
        incub_tickers = {p['ticker'] for p in incubating_positions}
        self._log(f'[2] SCREEN: {len(rows)} stocks on the D1 compounder screen')

        # ---- Step 3: incubating positions ----
        self._log(f'\n[3] INCUBATING POSITIONS ({len(incubating_positions)}):')
        if not incubating_positions:
            self._log('    none')
        for p in incubating_positions:
            tk = p['ticker']
            on_screen = p.get('on_screen', tk in screen_tickers)
            d = assess_incubation(tk, p['days_incubating'],
                                  p['current_conviction'], on_screen,
                                  p['target_value'])
            self.decisions.append(d)
            self._log(f'  {tk:13} {d.verdict}  (day {p["days_incubating"]}/90)')

        # ---- Step 4: held compounders ----
        self._log(f'\n[4] HELD COMPOUNDERS ({len(held_positions)}):')
        if not held_positions:
            self._log('    none')
        for p in held_positions:
            tk = p['ticker']
            on_screen = p.get('on_screen', tk in screen_tickers)
            months = p.get('months_held', 0)
            tier = tier_for_months(months)

            # 4a. thesis-break check, tier-aware (Module 4)
            th = check_thesis(tk, p['entry_price'], p['current_price'],
                              p.get('growth_3y'), p.get('piotroski'),
                              p.get('roe'), p.get('debt_equity'),
                              p.get('peg'), self.engine_a_score,
                              months_held=months,
                              soft_breach_streak=p.get('soft_breach_streak'))
            if th.verdict == 'EXIT':
                self.decisions.append(th)
                self._log(f'  {tk:13} EXIT (Module 4 - thesis break)  '
                          f'[{tier}]  {th.rule}')
                continue

            # 4b. churn check (Module 5) - only if it left the screen
            if not on_screen:
                ch = handle_churn(tk, p.get('peg'), p['entry_price'],
                                  p['current_price'])
                self.decisions.append(ch)
                self._log(f'  {tk:13} {ch.verdict} (Module 5 - left screen)  '
                          f'[{tier}]')
                continue

            # 4c. healthy hold
            self.decisions.append(th)   # the HOLD decision from Module 4
            gain = ((p['current_price'] - p['entry_price'])
                    / p['entry_price'] * 100)
            self._log(f'  {tk:13} HOLD  [{tier}, {months}mo]  '
                      f'(gain {gain:+.1f}%)')

        # ---- Step 5: candidates ----
        sector_pct = sector_exposure(held_positions)
        candidates = [tk for tk in screen_tickers
                      if tk not in held_tickers and tk not in incub_tickers]
        self._log(f'\n[5] CANDIDATES ({len(candidates)} not held/incubating):')

        incubate_now = []
        for tk in candidates:
            d = score_stock(tk, rows[tk], bc_tickers, sector_pct,
                            fresh_tickers={tk})
            self.decisions.append(d)
            if d.verdict == 'INCUBATE':
                incubate_now.append((tk, d.total_score()))

        if incubate_now:
            self._log(f'    {len(incubate_now)} candidate(s) cleared to '
                      f'begin incubation:')
            for tk, sc in sorted(incubate_now, key=lambda x: -x[1]):
                # begin incubation at 50% of a notional target
                bi = begin_incubation(tk, sc, target_value=100000)
                self.decisions.append(bi)
                self._log(f'      {tk:13} conviction {sc}/10 -> '
                          f'INCUBATE-START (deploy 50%)')
        else:
            self._log('    no candidates cleared for incubation this cycle')

        # ---- Step 6: summary ----
        verdicts = {}
        for d in self.decisions:
            verdicts[d.verdict] = verdicts.get(d.verdict, 0) + 1
        self._log('\n[6] CYCLE SUMMARY:')
        for v, n in sorted(verdicts.items()):
            self._log(f'    {v:22} {n}')

        return self._finish()

    def _finish(self):
        self._log('=' * 64)
        return '\n'.join(self.report_lines)


# ---- self-test / live run ----
if __name__ == '__main__':
    print('Running Engine D end-to-end on the live D1 screener...\n')

    csv_path = '/mnt/user-data/uploads/D1_Compound_May_16__2026.csv'
    if not os.path.exists(csv_path):
        csv_path = 'D1_Compound_May_16__2026.csv'

    # Simulate an incubating position and held compounders.
    incubating = [
        {'ticker': 'HINDZINC', 'days_incubating': 45, 'current_conviction': 7,
         'target_value': 100000, 'on_screen': True},
    ]
    held = [
        # a healthy SEEDLING compounder
        {'ticker': 'FORCEMOT', 'entry_price': 100, 'current_price': 130,
         'growth_3y': 40, 'piotroski': 8, 'roe': 28, 'debt_equity': 0.4,
         'peg': 0.6, 'sector': 'Automobiles & Auto Components',
         'months_held': 8, 'on_screen': True},
        # an IMMORTAL compounder that re-rated and left the screen
        {'ticker': 'OLDCOMPOUNDER', 'entry_price': 100, 'current_price': 240,
         'growth_3y': 30, 'piotroski': 8, 'roe': 30, 'debt_equity': 0.3,
         'peg': 2.0, 'sector': 'FMCG', 'months_held': 30,
         'on_screen': False},
    ]

    eng = EngineD(engine_a_score=55)
    report = eng.run_cycle(csv_path, held_positions=held,
                           incubating_positions=incubating,
                           file_date=datetime.now().isoformat())
    print(report)
    print(f'\nTotal decisions generated this cycle: {len(eng.decisions)}')
    print('Every decision carries a full auditable reason string.')
