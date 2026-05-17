"""
ranking_engine.py
Parthsarthi Capital - PERCENTILE & SECTOR-RELATIVE RANKING.

WHY THIS EXISTS
The graded conviction modules used fixed curves - "PE 8 earns full
marks" is a judgment baked in at build time. A fixed curve does not
breathe with the market: in an expensive market nothing looks cheap,
yet a fixed curve keeps handing out the same scores.

An institutional desk does not score against a fixed number. It
scores against the UNIVERSE: "this stock is in the cheapest 6% of
everything on the screen today." And it scores SECTOR-RELATIVE:
"cheapest 10% of cement stocks" - because metals and PSUs are
structurally cheap and a raw value score just keeps buying them.

THIS MODULE provides both, as a shared service the three conviction
engines call:

  percentile_rank(values)        - each value's 0-100 percentile
                                   within the whole screen
  sector_relative_rank(values,
                        sectors) - each value's 0-100 percentile
                                   within its OWN sector

A percentile of 100 = best in the group; 0 = worst. "Best" can mean
high-is-good (momentum, ROE) or low-is-good (PE, PEG) - the caller
says which via the `higher_is_better` flag.

Sector-relative ranking needs enough peers to be meaningful. If a
stock's sector has fewer than MIN_SECTOR_PEERS members on the
screen, its sector rank falls back to the whole-universe rank -
ranking a stock against two peers is noise, not signal.
"""

MIN_SECTOR_PEERS = 4    # below this, fall back to universe ranking


def _percentile_of_each(values, higher_is_better):
    """
    Given a list of (index, numeric_value), return {index: percentile}.
    Percentile is 0-100; 100 = best. None values get percentile None.

    Method: a value's percentile is the fraction of OTHER valid values
    it beats (or ties at half-credit), scaled to 0-100. This is the
    standard 'mean rank' percentile - stable with ties and small n.
    """
    valid = [(i, v) for i, v in values if v is not None]
    out = {i: None for i, _ in values}

    n = len(valid)
    if n == 0:
        return out
    if n == 1:
        out[valid[0][0]] = 50.0      # a lone value is neither best nor worst
        return out

    for i, v in valid:
        wins = 0.0
        for j, w in valid:
            if i == j:
                continue
            if higher_is_better:
                if v > w:
                    wins += 1.0
                elif v == w:
                    wins += 0.5
            else:   # lower is better
                if v < w:
                    wins += 1.0
                elif v == w:
                    wins += 0.5
        out[i] = round(wins / (n - 1) * 100.0, 1)
    return out


def percentile_rank(values, higher_is_better=True):
    """
    Rank every value against the WHOLE screen.

    values - list of (key, numeric_value_or_None)
    Returns {key: percentile_0_to_100_or_None}.
    """
    return _percentile_of_each(values, higher_is_better)


def sector_relative_rank(values, sectors, higher_is_better=True):
    """
    Rank every value against its OWN sector's peers on the screen.

    values  - list of (key, numeric_value_or_None)
    sectors - dict {key: sector_name}
    Returns {key: percentile_0_to_100_or_None}.

    If a stock's sector has fewer than MIN_SECTOR_PEERS members, that
    stock is ranked against the whole universe instead - too few peers
    to rank against meaningfully.
    """
    # group keys by sector
    by_sector = {}
    for key, _ in values:
        s = sectors.get(key, 'Unknown')
        by_sector.setdefault(s, []).append(key)

    value_of = dict(values)
    universe_rank = _percentile_of_each(values, higher_is_better)
    out = {}

    for sector, keys in by_sector.items():
        if len(keys) >= MIN_SECTOR_PEERS:
            sub = [(k, value_of[k]) for k in keys]
            sub_rank = _percentile_of_each(sub, higher_is_better)
            out.update(sub_rank)
        else:
            # too thin a sector - fall back to the universe rank
            for k in keys:
                out[k] = universe_rank[k]
    return out


def blended_rank(values, sectors, higher_is_better=True,
                 sector_weight=0.6):
    """
    A blend of sector-relative and whole-universe percentile.

    sector_weight - how much weight the sector-relative rank carries
                    (default 0.6). The remainder is the universe rank.

    Why blend rather than use sector-relative alone: pure sector
    ranking can crown the 'best of a bad sector'. Blending keeps the
    sector lens dominant while still respecting that some sectors are
    genuinely stronger than others.

    Returns {key: blended_percentile_0_to_100_or_None}.
    """
    uni = percentile_rank(values, higher_is_better)
    sec = sector_relative_rank(values, sectors, higher_is_better)
    out = {}
    for key, _ in values:
        u, s = uni.get(key), sec.get(key)
        if u is None and s is None:
            out[key] = None
        elif u is None:
            out[key] = s
        elif s is None:
            out[key] = u
        else:
            out[key] = round(sector_weight * s
                              + (1 - sector_weight) * u, 1)
    return out


# ---- self-test ----
if __name__ == '__main__':
    print('=' * 62)
    print('RANKING ENGINE - percentile & sector-relative - self-test')
    print('=' * 62)

    # PE values - lower is better
    pe = [('A', 5.0), ('B', 10.0), ('C', 15.0), ('D', 20.0),
          ('E', 25.0), ('F', None)]
    print('\nTest 1 - PE percentile (lower is better):')
    r = percentile_rank(pe, higher_is_better=False)
    for k, p in r.items():
        print(f'  {k}: PE rank {p}')

    # sector-relative: A,B,C are Metals (3 - too thin), D,E,F,G,H Pharma (5)
    vals = [('A', 5.0), ('B', 10.0), ('C', 15.0),
            ('D', 12.0), ('E', 14.0), ('F', 16.0), ('G', 18.0), ('H', 20.0)]
    secs = {'A': 'Metals', 'B': 'Metals', 'C': 'Metals',
            'D': 'Pharma', 'E': 'Pharma', 'F': 'Pharma',
            'G': 'Pharma', 'H': 'Pharma'}
    print('\nTest 2 - sector-relative PE rank (lower is better):')
    r = sector_relative_rank(vals, secs, higher_is_better=False)
    for k in sorted(r):
        peers = sum(1 for s in secs.values() if s == secs[k])
        note = '(thin sector -> universe rank)' if peers < 4 else \
               f'(ranked vs {peers} {secs[k]} peers)'
        print(f'  {k}: {secs[k]:8} rank {r[k]:5}  {note}')

    print('\nTest 3 - blended rank (60% sector, 40% universe):')
    r = blended_rank(vals, secs, higher_is_better=False)
    for k in sorted(r):
        print(f'  {k}: blended {r[k]}')

    print('\n' + '=' * 62)
    print('Ranking engine works. Scores are now RELATIVE to the screen')
    print('and to sector peers - they breathe with the universe.')
    print('=' * 62)
