"""
engine_d_thesis.py
Parthsarthi Capital - Phase 4, Item 4.4
ENGINE D - THESIS-BREAK MONITOR (Module 4).

Engine D has ONE exit path: the thesis break. There is no
profit-booking exit. A compounder is sold only when the business
that made it a compounder stops being one. Booking a compounder
early is the classic wealth-destroying mistake.

Seven triggers. Any one fires a full EXIT:
  1. Growth Collapse     - Net Profit 3Yr Growth below 10%   (soft)
  2. Quality Collapse    - Piotroski Score below 5            (soft)
  3. Profitability Break - ROE below 12%                      (soft)
  4. Debt Blowout        - D/E above 1.5                      (soft)
  5. Valuation Bubble    - PEG above 3.0                      (hard)
  6. Hard Stop           - price -30% from entry              (hard)
  7. Engine A Gate       - Engine A score <= 20               (hard)

TIER INTERACTION (from Module 3):
  - SOFT triggers (1-4): for IMMORTAL / LEGENDARY positions they
    must persist across TWO consecutive screen readings before
    firing. For LEGENDARY, soft drift is not monitored at all.
    For SEEDLING / ESTABLISHED they fire on first occurrence.
  - HARD triggers (5-7): fire immediately, regardless of tier.

Trigger 5, the Valuation Bubble, is important: Engine D never books
profit on the way up, but it WILL exit a wildly overvalued stock.
Letting a fairly-priced compounder run is discipline; refusing to
exit a bubble is negligence. PEG > 3.0 is the line.

There is NO dead-money timer - a quiet compounder with growing
fundamentals is still compounding. Time is the compounder's ally.
"""

from reasoning_engine import Decision
from engine_d_tiers import (tier_for_months, soft_trigger_threshold,
                            soft_drift_monitored, LEGENDARY)


# ---- locked thresholds (Engine D framework) ----
GROWTH_3Y_FLOOR = 10.0     # below this -> Growth Collapse (soft)
PIOTROSKI_FLOOR = 5        # below this -> Quality Collapse (soft)
ROE_FLOOR       = 12.0     # below this -> Profitability Break (soft)
DE_CEILING      = 1.5      # above this -> Debt Blowout (soft)
PEG_BUBBLE      = 3.0      # above this -> Valuation Bubble (hard)
HARD_STOP_PCT   = 30.0     # price fall from entry -> Hard Stop (hard)
ENGINE_A_EXIT   = 20       # Engine A score <= this -> Engine A Gate (hard)

SOFT_TRIGGERS = {'Growth Collapse', 'Quality Collapse',
                 'Profitability Break', 'Debt Blowout'}
HARD_TRIGGERS = {'Valuation Bubble', 'Hard Stop', 'Engine A Gate'}


def check_thesis(ticker, entry_price, current_price,
                 growth_3y, piotroski, roe, debt_equity, peg,
                 engine_a_score, months_held=0,
                 soft_breach_streak=None):
    """
    Check an open Engine D position against all seven triggers,
    applying tier-aware logic to the soft triggers.

    soft_breach_streak - dict {trigger_name: consecutive_readings_breached}
                         tracking how many consecutive screens each soft
                         trigger has been breached. Needed for the
                         IMMORTAL/LEGENDARY 2-reading rule.

    Returns a Decision: 'EXIT' if any trigger fires (after tier logic),
    or 'HOLD' if the position survives.
    """
    soft_breach_streak = dict(soft_breach_streak or {})
    tier = tier_for_months(months_held)
    readings_needed = soft_trigger_threshold(tier)
    monitor_soft = soft_drift_monitored(tier)

    drawdown_pct = 0.0
    if entry_price and entry_price > 0:
        drawdown_pct = (entry_price - current_price) / entry_price * 100.0

    # ---- detect raw breaches ----
    soft_breached = []   # (name, detail)
    hard_breached = []   # (name, detail)

    if growth_3y is not None and growth_3y < GROWTH_3Y_FLOOR:
        soft_breached.append(('Growth Collapse',
                              f'3Yr profit growth {growth_3y:.1f}% < {GROWTH_3Y_FLOOR}%'))
    if piotroski is not None and piotroski < PIOTROSKI_FLOOR:
        soft_breached.append(('Quality Collapse',
                              f'Piotroski {piotroski:.0f} < {PIOTROSKI_FLOOR}'))
    if roe is not None and roe < ROE_FLOOR:
        soft_breached.append(('Profitability Break',
                              f'ROE {roe:.1f}% < {ROE_FLOOR}%'))
    if debt_equity is not None and debt_equity > DE_CEILING:
        soft_breached.append(('Debt Blowout',
                              f'D/E {debt_equity:.2f} > {DE_CEILING}'))

    if peg is not None and peg > PEG_BUBBLE:
        hard_breached.append(('Valuation Bubble',
                              f'PEG {peg:.2f} > {PEG_BUBBLE} - growth no '
                              f'longer reasonably priced'))
    if drawdown_pct >= HARD_STOP_PCT:
        hard_breached.append(('Hard Stop',
                              f'price {current_price:.1f} is {drawdown_pct:.1f}% '
                              f'below entry, threshold {HARD_STOP_PCT}%'))
    if engine_a_score is not None and engine_a_score <= ENGINE_A_EXIT:
        hard_breached.append(('Engine A Gate',
                              f'Engine A score {engine_a_score} <= {ENGINE_A_EXIT}'))

    # ---- apply tier logic to soft triggers ----
    fired = list(hard_breached)        # hard triggers always fire
    new_streak = {}

    if monitor_soft:
        for name, detail in soft_breached:
            streak = soft_breach_streak.get(name, 0) + 1
            new_streak[name] = streak
            if streak >= readings_needed:
                fired.append((name, f'{detail} '
                              f'[{streak}/{readings_needed} consecutive readings]'))
            # else: breached but not yet enough readings - armed, not fired
    # if not monitor_soft (LEGENDARY), soft breaches are ignored entirely

    # ---- build the decision ----
    if fired:
        primary = fired[0][0]
        d = Decision('D', ticker, 'EXIT', f'Module 4 - {primary}')
        d.add_fact('Tier', tier)
        for name, detail in fired:
            d.add_fact(name, detail)
        d.add_fact('Triggers fired', str(len(fired)))
        d.set_margin('thesis-break triggers fired', len(fired))
        d.set_counterfactual(
            'a thesis-break exit is absolute and final - Engine D never '
            'books profit, so this is the only way a position closes')
        return d

    # ---- survives -> HOLD ----
    d = Decision('D', ticker, 'HOLD', 'Module 4 - Thesis Check (all clear)')
    d.add_fact('Tier', tier)
    d.add_fact('3Yr growth', f'{growth_3y:.1f}%' if growth_3y is not None else 'n/a')
    d.add_fact('Piotroski', f'{piotroski:.0f}' if piotroski is not None else 'n/a')
    d.add_fact('ROE', f'{roe:.1f}%' if roe is not None else 'n/a')
    d.add_fact('PEG', f'{peg:.2f}' if peg is not None else 'n/a')
    d.add_fact('Drawdown from entry', f'{drawdown_pct:.1f}%')

    # note any armed-but-not-fired soft breaches (IMMORTAL+ grace)
    if monitor_soft and soft_breached and new_streak:
        armed = [n for n in new_streak if new_streak[n] < readings_needed]
        if armed:
            d.add_fact('Armed soft triggers',
                       f"{', '.join(armed)} - breached but awaiting a "
                       f"{readings_needed}th consecutive reading")

    # margin = distance to the nearest hard trigger
    margins = [('drawdown room to hard stop', HARD_STOP_PCT - drawdown_pct)]
    if peg is not None:
        margins.append(('PEG room to bubble', PEG_BUBBLE - peg))
    nearest = min(margins, key=lambda m: m[1])
    d.set_margin(nearest[0], round(nearest[1], 2))
    d.set_counterfactual(
        f'-> EXIT on any hard trigger (PEG > {PEG_BUBBLE}, price -'
        f'{HARD_STOP_PCT}%, Engine A <= {ENGINE_A_EXIT}); soft triggers '
        f'(growth/quality/ROE/debt) need {readings_needed} reading(s) at '
        f'tier {tier}' +
        ('' if monitor_soft else ' - soft drift not monitored at LEGENDARY'))
    return d


# ---- self-test ----
if __name__ == '__main__':
    print('=' * 66)
    print('ENGINE D THESIS-BREAK MONITOR (Module 4) - self-test')
    print('=' * 66)

    base = dict(entry_price=100, current_price=120, growth_3y=30,
                piotroski=8, roe=28, debt_equity=0.4, peg=0.8,
                engine_a_score=55)

    # Test 1: healthy compounder -> HOLD
    print('\nTest 1 - healthy compounder, SEEDLING (held 6 months):')
    d = check_thesis('HINDZINC', months_held=6, **base)
    print(f'  verdict: {d.verdict}')
    print(' ', d.reason_string())

    # Test 2: hard trigger - PEG bubble - fires immediately, any tier
    print('\nTest 2 - Valuation Bubble (PEG 3.5), LEGENDARY position:')
    b2 = dict(base); b2['peg'] = 3.5
    d = check_thesis('TITAN', months_held=60, **b2)
    print(f'  verdict: {d.verdict}')
    print(' ', d.reason_string())

    # Test 3: soft trigger on a SEEDLING - fires on first reading
    print('\nTest 3 - Quality Collapse (Piotroski 4), SEEDLING:')
    b3 = dict(base); b3['piotroski'] = 4
    d = check_thesis('GVPIL', months_held=8, **b3)
    print(f'  verdict: {d.verdict}')
    print(' ', d.reason_string())

    # Test 4: soft trigger on an IMMORTAL - first reading, armed not fired
    print('\nTest 4 - Quality Collapse (Piotroski 4), IMMORTAL, 1st reading:')
    b4 = dict(base); b4['piotroski'] = 4
    d = check_thesis('LUPIN', months_held=30, soft_breach_streak={}, **b4)
    print(f'  verdict: {d.verdict}  (armed, not yet fired)')
    print(' ', d.reason_string())

    # Test 5: soft trigger on an IMMORTAL - 2nd consecutive reading -> fires
    print('\nTest 5 - Quality Collapse, IMMORTAL, 2nd consecutive reading:')
    d = check_thesis('LUPIN', months_held=30,
                     soft_breach_streak={'Quality Collapse': 1}, **b4)
    print(f'  verdict: {d.verdict}  (2nd reading - now fires)')
    print(' ', d.reason_string())

    # Test 6: soft trigger on a LEGENDARY - ignored entirely
    print('\nTest 6 - Quality Collapse (Piotroski 4), LEGENDARY (soft ignored):')
    d = check_thesis('TITAN', months_held=60,
                     soft_breach_streak={'Quality Collapse': 5}, **b4)
    print(f'  verdict: {d.verdict}  (LEGENDARY ignores soft drift)')

    # Test 7: hard stop -32%
    print('\nTest 7 - Hard Stop (price down 32%):')
    b7 = dict(base); b7['current_price'] = 68
    d = check_thesis('FORCEMOT', months_held=15, **b7)
    print(f'  verdict: {d.verdict}')

    print('\n' + '=' * 66)
    print('Self-test complete. Hard triggers fire immediately at any tier;')
    print('soft triggers need 2 readings for IMMORTAL and are ignored for')
    print('LEGENDARY. Engine D never books profit - thesis-break is the')
    print('only exit. There is no dead-money timer.')
    print('=' * 66)
