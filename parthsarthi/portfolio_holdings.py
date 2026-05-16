"""
portfolio_holdings.py
Parthsarthi Capital - Phase 5, Item 5.5
PORTFOLIO MASTER - HOLDINGS CEILING & PORTFOLIO SECTOR CAP.

Two portfolio-wide limits, both measured across B + C + D combined.

1. THE HOLDINGS CEILING
   Each engine caps at 10 positions - so the arithmetic maximum is
   30 names. But 30 is more than a one-person operation can monitor
   well. The Portfolio Master sets:
       Target  : a focused book of 15-25 quality positions
       Hard max: 30 positions across all engines
   At/over the target the system warns; at the hard max it blocks
   any new entry until a slot frees up.

2. THE PORTFOLIO SECTOR CAP
   Each engine has its own 30% sector cap. But three engines could
   each be 30% in Metals and the WHOLE portfolio would then be 30%
   Metals with no single engine breaching its own cap. The Portfolio
   Master enforces a 30% sector cap on the COMBINED book.

This module is consulted before every new entry. It does not pick
stocks; it tells the engines whether the portfolio has room.
"""

from reasoning_engine import Decision


# ---- holdings ceiling ----
HOLDINGS_TARGET_LOW  = 15      # focused-book target, lower bound
HOLDINGS_TARGET_HIGH = 25      # focused-book target, upper bound
HOLDINGS_HARD_MAX    = 30      # absolute ceiling across all engines

# ---- portfolio-wide sector cap ----
SECTOR_CAP_PCT = 30.0


def portfolio_sector_exposure(positions):
    """
    {sector: pct} across the COMBINED book (all engines).
    positions - list of {ticker, engine, sector, current_value}
    Exposure is value-weighted.
    """
    total = sum(p.get('current_value', 0) for p in positions)
    if total <= 0:
        return {}
    by_sector = {}
    for p in positions:
        s = p.get('sector', 'Unknown')
        by_sector[s] = by_sector.get(s, 0) + p.get('current_value', 0)
    return {s: v / total * 100.0 for s, v in by_sector.items()}


def check_capacity(new_sector, new_value, positions):
    """
    Check whether the portfolio has room for one more position.

    new_sector - the sector of the candidate stock
    new_value  - the rupee value of the proposed new position
    positions  - current positions across all engines

    Returns a Decision:
      ROOM-OK        - within target band; entry permitted
      ROOM-WARN      - in or above the target band but below hard max;
                       entry permitted, focus warning raised
      ROOM-FULL      - at the hard max; no new entry until a slot frees
      SECTOR-BREACH  - the new position would push its sector above
                       the 30% portfolio cap; entry blocked
    """
    n_held = len(positions)

    # ---- holdings ceiling check ----
    if n_held >= HOLDINGS_HARD_MAX:
        d = Decision('PM', 'PORTFOLIO', 'ROOM-FULL',
                     'Portfolio Master - Holdings Ceiling (full)')
        d.add_fact('Current holdings', f'{n_held}/{HOLDINGS_HARD_MAX}')
        d.add_fact('Decision', 'at the hard maximum - no new entry until '
                               'a slot frees up')
        d.set_margin('positions over the target band',
                     n_held - HOLDINGS_TARGET_HIGH)
        d.set_counterfactual(f'-> ROOM-OK once holdings fall back within '
                              f'the {HOLDINGS_TARGET_LOW}-'
                              f'{HOLDINGS_TARGET_HIGH} target band')
        return d

    # ---- portfolio sector cap check ----
    total_after = sum(p.get('current_value', 0) for p in positions) + new_value
    sector_now = sum(p.get('current_value', 0) for p in positions
                     if p.get('sector') == new_sector)
    sector_after = sector_now + new_value
    sector_after_pct = (sector_after / total_after * 100.0
                        if total_after > 0 else 0.0)

    if sector_after_pct > SECTOR_CAP_PCT:
        d = Decision('PM', 'PORTFOLIO', 'SECTOR-BREACH',
                     'Portfolio Master - Sector Cap (breach)')
        d.add_fact('Candidate sector', new_sector)
        d.add_fact('Sector after entry',
                   f'{sector_after_pct:.1f}% (cap {SECTOR_CAP_PCT:.0f}%)')
        d.add_fact('Decision', f'entry blocked - would push {new_sector} '
                               f'above the {SECTOR_CAP_PCT:.0f}% portfolio cap')
        d.set_margin('percent over the sector cap',
                     round(sector_after_pct - SECTOR_CAP_PCT, 1))
        d.set_counterfactual(
            f'-> entry permitted if {new_sector} exposure stays at or '
            f'below {SECTOR_CAP_PCT:.0f}% of the combined book')
        return d

    # ---- holdings within or above target band ----
    if n_held >= HOLDINGS_TARGET_HIGH:
        d = Decision('PM', 'PORTFOLIO', 'ROOM-WARN',
                     'Portfolio Master - Holdings Ceiling (focus warning)')
        d.add_fact('Current holdings', f'{n_held}/{HOLDINGS_HARD_MAX}')
        d.add_fact('Target band', f'{HOLDINGS_TARGET_LOW}-{HOLDINGS_TARGET_HIGH}')
        d.add_fact('Warning', 'above the focused-book target - each extra '
                              'name dilutes attention')
        d.add_fact('Candidate sector', f'{new_sector} '
                   f'-> {sector_after_pct:.1f}% after entry (OK)')
        d.set_margin('positions to the hard max', HOLDINGS_HARD_MAX - n_held)
        d.set_counterfactual(
            'entry is permitted but the book is above its focused target; '
            'prefer rotation over adding names')
        return d

    # ---- comfortable: within the target band ----
    d = Decision('PM', 'PORTFOLIO', 'ROOM-OK',
                 'Portfolio Master - Holdings Ceiling')
    d.add_fact('Current holdings', f'{n_held}/{HOLDINGS_HARD_MAX}')
    d.add_fact('Target band', f'{HOLDINGS_TARGET_LOW}-{HOLDINGS_TARGET_HIGH}')
    d.add_fact('Candidate sector', f'{new_sector} '
               f'-> {sector_after_pct:.1f}% after entry')
    d.set_margin('positions of room within the target band',
                 max(0, HOLDINGS_TARGET_HIGH - n_held))
    d.set_counterfactual(
        f'-> ROOM-WARN above {HOLDINGS_TARGET_HIGH} holdings; '
        f'-> SECTOR-BREACH if the sector would exceed '
        f'{SECTOR_CAP_PCT:.0f}% of the book')
    return d


# ---- self-test ----
if __name__ == '__main__':
    print('=' * 64)
    print('PORTFOLIO MASTER - HOLDINGS CEILING & SECTOR CAP (5.5) - self-test')
    print('=' * 64)

    def book(n, sector='Mixed', value=20000):
        """Build n dummy positions."""
        return [{'ticker': f'STK{i}', 'engine': 'BCD'[i % 3],
                 'sector': sector if i == 0 else f'Sector{i%6}',
                 'current_value': value} for i in range(n)]

    # Test 1: comfortable book of 12 -> ROOM-OK
    print('\nTest 1 - book of 12 positions, new entry:')
    d = check_capacity('IT', 20000, book(12))
    print(f'  verdict: {d.verdict}')
    print(' ', d.reason_string())

    # Test 2: book of 27 -> ROOM-WARN (above target, below hard max)
    print('\nTest 2 - book of 27 positions, new entry:')
    d = check_capacity('IT', 20000, book(27))
    print(f'  verdict: {d.verdict}')
    print(' ', d.reason_string())

    # Test 3: book of 30 -> ROOM-FULL
    print('\nTest 3 - book of 30 positions (hard max), new entry:')
    d = check_capacity('IT', 20000, book(30))
    print(f'  verdict: {d.verdict}')
    print(' ', d.reason_string())

    # Test 4: portfolio sector cap breach
    print('\nTest 4 - portfolio already 28% Metals, big Metals entry:')
    positions = ([{'ticker': f'M{i}', 'engine': 'D', 'sector': 'Metals',
                   'current_value': 20000} for i in range(4)] +
                 [{'ticker': f'X{i}', 'engine': 'C', 'sector': f'S{i}',
                   'current_value': 20000} for i in range(6)])
    # 4 Metals * 20k = 80k of 200k = 40% already; add more Metals
    d = check_capacity('Metals', 30000, positions)
    print(f'  verdict: {d.verdict}')
    print(' ', d.reason_string())

    # Test 5: same book, a non-Metals entry -> OK
    print('\nTest 5 - same book, an IT entry instead:')
    d = check_capacity('IT', 20000, positions)
    print(f'  verdict: {d.verdict}')

    print('\n' + '=' * 64)
    print('Self-test complete. The holdings ceiling targets a focused')
    print('15-25 book (30 hard max) and the sector cap holds any sector')
    print('to 30% of the COMBINED B+C+D portfolio.')
    print('=' * 64)
