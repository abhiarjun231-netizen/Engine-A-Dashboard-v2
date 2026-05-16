"""
engine_b_conviction.py
Parthsarthi Capital - Phase 2, Item 2.1
ENGINE B - CONVICTION SCORING (6-signal momentum model).

This is the first piece of Engine B itself. It takes the momentum
screener and scores every stock on six signals (max 10 points),
then assigns the verdict:

  7 - 10  STRIKE     buy at next session open
  4 - 6   STALK      stay in WATCH, re-score next upload
  1 - 3   SKIP       stay in WATCH, low priority

The six signals (from the Engine B framework):
  1. Multi-Engine       +3   also in Engine C or D screener
  2. Durability Fortress+2   Durability Score > 75
  3. Momentum Surge     +2   Momentum Score > 70
  4. Sector Safe        +1   sector < 30% of current B portfolio
  5. Volume Confirm     +1   weekly delivery % above monthly average
  6. Fresh Qualifier    +1   first appearance / 30+ day re-appearance

Every score produces a full reason string via the reasoning engine.

NOTE on the Multi-Engine signal: it needs the C and D screener lists.
Until those are wired, it is passed in as an (optional) set of tickers;
if not provided it scores 0 - the 10-point scale is retained so the
locked thresholds stay valid, exactly as the framework specifies.
"""

import csv
from reasoning_engine import Decision


# ---- thresholds (locked, from the Engine B framework) ----
DURABILITY_FORTRESS = 75
MOMENTUM_SURGE      = 70
SECTOR_CAP_PCT      = 30.0
STRIKE_MIN          = 7
STALK_MIN           = 4


def _num(v):
    """Best-effort numeric parse."""
    try:
        return float(str(v).replace(',', '').strip())
    except (ValueError, AttributeError, TypeError):
        return None


def load_screener(csv_path):
    """Load the momentum screener CSV -> {ticker: row}."""
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
    """
    Given current Engine B holdings [{ticker, sector}], return
    {sector: pct_of_portfolio}. Used by the Sector Safe signal.
    """
    if not held_positions:
        return {}
    n = len(held_positions)
    counts = {}
    for p in held_positions:
        s = p.get('sector', 'Unknown')
        counts[s] = counts.get(s, 0) + 1
    return {s: c / n * 100.0 for s, c in counts.items()}


def score_stock(ticker, row, cd_tickers=None, sector_pct=None,
                fresh_tickers=None):
    """
    Score one stock on the 6-signal model. Returns a Decision object
    (from reasoning_engine) carrying the verdict and full reason string.

    cd_tickers    - set of tickers also in Engine C or D screeners
    sector_pct    - {sector: pct} of current B portfolio
    fresh_tickers - set of tickers that are fresh qualifiers
    """
    cd_tickers = cd_tickers or set()
    sector_pct = sector_pct or {}
    fresh_tickers = fresh_tickers or set()

    dur = _num(row.get('Durability Score'))
    mom = _num(row.get('Momentum Score'))
    sector = row.get('Sector', 'Unknown')
    wk_deliv = _num(row.get('Delivery% Vol  Avg Week'))
    mo_deliv = _num(row.get('Delivery% Vol  Avg Month'))

    # ---- Signal 1: Multi-Engine (+3) ----
    if ticker in cd_tickers:
        s1 = (3, 'also qualifies in Engine C or D')
    else:
        s1 = (0, 'not in C or D screener')

    # ---- Signal 2: Durability Fortress (+2) ----
    dur_disp = f'{dur:.0f}' if dur is not None else 'n/a'
    if dur is not None and dur > DURABILITY_FORTRESS:
        s2 = (2, f'Durability {dur_disp} > {DURABILITY_FORTRESS}')
    else:
        s2 = (0, f'Durability {dur_disp}, needs >{DURABILITY_FORTRESS}')

    # ---- Signal 3: Momentum Surge (+2) ----
    mom_disp = f'{mom:.0f}' if mom is not None else 'n/a'
    if mom is not None and mom > MOMENTUM_SURGE:
        s3 = (2, f'Momentum {mom_disp} > {MOMENTUM_SURGE}')
    else:
        s3 = (0, f'Momentum {mom_disp}, needs >{MOMENTUM_SURGE}')

    # ---- Signal 4: Sector Safe (+1) ----
    this_sector_pct = sector_pct.get(sector, 0.0)
    if this_sector_pct < SECTOR_CAP_PCT:
        s4 = (1, f'{sector} {this_sector_pct:.0f}% of book (<{SECTOR_CAP_PCT:.0f}%)')
    else:
        s4 = (0, f'{sector} {this_sector_pct:.0f}% of book (>={SECTOR_CAP_PCT:.0f}%)')

    # ---- Signal 5: Volume Confirm (+1) ----
    if (wk_deliv is not None and mo_deliv is not None
            and wk_deliv > mo_deliv):
        s5 = (1, f'weekly delivery {wk_deliv:.0f}% > monthly {mo_deliv:.0f}%')
    else:
        s5 = (0, 'weekly delivery not above monthly average')

    # ---- Signal 6: Fresh Qualifier (+1) ----
    if ticker in fresh_tickers:
        s6 = (1, 'fresh qualifier')
    else:
        s6 = (0, 'not a fresh qualifier')

    total = s1[0] + s2[0] + s3[0] + s4[0] + s5[0] + s6[0]

    # ---- verdict ----
    if total >= STRIKE_MIN:
        verdict = 'STRIKE'
    elif total >= STALK_MIN:
        verdict = 'STALK'
    else:
        verdict = 'SKIP'

    # ---- build the Decision / reason string ----
    d = Decision('B', ticker, verdict, 'Module 1 - Conviction Scoring')
    d.add_signal('Multi-Engine',        3, s1[0], s1[1])
    d.add_signal('Durability Fortress', 2, s2[0], s2[1])
    d.add_signal('Momentum Surge',      2, s3[0], s3[1])
    d.add_signal('Sector Safe',         1, s4[0], s4[1])
    d.add_signal('Volume Confirm',      1, s5[0], s5[1])
    d.add_signal('Fresh Qualifier',     1, s6[0], s6[1])

    # margin to the nearest band boundary
    if verdict == 'STRIKE':
        d.set_margin('points clear of STRIKE', total - STRIKE_MIN)
    elif verdict == 'STALK':
        d.set_margin('points to STRIKE', total - STRIKE_MIN)
    else:
        d.set_margin('points to STALK', total - STALK_MIN)

    # counterfactual - what would flip it up
    if verdict != 'STRIKE':
        gaps = []
        if s1[0] == 0:
            gaps.append('also qualifies in C/D (+3)')
        if s2[0] == 0 and dur is not None:
            gaps.append(f'Durability rises above {DURABILITY_FORTRESS} (+2)')
        if s3[0] == 0 and mom is not None:
            gaps.append(f'Momentum rises above {MOMENTUM_SURGE} (+2)')
        if s4[0] == 0:
            gaps.append(f'sector drops below {SECTOR_CAP_PCT:.0f}% (+1)')
        need = STRIKE_MIN - total
        d.set_counterfactual(
            f'-> STRIKE (needs +{need}) if: ' +
            (' OR '.join(gaps) if gaps else 'no single signal closes the gap'))
    else:
        d.set_counterfactual('already STRIKE - would drop to STALK if it '
                              'loses signals worth more than '
                              f'{total - STALK_MIN + 1} points')

    return d


def score_screener(csv_path, cd_tickers=None, held_positions=None,
                    fresh_tickers=None):
    """
    Score an entire momentum screener CSV.
    Returns a list of Decision objects, sorted highest conviction first.
    """
    rows = load_screener(csv_path)
    sector_pct = sector_exposure(held_positions or [])
    decisions = []
    for tk, row in rows.items():
        d = score_stock(tk, row, cd_tickers, sector_pct, fresh_tickers)
        decisions.append(d)
    decisions.sort(key=lambda d: d.total_score(), reverse=True)
    return decisions


# ---- self-test / live run ----
if __name__ == '__main__':
    import os
    print('=' * 64)
    print('ENGINE B CONVICTION SCORING - run on live screener')
    print('=' * 64)

    csv_path = '/mnt/user-data/uploads/Mom_1_May_16__2026.csv'
    if not os.path.exists(csv_path):
        # fallback location
        csv_path = 'Mom_1_May_16__2026.csv'

    # No C/D lists wired yet, no prior holdings, treat all as fresh.
    rows = load_screener(csv_path)
    fresh = set(rows.keys())

    decisions = score_screener(csv_path, cd_tickers=None,
                               held_positions=None, fresh_tickers=fresh)

    strike = [d for d in decisions if d.verdict == 'STRIKE']
    stalk  = [d for d in decisions if d.verdict == 'STALK']
    skip   = [d for d in decisions if d.verdict == 'SKIP']

    print(f'\nScored {len(decisions)} momentum stocks')
    print(f'  STRIKE: {len(strike)}   STALK: {len(stalk)}   SKIP: {len(skip)}')

    print('\n--- TOP 8 BY CONVICTION ---')
    for d in decisions[:8]:
        print(f'  {d.ticker:14} {d.verdict:7} {d.total_score()}/10')

    print('\n--- SAMPLE FULL REASON STRING (highest conviction) ---')
    if decisions:
        print(' ', decisions[0].reason_string())

    print('\n' + '=' * 64)
    print('Conviction scoring complete. Each stock has a verdict and a')
    print('full auditable reason string. Multi-Engine signal scores 0')
    print('until C/D screeners are wired (10-point scale retained).')
    print('=' * 64)
