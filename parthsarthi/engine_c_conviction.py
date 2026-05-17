"""
engine_c_conviction.py
Parthsarthi Capital - Engine C - VALUE CONVICTION (percentile-ranked).

WHY THIS WAS REBUILT (again)
Version 1 used binary signals - everything clustered at 7/10.
Version 2 used fixed graded curves - scores spread, but the curves
were fixed judgments that did not breathe with the market.
THIS version scores each metric as a PERCENTILE against the screen,
blended with a SECTOR-RELATIVE percentile. This is the institutional
method: a stock is judged against the actual universe and against
its own sector's peers, not against a number fixed at build time.

HOW IT WORKS
For every stock on the C2 value screener, each of the four value
metrics is ranked 0-100:
  - a whole-universe percentile (cheapest 5% of the screen?)
  - a sector-relative percentile (cheapest 10% of cement stocks?)
  - blended 60/40 in favour of the sector-relative view
The blended 0-100 rank is then scaled to the metric's point budget.

Four value metrics, 10 points total:
  Cheapness          0 - 3.5   PE TTM            (lower is better)
  Quality            0 - 2.5   Piotroski F-Score (higher is better)
  Earnings growth    0 - 2.0   net-profit YoY %  (higher is better)
  Capital efficiency 0 - 2.0   ROE %             (higher is better)

Verdict bands (plain English):
  >= 7.0   Buy      strong relative value, buy at next session open
  4.5-6.9  Watch    a real case, not yet strong enough
  < 4.5    Skip     does not clear the value bar

Because scores are relative, they auto-adjust: in a screen full of
cheap stocks, only the cheapest still top out - the bar rises with
the universe. Cross-engine qualification is shown as a flag.
Every decision carries a plain-English summary from real numbers.
"""

import csv
from reasoning_engine import Decision
from ranking_engine import blended_rank


# ---- verdict bands ----
BUY_MIN   = 7.0
WATCH_MIN = 4.5

# ---- metric point budgets (sum = 10.0) ----
MAX_CHEAP   = 3.5
MAX_QUALITY = 2.5
MAX_GROWTH  = 2.0
MAX_ROE     = 2.0


def _num(v):
    try:
        return float(str(v).replace(',', '').replace('%', '').strip())
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
    """Kept for orchestrator compatibility - returns empty dict."""
    return {}


# ---- plain-English descriptors keyed off the percentile rank ----

def _cheap_desc(pe, rank):
    if pe is None:
        return 'PE not available'
    if rank >= 80:
        return f'among the cheapest on the screen, a PE of {pe:.1f}'
    if rank >= 55:
        return f'cheaper than most peers, a PE of {pe:.1f}'
    if rank >= 30:
        return f'mid-pack on price, a PE of {pe:.1f}'
    return f'expensive relative to peers, a PE of {pe:.1f}'


def _quality_desc(pio, rank):
    if pio is None:
        return 'Piotroski score not available'
    if rank >= 75:
        return f'top-tier quality, a Piotroski score of {pio:.0f} of 9'
    if rank >= 45:
        return f'sound quality, a Piotroski score of {pio:.0f} of 9'
    return f'below-peer quality, a Piotroski score of {pio:.0f} of 9'


def _growth_desc(yoy, rank):
    if yoy is None:
        return 'earnings growth not available'
    if yoy < 0:
        return f'earnings fell {abs(yoy):.0f}% over the year'
    if rank >= 75:
        return f'among the fastest growers, earnings up {yoy:.0f}%'
    if rank >= 45:
        return f'solid earnings growth, up {yoy:.0f}%'
    return f'slower growth than peers, up {yoy:.0f}%'


def _roe_desc(roe, rank):
    if roe is None:
        return 'return on equity not available'
    if rank >= 75:
        return f'top-tier capital efficiency, an ROE of {roe:.0f}%'
    if rank >= 45:
        return f'sound capital efficiency, an ROE of {roe:.0f}%'
    return f'below-peer capital efficiency, an ROE of {roe:.0f}%'


def _pts(rank, budget):
    """Scale a 0-100 percentile rank to a 0-budget point score."""
    if rank is None:
        return 0.0
    return round(rank / 100.0 * budget, 2)


def score_screener(csv_path, cross_engine=None, **_ignored):
    """
    Score an entire C2 screener. Because ranking is relative, the
    whole screen must be scored together - this is the main entry.
    Returns a list of Decisions, highest conviction first.
    """
    cross_engine = cross_engine or set()
    rows = load_screener(csv_path)
    tickers = list(rows.keys())

    pe   = {t: _num(rows[t].get('PE TTM')) for t in tickers}
    pio  = {t: _num(rows[t].get('Piotroski Score')) for t in tickers}
    yoy  = {t: _num(rows[t].get('Net Profit Ann  YoY Growth %'))
            for t in tickers}
    roe  = {t: _num(rows[t].get('ROE Ann  %')) for t in tickers}
    sect = {t: (rows[t].get('Sector') or 'Unknown') for t in tickers}

    cheap_rank = blended_rank([(t, pe[t]) for t in tickers], sect,
                              higher_is_better=False)   # low PE is good
    qual_rank  = blended_rank([(t, pio[t]) for t in tickers], sect,
                              higher_is_better=True)
    grow_rank  = blended_rank([(t, yoy[t]) for t in tickers], sect,
                              higher_is_better=True)
    roe_rank   = blended_rank([(t, roe[t]) for t in tickers], sect,
                              higher_is_better=True)

    decisions = []
    for t in tickers:
        decisions.append(_build_decision(
            t, cross_engine,
            pe[t], cheap_rank.get(t), pio[t], qual_rank.get(t),
            yoy[t], grow_rank.get(t), roe[t], roe_rank.get(t)))
    decisions.sort(key=lambda d: d.total_score(), reverse=True)
    return decisions


def _build_decision(ticker, cross_engine, pe, c_rank, pio, q_rank,
                     yoy, g_rank, roe, r_rank):
    """Assemble one stock's Decision from its four ranked metrics."""
    c_pts = _pts(c_rank, MAX_CHEAP)
    q_pts = _pts(q_rank, MAX_QUALITY)
    g_pts = _pts(g_rank, MAX_GROWTH)
    r_pts = _pts(r_rank, MAX_ROE)
    total = round(c_pts + q_pts + g_pts + r_pts, 1)

    if total >= BUY_MIN:
        verdict = 'Buy'
    elif total >= WATCH_MIN:
        verdict = 'Watch'
    else:
        verdict = 'Skip'

    c_desc = _cheap_desc(pe, c_rank or 0)
    q_desc = _quality_desc(pio, q_rank or 0)
    g_desc = _growth_desc(yoy, g_rank or 0)
    r_desc = _roe_desc(roe, r_rank or 0)

    d = Decision('C', ticker, verdict, 'Value conviction (percentile-ranked)')
    d.add_signal('Cheapness',          MAX_CHEAP,   c_pts, c_desc)
    d.add_signal('Quality',            MAX_QUALITY, q_pts, q_desc)
    d.add_signal('Earnings growth',    MAX_GROWTH,  g_pts, g_desc)
    d.add_signal('Capital efficiency', MAX_ROE,     r_pts, r_desc)

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
            [('a better cheapness rank', MAX_CHEAP - c_pts),
             ('a better quality rank', MAX_QUALITY - q_pts),
             ('a better growth rank', MAX_GROWTH - g_pts),
             ('a better ROE rank', MAX_ROE - r_pts)],
            key=lambda x: -x[1])
        d.set_counterfactual(
            f'To reach Buy this needs {round(BUY_MIN - total, 1)} more '
            f'points - the most room is in {gaps[0][0]}.')

    d.set_summary(_summary(ticker, verdict, total,
                           c_pts, c_desc, q_pts, q_desc,
                           g_pts, g_desc, r_pts, r_desc))
    return d


def _summary(ticker, verdict, total, c_pts, c_desc, q_pts, q_desc,
             g_pts, g_desc, r_pts, r_desc):
    comps = sorted(
        [('cheapness', c_pts, MAX_CHEAP, c_desc),
         ('quality', q_pts, MAX_QUALITY, q_desc),
         ('growth', g_pts, MAX_GROWTH, g_desc),
         ('capital efficiency', r_pts, MAX_ROE, r_desc)],
        key=lambda x: -(x[1] / x[2] if x[2] else 0))
    lead, weak = comps[0], comps[-1]
    head = f'{verdict} - value conviction {total:.1f} of 10. '
    body = (f'{ticker} is {lead[3]}, the strongest part of the case '
            f'({lead[1]:.1f} of {lead[2]:.1f}). ')
    body += 'It also shows ' + ' and '.join(m[3] for m in comps[1:3]) + '. '
    if weak[2] and weak[1] / weak[2] < 0.45:
        body += (f'The weakest point is {weak[0]} - {weak[3]} '
                 f'({weak[1]:.1f} of {weak[2]:.1f}).')
    else:
        body += f'Even its weakest area, {weak[0]}, holds up - {weak[3]}.'
    body += (' Scores are ranked against this screen and against sector '
             'peers, so they reflect relative value, not a fixed cutoff.')
    return head + body


def score_stock(ticker, row, cross_engine=None, **_ignored):
    """
    Single-stock scoring, kept for orchestrator compatibility.
    Percentile ranking is relative to the whole screen, so a lone
    stock cannot be truly relative - it is scored at mid-rank.
    Orchestrators should prefer score_screener().
    """
    cross_engine = cross_engine or set()
    pe  = _num(row.get('PE TTM'))
    pio = _num(row.get('Piotroski Score'))
    yoy = _num(row.get('Net Profit Ann  YoY Growth %'))
    roe = _num(row.get('ROE Ann  %'))
    return _build_decision(ticker, cross_engine,
                           pe, 50.0, pio, 50.0, yoy, 50.0, roe, 50.0)


# ---- self-test / live run ----
if __name__ == '__main__':
    import os
    print('=' * 66)
    print('ENGINE C - VALUE CONVICTION (percentile-ranked) - live run')
    print('=' * 66)

    csv_path = '/mnt/user-data/uploads/C2_Value_May_16__2026.csv'
    if not os.path.exists(csv_path):
        csv_path = 'C2_Value_May_16__2026.csv'

    decisions = score_screener(csv_path)
    buys  = [d for d in decisions if d.verdict == 'Buy']
    watch = [d for d in decisions if d.verdict == 'Watch']
    skip  = [d for d in decisions if d.verdict == 'Skip']

    print(f'\nScored {len(decisions)} value stocks (ranked relative to screen)')
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
    print('Percentile + sector-relative scoring complete.')
    print('=' * 66)
