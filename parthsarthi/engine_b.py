"""
engine_b.py
Parthsarthi Capital - Phase 2, Item 2.8
ENGINE B - THE ORCHESTRATOR (wires Modules 1-6 into one engine).

This is the integration step. The seven Engine B modules built in
Phase 2 each do one job; this file runs them as a single pipeline.

One daily cycle of Engine B:
  1. GUARD     - Risk Layer 4: is the upload fresh and well-formed?
  2. JOURNAL   - screen-diff vs the previous upload
  3. HELD POSITIONS - for each open position, run:
        exit triggers (Module 3)
        profit / trailing stop (Module 4)
        churn check if it left the screen (Module 5)
  4. CANDIDATES - for each screen stock not held, run:
        conviction scoring (Module 1)
        lifecycle stage (Module 2)
        re-entry check (Module 6) if previously exited
  5. REPORT    - a clear summary of every decision, each with its
                 reason string, all routed through the state model.

This orchestrator does not place trades. It produces decisions.
Trade execution stays a human step (paper-trading first).
"""

import os
from datetime import datetime

from data_guard import guard
from engine_b_conviction import load_screener, score_stock, sector_exposure
from engine_b_lifecycle import stage_for_candidate, stage_for_holding
from engine_b_exits import check_exit, engine_a_regime
from engine_b_profit import check_profit
from engine_b_churn import handle_churn
from engine_b_reentry import evaluate_reentry


class EngineB:
    """The Momentum Hunter engine - orchestrates Modules 1-6."""

    def __init__(self, engine_a_score=55):
        self.engine_a_score = engine_a_score
        self.regime = engine_a_regime(engine_a_score)
        self.decisions = []          # all decisions this cycle
        self.report_lines = []

    def _log(self, line):
        self.report_lines.append(line)

    def run_cycle(self, screener_csv, held_positions=None,
                  price_data=None, prev_scores=None,
                  cd_tickers=None, file_date=None):
        """
        Run one daily Engine B cycle.

        held_positions - list of dicts: {ticker, entry_price, current_price,
                         peak_price, durability, momentum, sector,
                         weeks_flat, on_screen(bool)}
        price_data     - optional {ticker: PriceData} for execution layer
        prev_scores    - optional {ticker: momentum_last_week}
        cd_tickers     - set of tickers also in C/D screeners
        """
        held_positions = held_positions or []
        prev_scores = prev_scores or {}
        cd_tickers = cd_tickers or set()

        self._log('=' * 64)
        self._log(f'ENGINE B - MOMENTUM HUNTER  |  cycle {datetime.now():%Y-%m-%d %H:%M}')
        self._log(f'Engine A score {self.engine_a_score} -> regime {self.regime}')
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
        self._log(f'[2] SCREEN: {len(rows)} stocks on the momentum screen')

        # regime gate
        if self.regime == 'EXIT-ALL':
            self._log('    REGIME EXIT-ALL: every position is to be closed.')
        elif self.regime == 'FREEZE':
            self._log('    REGIME FREEZE: holdings kept, no new entries permitted.')

        # ---- Step 3: held positions ----
        self._log(f'\n[3] HELD POSITIONS ({len(held_positions)}):')
        if not held_positions:
            self._log('    none')
        for p in held_positions:
            tk = p['ticker']
            on_screen = p.get('on_screen', tk in screen_tickers)

            # 3a. exit triggers (Module 3)
            ex = check_exit(tk, p.get('durability'), p.get('momentum'),
                            prev_scores.get(tk), p['current_price'],
                            p.get('peak_price', p['current_price']),
                            self.engine_a_score)
            if ex.verdict == 'EXIT':
                self.decisions.append(ex)
                self._log(f'  {tk:13} EXIT (Module 3)  {ex.rule}')
                continue

            # 3b. profit / trailing stop (Module 4)
            pf = check_profit(tk, p['entry_price'], p['current_price'],
                              p.get('peak_price', p['current_price']),
                              weeks_flat=p.get('weeks_flat', 0))
            if pf.verdict.startswith('EXIT'):
                self.decisions.append(pf)
                self._log(f'  {tk:13} {pf.verdict} (Module 4)  {pf.rule}')
                continue

            # 3c. churn check (Module 5) - only if it left the screen
            if not on_screen:
                ch = handle_churn(tk, p['entry_price'], p['current_price'])
                self.decisions.append(ch)
                self._log(f'  {tk:13} {ch.verdict} (Module 5 - left screen)')
                continue

            # 3d. still healthy - lifecycle stage
            stage, _ = stage_for_holding(p.get('durability'), p.get('momentum'))
            self.decisions.append(pf)   # the HOLD decision from Module 4
            self._log(f'  {tk:13} HOLD - stage {stage}  '
                      f'(gain {((p["current_price"]-p["entry_price"])/p["entry_price"]*100):+.1f}%)')

        # ---- Step 4: candidates ----
        sector_pct = sector_exposure(held_positions)
        candidates = [tk for tk in screen_tickers if tk not in held_tickers]
        self._log(f'\n[4] CANDIDATES ({len(candidates)} not held):')

        strikes = []
        for tk in candidates:
            d = score_stock(tk, rows[tk], cd_tickers, sector_pct,
                            fresh_tickers={tk})  # treated fresh in this demo
            self.decisions.append(d)
            if d.verdict == 'STRIKE':
                if self.regime in ('EXIT-ALL', 'FREEZE'):
                    self._log(f'  {tk:13} STRIKE {d.total_score()}/10 '
                              f'- BLOCKED by regime {self.regime}')
                else:
                    strikes.append((tk, d.total_score()))

        if strikes:
            self._log(f'    {len(strikes)} STRIKE candidate(s) cleared to buy:')
            for tk, sc in sorted(strikes, key=lambda x: -x[1]):
                self._log(f'      {tk:13} conviction {sc}/10')
        else:
            self._log('    no STRIKE candidates cleared this cycle')

        # ---- Step 5: summary ----
        verdicts = {}
        for d in self.decisions:
            verdicts[d.verdict] = verdicts.get(d.verdict, 0) + 1
        self._log('\n[5] CYCLE SUMMARY:')
        for v, n in sorted(verdicts.items()):
            self._log(f'    {v:20} {n}')

        return self._finish()

    def _finish(self):
        self._log('=' * 64)
        return '\n'.join(self.report_lines)


# ---- self-test / live run ----
if __name__ == '__main__':
    print('Running Engine B end-to-end on the live May 16 screener...\n')

    csv_path = '/mnt/user-data/uploads/Mom_1_May_16__2026.csv'
    if not os.path.exists(csv_path):
        csv_path = 'Mom_1_May_16__2026.csv'

    # Simulate two held positions to exercise Modules 3/4/5.
    held = [
        {'ticker': 'HINDCOPPER', 'entry_price': 300, 'current_price': 345,
         'peak_price': 360, 'durability': 95, 'momentum': 70,
         'sector': 'Metals & Mining', 'weeks_flat': 0, 'on_screen': True},
        {'ticker': 'OLDHOLDING', 'entry_price': 500, 'current_price': 470,
         'peak_price': 520, 'durability': 58, 'momentum': 55,
         'sector': 'Auto', 'weeks_flat': 0, 'on_screen': False},
    ]

    eng = EngineB(engine_a_score=55)
    report = eng.run_cycle(csv_path, held_positions=held,
                           file_date=datetime.now().isoformat())
    print(report)
    print(f'\nTotal decisions generated this cycle: {len(eng.decisions)}')
    print('Every decision carries a full auditable reason string.')
