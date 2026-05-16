"""
engine_d_conviction.py
Parthsarthi Capital - Phase 4, Item 4.1
ENGINE D - COMPOUNDER CONVICTION SCORING (6-signal GARP model).

The first piece of Engine D. It scores every stock on the D1
compounder screener against six GARP-specific signals (max 10):

  1. Multi-Engine     +3   also qualifies in Engine B or C screener
  2. Elite Growth     +2   Net Profit 3Yr Growth > 25%
  3. Reasonable Price +2   PEG < 1.0
  4. Sector Safe      +1   sector < 30% of current D portfolio
  5. Quality Wall     +1   Piotroski Score >= 8
  6. Capital Efficient+1   ROE > 25%

Verdict bands:
  7 - 10  INCUBATE    deploy partial capital, begin 90-day incubation
  4 - 6   HOLD-FIRE   stay in WATCH, re-score next upload
  1 - 3   PASS        stay in WATCH, low priority

Note Engine D weights 3-YEAR growth, not just YoY - a compounder
must show durable multi-year growth, not one good year. The DEPLOY-
grade verdict is INCUBATE: Engine D never commits full capital at
entry (see the incubation engine, item 4.2).
"""

import csv
from reasoning_engine import Decision


# ---- locked thresholds (Engine D framework) ----
ELITE_GROWTH_3Y   = 25.0     # NP 3Yr growth above this -> Elite Growth
REASONABLE_PEG    = 1.0      # PEG below this -> Reasonable Price
QUALITY_PIOTROSKI = 8        # Piotroski >= this -> Quality Wall
CAPITAL_EFF_ROE   = 25.0     # ROE above this -> Capital Efficient
SECTOR_CAP_PCT    = 30.0
INCUBATE_MIN      = 7
HOLDFIRE_MIN      = 4


def _num(v):
    try:
        return float(str(v).replace(',', '').strip())
    except (ValueError, AttributeError, TypeError):
        return None


def load_screener(csv_path):
    """Load the D1 compounder screener CSV -> {ticker: row}."""
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
    """{sector: pct} of current Engine D portfolio."""
    if not held_positions:
        return {}
    n = len(held_positions)
    counts = {}
    for p in held_positions:
        s = p.get('sector', 'Unknown')
        counts[s] = counts.get(s, 0) + 1
    return {s: c / n * 100.0 for s, c in counts.items()}


def score_stock(ticker, row, bc_tickers=None, sector_pct=None,
                fresh_tickers=None):
    """
    Score one stock on the 6-signal compounder model.
    Returns a Decision carrying the verdict and full reason string.

    bc_tickers - set of tickers also in Engine B or C screeners
    """
    bc_tickers = bc_tickers or set()
    sector_pct = sector_pct or {}
    fresh_tickers = fresh_tickers or set()

    growth_3y = _num(row.get('Net Profit 3Y Growth %'))
    peg = _num(row.get('PEG TTM'))
    piotroski = _num(row.get('Piotroski Score'))
    roe = _num(row.get('ROE Ann  %'))
    sector = row.get('Sector', 'Unknown')

    # ---- Signal 1: Multi-Engine (+3) ----
    if ticker in bc_tickers:
        s1 = (3, 'also qualifies in Engine B or C')
    else:
        s1 = (0, 'not in B or C screener')

    # ---- Signal 2: Elite Growth (+2) ----
    g_disp = f'{growth_3y:.0f}%' if growth_3y is not None else 'n/a'
    if growth_3y is not None and growth_3y > ELITE_GROWTH_3Y:
        s2 = (2, f'3Yr profit growth {g_disp} > {ELITE_GROWTH_3Y:.0f}%')
    else:
        s2 = (0, f'3Yr profit growth {g_disp}, needs >{ELITE_GROWTH_3Y:.0f}%')

    # ---- Signal 3: Reasonable Price (+2) ----
    peg_disp = f'{peg:.2f}' if peg is not None else 'n/a'
    if peg is not None and 0 < peg < REASONABLE_PEG:
        s3 = (2, f'PEG {peg_disp} < {REASONABLE_PEG}')
    else:
        s3 = (0, f'PEG {peg_disp}, needs 0 < PEG < {REASONABLE_PEG}')

    # ---- Signal 4: Sector Safe (+1) ----
    this_sector_pct = sector_pct.get(sector, 0.0)
    if this_sector_pct < SECTOR_CAP_PCT:
        s4 = (1, f'{sector} {this_sector_pct:.0f}% of book (<{SECTOR_CAP_PCT:.0f}%)')
    else:
        s4 = (0, f'{sector} {this_sector_pct:.0f}% of book (>={SECTOR_CAP_PCT:.0f}%)')

    # ---- Signal 5: Quality Wall (+1) ----
    pio_disp = f'{piotroski:.0f}' if piotroski is not None else 'n/a'
    if piotroski is not None and piotroski >= QUALITY_PIOTROSKI:
        s5 = (1, f'Piotroski {pio_disp} >= {QUALITY_PIOTROSKI}')
    else:
        s5 = (0, f'Piotroski {pio_disp}, needs >={QUALITY_PIOTROSKI}')

    # ---- Signal 6: Capital Efficient (+1) ----
    roe_disp = f'{roe:.0f}%' if roe is not None else 'n/a'
    if roe is not None and roe > CAPITAL_EFF_ROE:
        s6 = (1, f'ROE {roe_disp} > {CAPITAL_EFF_ROE:.0f}%')
    else:
        s6 = (0, f'ROE {roe_disp}, needs >{CAPITAL_EFF_ROE:.0f}%')

    total = s1[0] + s2[0] + s3[0] + s4[0] + s5[0] + s6[0]

    # ---- verdict ----
    if total >= INCUBATE_MIN:
        verdict = 'INCUBATE'
    elif total >= HOLDFIRE_MIN:
        verdict = 'HOLD-FIRE'
    else:
        verdict = 'PASS'

    # ---- build the Decision ----
    d = Decision('D', ticker, verdict, 'Module 1 - Compounder Conviction Scoring')
    d.add_signal('Multi-Engine',      3, s1[0], s1[1])
    d.add_signal('Elite Growth',      2, s2[0], s2[1])
    d.add_signal('Reasonable Price',  2, s3[0], s3[1])
    d.add_signal('Sector Safe',       1, s4[0], s4[1])
    d.add_signal('Quality Wall',      1, s5[0], s5[1])
    d.add_signal('Capital Efficient', 1, s6[0], s6[1])

    if verdict == 'INCUBATE':
        d.set_margin('points clear of INCUBATE', total - INCUBATE_MIN)
    elif verdict == 'HOLD-FIRE':
        d.set_margin('points to INCUBATE', total - INCUBATE_MIN)
    else:
        d.set_margin('points to HOLD-FIRE', total - HOLDFIRE_MIN)

    if verdict != 'INCUBATE':
        gaps = []
        if s1[0] == 0:
            gaps.append('also qualifies in B/C (+3)')
        if s2[0] == 0 and growth_3y is not None:
            gaps.append(f'3Yr growth rises above {ELITE_GROWTH_3Y:.0f}% (+2)')
        if s3[0] == 0 and peg is not None:
            gaps.append(f'PEG falls below {REASONABLE_PEG} (+2)')
        if s6[0] == 0 and roe is not None:
            gaps.append(f'ROE rises above {CAPITAL_EFF_ROE:.0f}% (+1)')
        need = INCUBATE_MIN - total
        d.set_counterfactual(
            f'-> INCUBATE (needs +{need}) if: ' +
            (' OR '.join(gaps) if gaps else 'no single signal closes the gap'))
    else:
        d.set_counterfactual('already INCUBATE-grade - would drop to '
                              f'HOLD-FIRE if it loses more than '
                              f'{total - HOLDFIRE_MIN + 1} points')
    return d


def score_screener(csv_path, bc_tickers=None, held_positions=None,
                    fresh_tickers=None):
    """Score the whole D1 screener CSV. Returns Decisions, best first."""
    rows = load_screener(csv_path)
    sector_pct = sector_exposure(held_positions or [])
    decisions = [score_stock(tk, row, bc_tickers, sector_pct, fresh_tickers)
                 for tk, row in rows.items()]
    decisions.sort(key=lambda d: d.total_score(), reverse=True)
    return decisions


# ---- self-test / live run ----
if __name__ == '__main__':
    import os
    print('=' * 64)
    print('ENGINE D COMPOUNDER CONVICTION SCORING - run on live D1 screener')
    print('=' * 64)

    csv_path = '/mnt/user-data/uploads/D1_Compound_May_16__2026.csv'
    if not os.path.exists(csv_path):
        csv_path = 'D1_Compound_May_16__2026.csv'

    rows = load_screener(csv_path)
    fresh = set(rows.keys())
    decisions = score_screener(csv_path, fresh_tickers=fresh)

    inc = [d for d in decisions if d.verdict == 'INCUBATE']
    hf  = [d for d in decisions if d.verdict == 'HOLD-FIRE']
    ps  = [d for d in decisions if d.verdict == 'PASS']

    print(f'\nScored {len(decisions)} compounder stocks')
    print(f'  INCUBATE: {len(inc)}   HOLD-FIRE: {len(hf)}   PASS: {len(ps)}')

    print('\n--- TOP 12 BY CONVICTION ---')
    for d in decisions[:12]:
        print(f'  {d.ticker:14} {d.verdict:10} {d.total_score()}/10')

    print('\n--- SAMPLE FULL REASON STRING (highest conviction) ---')
    if decisions:
        print(' ', decisions[0].reason_string())

    print('\n' + '=' * 64)
    print('Compounder conviction scoring complete. Multi-Engine signal')
    print('scores 0 until B/C screeners are wired (10-point scale kept).')
    print('=' * 64)
