"""
engine_b_conviction.py
Parthsarthi Capital - Engine B - MOMENTUM CONVICTION (percentile-ranked).

WHY THIS WAS REBUILT (again)
V1 binary - everything clustered. V2 fixed graded curves - spread,
but fixed. THIS version scores each metric as a PERCENTILE against
the screen, blended with a SECTOR-RELATIVE percentile. A stock is
judged against the actual universe and its own sector's peers.

Four momentum metrics, 10 points total:
  Trend strength      0 - 3.5   Momentum Score   (higher is better)
  Durability          0 - 2.5   Durability Score (higher is better)
  Range position      0 - 2.0   place in 52-week range (higher better)
  Delivery strength   0 - 2.0   weekly delivery vs monthly (higher better)

Verdict bands (plain English):
  >= 7.0   Buy      strong relative momentum, buy at next session open
  4.5-6.9  Watch    a real case, not yet strong enough
  < 4.5    Skip     does not clear the momentum bar

Cross-engine qualification is shown as a flag. Every decision
carries a plain-English summary from real numbers.
"""

import csv
from reasoning_engine import Decision
from ranking_engine import blended_rank


BUY_MIN   = 7.0
WATCH_MIN = 4.5

MAX_TREND    = 3.5
MAX_DURABLE  = 2.5
MAX_RANGE    = 2.0
MAX_DELIVERY = 2.0


def _num(v):
    try:
        return float(str(v).replace(',', '').replace('%', '').strip())
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
    """Kept for orchestrator compatibility - returns empty dict."""
    return {}


def _range_position(ltp, low, high):
    """Place in the 52-week range, 0-100. None if data missing."""
    if None in (ltp, low, high) or high <= low:
        return None
    return max(0.0, min(100.0, (ltp - low) / (high - low) * 100.0))


def _delivery_ratio(week, month):
    """Weekly delivery % over monthly average. None if data missing."""
    if week is None or month is None or month <= 0:
        return None
    return week / month


def _pts(rank, budget):
    if rank is None:
        return 0.0
    return round(rank / 100.0 * budget, 2)


# ---- descriptors keyed off the percentile rank ----

def _trend_desc(mom, rank):
    if mom is None:
        return 'momentum score not available'
    if rank >= 80:
        return f'among the strongest trends on the screen, a score of {mom:.0f}'
    if rank >= 55:
        return f'stronger momentum than most peers, a score of {mom:.0f}'
    if rank >= 30:
        return f'mid-pack momentum, a score of {mom:.0f}'
    return f'weaker momentum than peers, a score of {mom:.0f}'


def _durable_desc(dur, rank):
    if dur is None:
        return 'durability score not available'
    if rank >= 75:
        return f'a top-tier financial base, a Durability score of {dur:.0f}'
    if rank >= 45:
        return f'a sound financial base, a Durability score of {dur:.0f}'
    return f'a weaker financial base than peers, a Durability score of {dur:.0f}'


def _range_desc(pos, rank):
    if pos is None:
        return '52-week range not available'
    if rank >= 75:
        return f'pushing its 52-week high ({pos:.0f}% of range)'
    if rank >= 45:
        return f'in the upper part of its 52-week range ({pos:.0f}%)'
    return f'low in its 52-week range ({pos:.0f}%)'


def _delivery_desc(ratio, week, rank):
    if ratio is None:
        return 'delivery data not available'
    wk = f'{week:.0f}%' if week is not None else 'n/a'
    if rank >= 75:
        return f'delivery volume building faster than peers (this week {wk})'
    if rank >= 45:
        return f'steady delivery volume (this week {wk})'
    return f'softer delivery volume than peers (this week {wk})'


def score_screener(csv_path, cross_engine=None, **_ignored):
    """Score an entire momentum screener relative to the screen."""
    cross_engine = cross_engine or set()
    rows = load_screener(csv_path)
    tickers = list(rows.keys())

    mom  = {t: _num(rows[t].get('Momentum Score')) for t in tickers}
    dur  = {t: _num(rows[t].get('Durability Score')) for t in tickers}
    rng  = {t: _range_position(_num(rows[t].get('LTP')),
                               _num(rows[t].get('1Y Low')),
                               _num(rows[t].get('1Y High')))
            for t in tickers}
    dlv  = {t: _delivery_ratio(_num(rows[t].get('Delivery% Vol  Avg Week')),
                               _num(rows[t].get('Delivery% Vol  Avg Month')))
            for t in tickers}
    wk   = {t: _num(rows[t].get('Delivery% Vol  Avg Week')) for t in tickers}
    sect = {t: (rows[t].get('Sector') or 'Unknown') for t in tickers}

    t_rank = blended_rank([(t, mom[t]) for t in tickers], sect, True)
    d_rank = blended_rank([(t, dur[t]) for t in tickers], sect, True)
    r_rank = blended_rank([(t, rng[t]) for t in tickers], sect, True)
    v_rank = blended_rank([(t, dlv[t]) for t in tickers], sect, True)

    decisions = []
    for t in tickers:
        decisions.append(_build_decision(
            t, cross_engine,
            mom[t], t_rank.get(t), dur[t], d_rank.get(t),
            rng[t], r_rank.get(t), dlv[t], wk[t], v_rank.get(t)))
    decisions.sort(key=lambda d: d.total_score(), reverse=True)
    return decisions


def _build_decision(ticker, cross_engine, mom, t_rank, dur, d_rank,
                     rng, r_rank, dlv, wk, v_rank):
    t_pts = _pts(t_rank, MAX_TREND)
    d_pts = _pts(d_rank, MAX_DURABLE)
    r_pts = _pts(r_rank, MAX_RANGE)
    v_pts = _pts(v_rank, MAX_DELIVERY)
    total = round(t_pts + d_pts + r_pts + v_pts, 1)

    if total >= BUY_MIN:
        verdict = 'Buy'
    elif total >= WATCH_MIN:
        verdict = 'Watch'
    else:
        verdict = 'Skip'

    t_desc = _trend_desc(mom, t_rank or 0)
    d_desc = _durable_desc(dur, d_rank or 0)
    r_desc = _range_desc(rng, r_rank or 0)
    v_desc = _delivery_desc(dlv, wk, v_rank or 0)

    d = Decision('B', ticker, verdict, 'Momentum conviction (percentile-ranked)')
    d.add_signal('Trend strength',    MAX_TREND,    t_pts, t_desc)
    d.add_signal('Durability',        MAX_DURABLE,  d_pts, d_desc)
    d.add_signal('Range position',    MAX_RANGE,    r_pts, r_desc)
    d.add_signal('Delivery strength', MAX_DELIVERY, v_pts, v_desc)

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
            [('a better trend rank', MAX_TREND - t_pts),
             ('a better durability rank', MAX_DURABLE - d_pts),
             ('a better range-position rank', MAX_RANGE - r_pts),
             ('a better delivery rank', MAX_DELIVERY - v_pts)],
            key=lambda x: -x[1])
        d.set_counterfactual(
            f'To reach Buy this needs {round(BUY_MIN - total, 1)} more '
            f'points - the most room is in {gaps[0][0]}.')

    d.set_summary(_summary(ticker, verdict, total,
                           t_pts, t_desc, d_pts, d_desc,
                           r_pts, r_desc, v_pts, v_desc))
    return d


def _summary(ticker, verdict, total, t_pts, t_desc, d_pts, d_desc,
             r_pts, r_desc, v_pts, v_desc):
    comps = sorted(
        [('trend', t_pts, MAX_TREND, t_desc),
         ('durability', d_pts, MAX_DURABLE, d_desc),
         ('range position', r_pts, MAX_RANGE, r_desc),
         ('delivery', v_pts, MAX_DELIVERY, v_desc)],
        key=lambda x: -(x[1] / x[2] if x[2] else 0))
    lead, weak = comps[0], comps[-1]
    head = f'{verdict} - momentum conviction {total:.1f} of 10. '
    body = (f'{ticker} shows {lead[3]}, the strongest part of the case '
            f'({lead[1]:.1f} of {lead[2]:.1f}). ')
    body += 'It also has ' + ' and '.join(m[3] for m in comps[1:3]) + '. '
    if weak[2] and weak[1] / weak[2] < 0.45:
        body += (f'The weakest point is {weak[0]} - {weak[3]} '
                 f'({weak[1]:.1f} of {weak[2]:.1f}).')
    else:
        body += f'Even its weakest area, {weak[0]}, holds up - {weak[3]}.'
    body += (' Scores are ranked against this screen and against sector '
             'peers, so they reflect relative momentum, not a fixed cutoff.')
    return head + body


def score_stock(ticker, row, cross_engine=None, **_ignored):
    """Lone-stock fallback - scored at mid-rank. Prefer score_screener()."""
    cross_engine = cross_engine or set()
    mom = _num(row.get('Momentum Score'))
    dur = _num(row.get('Durability Score'))
    rng = _range_position(_num(row.get('LTP')),
                          _num(row.get('1Y Low')),
                          _num(row.get('1Y High')))
    dlv = _delivery_ratio(_num(row.get('Delivery% Vol  Avg Week')),
                          _num(row.get('Delivery% Vol  Avg Month')))
    wk  = _num(row.get('Delivery% Vol  Avg Week'))
    return _build_decision(ticker, cross_engine,
                           mom, 50.0, dur, 50.0, rng, 50.0, dlv, wk, 50.0)


# ---- self-test / live run ----
if __name__ == '__main__':
    import os
    print('=' * 66)
    print('ENGINE B - MOMENTUM CONVICTION (percentile-ranked) - live run')
    print('=' * 66)

    csv_path = '/mnt/user-data/uploads/Mom_1_May_16__2026.csv'
    if not os.path.exists(csv_path):
        csv_path = 'Mom_1_May_16__2026.csv'

    decisions = score_screener(csv_path)
    buys  = [d for d in decisions if d.verdict == 'Buy']
    watch = [d for d in decisions if d.verdict == 'Watch']
    skip  = [d for d in decisions if d.verdict == 'Skip']

    print(f'\nScored {len(decisions)} momentum stocks (ranked relative)')
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
    print('Percentile + sector-relative momentum scoring complete.')
    print('=' * 66)
