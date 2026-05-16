"""
engine_c_conviction.py
Parthsarthi Capital - Phase 3, Item 3.1
ENGINE C - VALUE CONVICTION SCORING (6-signal value model).

The first piece of Engine C. It scores every stock on the C2 value
screener against six value-specific signals (max 10 points):

  1. Multi-Engine     +3   also qualifies in Engine B or D screener
  2. Deep Value       +2   PE TTM < 15
  3. Quality Wall     +2   Piotroski Score >= 8
  4. Sector Safe      +1   sector < 30% of current C portfolio
  5. Growth Intact    +1   Net Profit YoY Growth > 25%
  6. Fresh Qualifier  +1   first appearance / 30+ day re-appearance

Verdict bands:
  7 - 10  DEPLOY      buy at next session open
  4 - 6   HOLD-FIRE   stay in WATCH, re-score next upload
  1 - 3   PASS        stay in WATCH, low priority

Every score produces a full reason string via the reasoning engine.

This mirrors Engine B's conviction module in structure but uses
value signals - cheapness and quality, not momentum. The Multi-Engine
signal scores 0 until B and D screeners are wired (10-point scale
retained so the locked thresholds stay valid).
"""

import csv
from reasoning_engine import Decision


# ---- locked thresholds (Engine C framework) ----
DEEP_VALUE_PE     = 15.0     # PE below this -> Deep Value
QUALITY_PIOTROSKI = 8        # Piotroski >= this -> Quality Wall
GROWTH_YOY        = 25.0     # NP YoY growth above this -> Growth Intact
SECTOR_CAP_PCT    = 30.0
DEPLOY_MIN        = 7
HOLDFIRE_MIN      = 4


def _num(v):
    try:
        return float(str(v).replace(',', '').strip())
    except (ValueError, AttributeError, TypeError):
        return None


def load_screener(csv_path):
    """Load the C2 value screener CSV -> {ticker: row}."""
    rows = {}
    with open(csv_path, 'r', encoding='utf-8-sig') as f:
        for raw in csv.DictReader(f):
            row = {k.strip(): (v.strip() if isinstance(v, str) else v)
                   for k, v in raw.items()}
            tk = row.get('NSE Code') or row.get('Stock')
            if tk:
                rows[tk] = row
    return rows


def sector_exposure(held_positions):
    """{sector: pct} of current Engine C portfolio."""
    if not held_positions:
        return {}
    n = len(held_positions)
    counts = {}
    for p in held_positions:
        s = p.get('sector', 'Unknown')
        counts[s] = counts.get(s, 0) + 1
    return {s: c / n * 100.0 for s, c in counts.items()}


def score_stock(ticker, row, bd_tickers=None, sector_pct=None,
                fresh_tickers=None):
    """
    Score one stock on the 6-signal value model.
    Returns a Decision carrying the verdict and full reason string.

    bd_tickers - set of tickers also in Engine B or D screeners
    """
    bd_tickers = bd_tickers or set()
    sector_pct = sector_pct or {}
    fresh_tickers = fresh_tickers or set()

    pe = _num(row.get('PE TTM'))
    piotroski = _num(row.get('Piotroski Score'))
    yoy = _num(row.get('Net Profit Ann  YoY Growth %'))
    sector = row.get('Sector', 'Unknown')

    # ---- Signal 1: Multi-Engine (+3) ----
    if ticker in bd_tickers:
        s1 = (3, 'also qualifies in Engine B or D')
    else:
        s1 = (0, 'not in B or D screener')

    # ---- Signal 2: Deep Value (+2) ----
    pe_disp = f'{pe:.1f}' if pe is not None else 'n/a'
    if pe is not None and pe < DEEP_VALUE_PE:
        s2 = (2, f'PE {pe_disp} < {DEEP_VALUE_PE:.0f}')
    else:
        s2 = (0, f'PE {pe_disp}, needs <{DEEP_VALUE_PE:.0f}')

    # ---- Signal 3: Quality Wall (+2) ----
    pio_disp = f'{piotroski:.0f}' if piotroski is not None else 'n/a'
    if piotroski is not None and piotroski >= QUALITY_PIOTROSKI:
        s3 = (2, f'Piotroski {pio_disp} >= {QUALITY_PIOTROSKI}')
    else:
        s3 = (0, f'Piotroski {pio_disp}, needs >={QUALITY_PIOTROSKI}')

    # ---- Signal 4: Sector Safe (+1) ----
    this_sector_pct = sector_pct.get(sector, 0.0)
    if this_sector_pct < SECTOR_CAP_PCT:
        s4 = (1, f'{sector} {this_sector_pct:.0f}% of book (<{SECTOR_CAP_PCT:.0f}%)')
    else:
        s4 = (0, f'{sector} {this_sector_pct:.0f}% of book (>={SECTOR_CAP_PCT:.0f}%)')

    # ---- Signal 5: Growth Intact (+1) ----
    yoy_disp = f'{yoy:.0f}%' if yoy is not None else 'n/a'
    if yoy is not None and yoy > GROWTH_YOY:
        s5 = (1, f'NP YoY {yoy_disp} > {GROWTH_YOY:.0f}%')
    else:
        s5 = (0, f'NP YoY {yoy_disp}, needs >{GROWTH_YOY:.0f}%')

    # ---- Signal 6: Fresh Qualifier (+1) ----
    if ticker in fresh_tickers:
        s6 = (1, 'fresh qualifier')
    else:
        s6 = (0, 'not a fresh qualifier')

    total = s1[0] + s2[0] + s3[0] + s4[0] + s5[0] + s6[0]

    # ---- verdict ----
    if total >= DEPLOY_MIN:
        verdict = 'DEPLOY'
    elif total >= HOLDFIRE_MIN:
        verdict = 'HOLD-FIRE'
    else:
        verdict = 'PASS'

    # ---- build the Decision ----
    d = Decision('C', ticker, verdict, 'Module 1 - Value Conviction Scoring')
    d.add_signal('Multi-Engine',   3, s1[0], s1[1])
    d.add_signal('Deep Value',     2, s2[0], s2[1])
    d.add_signal('Quality Wall',   2, s3[0], s3[1])
    d.add_signal('Sector Safe',    1, s4[0], s4[1])
    d.add_signal('Growth Intact',  1, s5[0], s5[1])
    d.add_signal('Fresh Qualifier',1, s6[0], s6[1])

    if verdict == 'DEPLOY':
        d.set_margin('points clear of DEPLOY', total - DEPLOY_MIN)
    elif verdict == 'HOLD-FIRE':
        d.set_margin('points to DEPLOY', total - DEPLOY_MIN)
    else:
        d.set_margin('points to HOLD-FIRE', total - HOLDFIRE_MIN)

    if verdict != 'DEPLOY':
        gaps = []
        if s1[0] == 0:
            gaps.append('also qualifies in B/D (+3)')
        if s2[0] == 0 and pe is not None:
            gaps.append(f'PE falls below {DEEP_VALUE_PE:.0f} (+2)')
        if s3[0] == 0 and piotroski is not None:
            gaps.append(f'Piotroski rises to {QUALITY_PIOTROSKI} (+2)')
        if s5[0] == 0 and yoy is not None:
            gaps.append(f'NP YoY rises above {GROWTH_YOY:.0f}% (+1)')
        need = DEPLOY_MIN - total
        d.set_counterfactual(
            f'-> DEPLOY (needs +{need}) if: ' +
            (' OR '.join(gaps) if gaps else 'no single signal closes the gap'))
    else:
        d.set_counterfactual('already DEPLOY - would drop to HOLD-FIRE if it '
                              f'loses more than {total - HOLDFIRE_MIN + 1} points')
    return d


def score_screener(csv_path, bd_tickers=None, held_positions=None,
                    fresh_tickers=None):
    """Score an entire C2 value screener CSV. Returns Decisions, best first."""
    rows = load_screener(csv_path)
    sector_pct = sector_exposure(held_positions or [])
    decisions = [score_stock(tk, row, bd_tickers, sector_pct, fresh_tickers)
                 for tk, row in rows.items()]
    decisions.sort(key=lambda d: d.total_score(), reverse=True)
    return decisions


# ---- self-test / live run ----
if __name__ == '__main__':
    import os
    print('=' * 64)
    print('ENGINE C VALUE CONVICTION SCORING - run on live C2 screener')
    print('=' * 64)

    csv_path = '/mnt/user-data/uploads/C2_Value_May_16__2026.csv'
    if not os.path.exists(csv_path):
        csv_path = 'C2_Value_May_16__2026.csv'

    rows = load_screener(csv_path)
    fresh = set(rows.keys())
    decisions = score_screener(csv_path, fresh_tickers=fresh)

    deploy = [d for d in decisions if d.verdict == 'DEPLOY']
    holdf  = [d for d in decisions if d.verdict == 'HOLD-FIRE']
    passd  = [d for d in decisions if d.verdict == 'PASS']

    print(f'\nScored {len(decisions)} value stocks')
    print(f'  DEPLOY: {len(deploy)}   HOLD-FIRE: {len(holdf)}   PASS: {len(passd)}')

    print('\n--- ALL STOCKS BY CONVICTION ---')
    for d in decisions:
        print(f'  {d.ticker:14} {d.verdict:10} {d.total_score()}/10')

    print('\n--- SAMPLE FULL REASON STRING (highest conviction) ---')
    if decisions:
        print(' ', decisions[0].reason_string())

    print('\n' + '=' * 64)
    print('Value conviction scoring complete. Multi-Engine signal scores')
    print('0 until B/D screeners are wired (10-point scale retained).')
    print('=' * 64)
