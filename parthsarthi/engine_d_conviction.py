"""
engine_d_conviction.py
Parthsarthi Capital - Engine D - COMPOUNDER CONVICTION (percentile-ranked).

WHY THIS WAS REBUILT (again)
V1 binary - everything clustered. V2 fixed graded curves - spread,
but fixed. THIS version scores each metric as a PERCENTILE against
the screen, blended with a SECTOR-RELATIVE percentile. A stock is
judged against the actual universe and its own sector's peers.

Engine D looks for COMPOUNDERS - growth at a reasonable price (GARP).
Four metrics, 10 points total:
  Long-term growth   0 - 3.0   net-profit 3Y growth % (higher is better)
  Price for growth   0 - 3.0   PEG TTM                (lower is better)
  Capital efficiency 0 - 2.0   ROE %                  (higher is better)
  Quality            0 - 2.0   Piotroski F-Score      (higher is better)

Verdict bands (plain English):
  >= 7.0   Buy      a strong compounder - begin a half-size position
  4.5-6.9  Watch    a real candidate, not yet strong enough
  < 4.5    Skip     does not clear the compounder bar

IMPORTANT - Engine D buys slowly. A 'Buy' means BEGIN A HALF
POSITION and review at 90 days, never a full commitment on day one.
That distinction is carried in the summary text.

Cross-engine qualification is shown as a flag. Every decision
carries a plain-English summary from real numbers.
"""

import csv
from reasoning_engine import Decision
from ranking_engine import blended_rank


BUY_MIN   = 7.0
WATCH_MIN = 4.5

MAX_GROWTH  = 3.0
MAX_PEG     = 3.0
MAX_ROE     = 2.0
MAX_QUALITY = 2.0


def _num(v):
    try:
        return float(str(v).replace(',', '').replace('%', '').strip())
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
    """Kept for orchestrator compatibility - returns empty dict."""
    return {}


def _pts(rank, budget):
    if rank is None:
        return 0.0
    return round(rank / 100.0 * budget, 2)


# ---- descriptors keyed off the percentile rank ----

def _growth_desc(g, rank):
    if g is None:
        return '3-year growth not available'
    if g < 0:
        return f'profit shrank over three years ({g:.0f}%)'
    if rank >= 80:
        return f'among the fastest compounders, profit up {g:.0f}% over 3 years'
    if rank >= 50:
        return f'a strong 3-year compounder, profit up {g:.0f}%'
    return f'slower 3-year growth than peers, up {g:.0f}%'


def _peg_desc(peg, rank):
    if peg is None or peg <= 0:
        return 'PEG not available'
    if rank >= 80:
        return f'growth is keenly priced versus peers, a PEG of {peg:.2f}'
    if rank >= 50:
        return f'growth is fairly priced, a PEG of {peg:.2f}'
    return f'growth is dearer than peers, a PEG of {peg:.2f}'


def _roe_desc(roe, rank):
    if roe is None:
        return 'return on equity not available'
    if rank >= 75:
        return f'top-tier capital efficiency, an ROE of {roe:.0f}%'
    if rank >= 45:
        return f'sound capital efficiency, an ROE of {roe:.0f}%'
    return f'below-peer capital efficiency, an ROE of {roe:.0f}%'


def _quality_desc(pio, rank):
    if pio is None:
        return 'Piotroski score not available'
    if rank >= 75:
        return f'top-tier quality, a Piotroski score of {pio:.0f} of 9'
    if rank >= 45:
        return f'sound quality, a Piotroski score of {pio:.0f} of 9'
    return f'below-peer quality, a Piotroski score of {pio:.0f} of 9'


def score_screener(csv_path, cross_engine=None, **_ignored):
    """Score an entire D1 screener relative to the screen."""
    cross_engine = cross_engine or set()
    rows = load_screener(csv_path)
    tickers = list(rows.keys())

    grw  = {t: _num(rows[t].get('Net Profit 3Y Growth %')) for t in tickers}
    peg  = {t: _num(rows[t].get('PEG TTM')) for t in tickers}
    roe  = {t: _num(rows[t].get('ROE Ann  %')) for t in tickers}
    pio  = {t: _num(rows[t].get('Piotroski Score')) for t in tickers}
    sect = {t: (rows[t].get('Sector') or 'Unknown') for t in tickers}

    # PEG: a non-positive PEG is meaningless - treat as missing
    peg_clean = {t: (peg[t] if (peg[t] is not None and peg[t] > 0) else None)
                 for t in tickers}

    g_rank = blended_rank([(t, grw[t]) for t in tickers], sect, True)
    p_rank = blended_rank([(t, peg_clean[t]) for t in tickers], sect,
                          higher_is_better=False)   # low PEG is good
    r_rank = blended_rank([(t, roe[t]) for t in tickers], sect, True)
    q_rank = blended_rank([(t, pio[t]) for t in tickers], sect, True)

    decisions = []
    for t in tickers:
        decisions.append(_build_decision(
            t, cross_engine,
            grw[t], g_rank.get(t), peg_clean[t], p_rank.get(t),
            roe[t], r_rank.get(t), pio[t], q_rank.get(t)))
    decisions.sort(key=lambda d: d.total_score(), reverse=True)
    return decisions


def _build_decision(ticker, cross_engine, grw, g_rank, peg, p_rank,
                     roe, r_rank, pio, q_rank):
    g_pts = _pts(g_rank, MAX_GROWTH)
    p_pts = _pts(p_rank, MAX_PEG)
    r_pts = _pts(r_rank, MAX_ROE)
    q_pts = _pts(q_rank, MAX_QUALITY)
    total = round(g_pts + p_pts + r_pts + q_pts, 1)

    if total >= BUY_MIN:
        verdict = 'Buy'
    elif total >= WATCH_MIN:
        verdict = 'Watch'
    else:
        verdict = 'Skip'

    g_desc = _growth_desc(grw, g_rank or 0)
    p_desc = _peg_desc(peg, p_rank or 0)
    r_desc = _roe_desc(roe, r_rank or 0)
    q_desc = _quality_desc(pio, q_rank or 0)

    d = Decision('D', ticker, verdict,
                 'Compounder conviction (percentile-ranked)')
    d.add_signal('Long-term growth',   MAX_GROWTH,  g_pts, g_desc)
    d.add_signal('Price for growth',   MAX_PEG,     p_pts, p_desc)
    d.add_signal('Capital efficiency', MAX_ROE,     r_pts, r_desc)
    d.add_signal('Quality',            MAX_QUALITY, q_pts, q_desc)

    if ticker in cross_engine:
        d.add_flag('Also appears on another engine\'s screen - a stronger, '
                   'multi-angle pick.')

    if verdict == 'Buy':
        d.set_margin('points clear of the Buy line', round(total - BUY_MIN, 1))
    elif verdict == 'Watch':
        d.set_margin('points short of Buy', round(BUY_MIN - total, 1))
    else:
        d.set_margin('points short of Watch', round(WATCH_MIN - total, 1))

    if verdict == 'Buy':
        d.set_counterfactual(
            f'This stays a Buy unless conviction falls below {BUY_MIN:.0f}.')
    else:
        gaps = sorted(
            [('a better growth rank', MAX_GROWTH - g_pts),
             ('a better PEG rank', MAX_PEG - p_pts),
             ('a better ROE rank', MAX_ROE - r_pts),
             ('a better quality rank', MAX_QUALITY - q_pts)],
            key=lambda x: -x[1])
        d.set_counterfactual(
            f'To reach Buy this needs {round(BUY_MIN - total, 1)} more '
            f'points - the most room is in {gaps[0][0]}.')

    d.set_summary(_summary(ticker, verdict, total,
                           g_pts, g_desc, p_pts, p_desc,
                           r_pts, r_desc, q_pts, q_desc))
    return d


def _summary(ticker, verdict, total, g_pts, g_desc, p_pts, p_desc,
             r_pts, r_desc, q_pts, q_desc):
    comps = sorted(
        [('long-term growth', g_pts, MAX_GROWTH, g_desc),
         ('price for growth', p_pts, MAX_PEG, p_desc),
         ('capital efficiency', r_pts, MAX_ROE, r_desc),
         ('quality', q_pts, MAX_QUALITY, q_desc)],
        key=lambda x: -(x[1] / x[2] if x[2] else 0))
    lead, weak = comps[0], comps[-1]

    if verdict == 'Buy':
        head = (f'Buy (begin a half position) - compounder conviction '
                f'{total:.1f} of 10. ')
    else:
        head = f'{verdict} - compounder conviction {total:.1f} of 10. '

    body = (f'{ticker} shows {lead[3]}, the strongest part of the case '
            f'({lead[1]:.1f} of {lead[2]:.1f}). ')
    body += 'It also has ' + ' and '.join(m[3] for m in comps[1:3]) + '. '
    if weak[2] and weak[1] / weak[2] < 0.45:
        body += (f'The weakest point is {weak[0]} - {weak[3]} '
                 f'({weak[1]:.1f} of {weak[2]:.1f}).')
    else:
        body += f'Even its weakest area, {weak[0]}, holds up - {weak[3]}.'
    body += (' Scores are ranked against this screen and against sector '
             'peers, not a fixed cutoff.')
    if verdict == 'Buy':
        body += (' As a compounder, the position starts at half size and '
                 'is reviewed at 90 days before any top-up.')
    return head + body


def score_stock(ticker, row, cross_engine=None, **_ignored):
    """Lone-stock fallback - scored at mid-rank. Prefer score_screener()."""
    cross_engine = cross_engine or set()
    grw = _num(row.get('Net Profit 3Y Growth %'))
    peg = _num(row.get('PEG TTM'))
    peg = peg if (peg is not None and peg > 0) else None
    roe = _num(row.get('ROE Ann  %'))
    pio = _num(row.get('Piotroski Score'))
    return _build_decision(ticker, cross_engine,
                           grw, 50.0, peg, 50.0, roe, 50.0, pio, 50.0)


# ---- self-test / live run ----
if __name__ == '__main__':
    import os
    print('=' * 66)
    print('ENGINE D - COMPOUNDER CONVICTION (percentile-ranked) - live run')
    print('=' * 66)

    csv_path = '/mnt/user-data/uploads/D1_Compound_May_16__2026.csv'
    if not os.path.exists(csv_path):
        csv_path = 'D1_Compound_May_16__2026.csv'

    decisions = score_screener(csv_path)
    buys  = [d for d in decisions if d.verdict == 'Buy']
    watch = [d for d in decisions if d.verdict == 'Watch']
    skip  = [d for d in decisions if d.verdict == 'Skip']

    print(f'\nScored {len(decisions)} compounder stocks (ranked relative)')
    print(f'  Buy: {len(buys)}   Watch: {len(watch)}   Skip: {len(skip)}')

    scores = [d.total_score() for d in decisions]
    print(f'\nSCORE SPREAD: highest {max(scores):.1f} / lowest {min(scores):.1f}'
          f' / {len(set(scores))} distinct values')

    print('\n--- ALL STOCKS BY CONVICTION ---')
    for d in decisions:
        print(f'  {d.ticker:14} {d.verdict:6} {d.total_score():4.1f}/10')

    print('\n--- TOP 3 PLAIN-ENGLISH SUMMARIES ---')
    for d in decisions[:3]:
        print(f'\n  [{d.ticker}]')
        print(f'  {d.summary}')

    print('\n' + '=' * 66)
    print('Percentile + sector-relative compounder scoring complete.')
    print('=' * 66)
