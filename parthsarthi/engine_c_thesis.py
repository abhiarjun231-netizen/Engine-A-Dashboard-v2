"""
engine_c_thesis.py
Parthsarthi Capital - Phase 3, Item 3.4
ENGINE C - THESIS-BREAK MONITOR (Module 2B, Path B).

Engine C has two exit paths. Path A (item 3.3) is the planned
harvest - PE-expansion booking. Path B is this module: the safety net.

A value trap is a cheap stock that STAYS cheap because the business
is quietly rotting. PE-expansion booking never fires on a trap - so
without a safety net, capital sits dead forever. Path B catches it.

Any one of these triggers fires a full EXIT:
  1. Quality Collapse    - Piotroski Score below 5
  2. Profitability Break - ROE below 12% (was >15% at entry)
  3. Debt Blowout        - D/E above 1.5
  4. Hard Stop           - price -25% from entry
  5. Engine A Gate       - Engine A score <= 20 (exit all)
  6. Dead Money          - held 18 months with no PE-booking ever
                           triggered

The Dead-Money rule is the value-trap timer. If 18 months pass and
the market has not begun to re-rate the stock at all, the thesis has
failed regardless of whether the business metrics broke.

This module checks an open position against all six Path B triggers
and returns an EXIT decision if any fires, or HOLD if it survives.
"""

from reasoning_engine import Decision


# ---- locked Path B thresholds (Engine C framework) ----
PIOTROSKI_FLOOR = 5        # below this -> Quality Collapse
ROE_FLOOR       = 12.0     # below this -> Profitability Break
DE_CEILING      = 1.5      # above this -> Debt Blowout
HARD_STOP_PCT   = 25.0     # price fall from entry -> Hard Stop
ENGINE_A_EXIT   = 20       # Engine A score <= this -> exit all
DEAD_MONEY_MONTHS = 18     # months held with no booking -> Dead Money


def check_thesis(ticker, entry_price, current_price,
                 piotroski, roe, debt_equity,
                 engine_a_score, months_held=0, booking_triggered=False):
    """
    Check an open Engine C position against all six Path B triggers.

    booking_triggered - True if ANY PE-expansion tranche has ever fired.
                        If True, the Dead-Money timer does not apply -
                        the stock has demonstrably begun re-rating.

    Returns a Decision: 'EXIT' if any trigger fired (rule names it),
    or 'HOLD' if the position survives all six.
    """
    triggers = []
    drawdown_pct = 0.0
    if entry_price and entry_price > 0:
        drawdown_pct = (entry_price - current_price) / entry_price * 100.0

    # ---- Trigger 1: Quality Collapse ----
    if piotroski is not None and piotroski < PIOTROSKI_FLOOR:
        triggers.append(('Quality Collapse',
                          f'Piotroski {piotroski:.0f} < {PIOTROSKI_FLOOR}'))

    # ---- Trigger 2: Profitability Break ----
    if roe is not None and roe < ROE_FLOOR:
        triggers.append(('Profitability Break',
                          f'ROE {roe:.1f}% < {ROE_FLOOR}%'))

    # ---- Trigger 3: Debt Blowout ----
    if debt_equity is not None and debt_equity > DE_CEILING:
        triggers.append(('Debt Blowout',
                          f'D/E {debt_equity:.2f} > {DE_CEILING}'))

    # ---- Trigger 4: Hard Stop ----
    if drawdown_pct >= HARD_STOP_PCT:
        triggers.append(('Hard Stop',
                          f'price {current_price:.1f} is {drawdown_pct:.1f}% '
                          f'below entry {entry_price:.1f}, '
                          f'threshold {HARD_STOP_PCT}%'))

    # ---- Trigger 5: Engine A Gate ----
    if engine_a_score is not None and engine_a_score <= ENGINE_A_EXIT:
        triggers.append(('Engine A Gate',
                          f'Engine A score {engine_a_score} <= {ENGINE_A_EXIT}'))

    # ---- Trigger 6: Dead Money ----
    if (not booking_triggered and months_held >= DEAD_MONEY_MONTHS):
        triggers.append(('Dead Money',
                          f'held {months_held} months with no PE-booking '
                          f'ever triggered (threshold {DEAD_MONEY_MONTHS})'))

    # ---- build the decision ----
    if triggers:
        primary = triggers[0][0]
        d = Decision('C', ticker, 'EXIT', f'Module 2B - {primary}')
        for name, detail in triggers:
            d.add_fact(name, detail)
        d.add_fact('Triggers fired', str(len(triggers)))
        d.set_margin('Path B triggers fired', len(triggers))
        d.set_counterfactual(
            'a thesis-break exit is absolute - the position closes fully; '
            'it is a separate path from PE-expansion booking')
        return d

    # ---- survives all six -> HOLD ----
    d = Decision('C', ticker, 'HOLD', 'Module 2B - Thesis Check (all clear)')
    d.add_fact('Piotroski', f'{piotroski:.0f}' if piotroski is not None else 'n/a')
    d.add_fact('ROE', f'{roe:.1f}%' if roe is not None else 'n/a')
    d.add_fact('D/E', f'{debt_equity:.2f}' if debt_equity is not None else 'n/a')
    d.add_fact('Drawdown from entry', f'{drawdown_pct:.1f}%')
    d.add_fact('Months held', str(months_held))

    # margin = distance to the nearest trigger
    margins = []
    if piotroski is not None:
        margins.append(('Piotroski above floor', piotroski - PIOTROSKI_FLOOR))
    if roe is not None:
        margins.append(('ROE above floor', roe - ROE_FLOOR))
    margins.append(('drawdown room to hard stop', HARD_STOP_PCT - drawdown_pct))
    if not booking_triggered:
        margins.append(('months to dead-money timer',
                         DEAD_MONEY_MONTHS - months_held))
    nearest = min(margins, key=lambda m: m[1])
    d.set_margin(nearest[0], round(nearest[1], 1))
    d.set_counterfactual(
        f'-> EXIT if Piotroski < {PIOTROSKI_FLOOR} OR ROE < {ROE_FLOOR}% '
        f'OR D/E > {DE_CEILING} OR price falls {HARD_STOP_PCT}% from entry '
        f'OR Engine A <= {ENGINE_A_EXIT} OR {DEAD_MONEY_MONTHS} months '
        f'with no booking')
    return d


# ---- self-test ----
if __name__ == '__main__':
    print('=' * 64)
    print('ENGINE C THESIS-BREAK MONITOR (Module 2B / Path B) - self-test')
    print('=' * 64)

    # Test 1: healthy value position -> HOLD
    print('\nTest 1 - healthy position (Piotroski 7, ROE 18%, D/E 0.4):')
    d = check_thesis('PTC', entry_price=100, current_price=108,
                     piotroski=7, roe=18, debt_equity=0.4,
                     engine_a_score=55, months_held=5)
    print(f'  verdict: {d.verdict}')
    print(' ', d.reason_string())

    # Test 2: Quality Collapse - Piotroski below 5
    print('\nTest 2 - Quality Collapse (Piotroski 4):')
    d = check_thesis('JSWSTEEL', entry_price=100, current_price=102,
                     piotroski=4, roe=16, debt_equity=0.6,
                     engine_a_score=55, months_held=8)
    print(f'  verdict: {d.verdict}')
    print(' ', d.reason_string())

    # Test 3: Profitability Break - ROE below 12%
    print('\nTest 3 - Profitability Break (ROE 9%):')
    d = check_thesis('SHARDACROP', entry_price=100, current_price=95,
                     piotroski=6, roe=9, debt_equity=0.5,
                     engine_a_score=55, months_held=10)
    print(f'  verdict: {d.verdict}')
    print(' ', d.reason_string())

    # Test 4: Hard Stop - down 28% from entry
    print('\nTest 4 - Hard Stop (price down 28%):')
    d = check_thesis('HINDZINC', entry_price=100, current_price=72,
                     piotroski=7, roe=15, debt_equity=0.7,
                     engine_a_score=55, months_held=6)
    print(f'  verdict: {d.verdict}')
    print(' ', d.reason_string())

    # Test 5: Dead Money - 18 months, no booking ever
    print('\nTest 5 - Dead Money (held 19 months, no booking):')
    d = check_thesis('GESHIP', entry_price=100, current_price=103,
                     piotroski=7, roe=16, debt_equity=0.5,
                     engine_a_score=55, months_held=19,
                     booking_triggered=False)
    print(f'  verdict: {d.verdict}')
    print(' ', d.reason_string())

    # Test 6: 19 months held BUT booking has triggered -> no dead money
    print('\nTest 6 - 19 months held but PE-booking already triggered:')
    d = check_thesis('FORCEMOT', entry_price=100, current_price=140,
                     piotroski=7, roe=20, debt_equity=0.4,
                     engine_a_score=55, months_held=19,
                     booking_triggered=True)
    print(f'  verdict: {d.verdict}  (dead-money timer does not apply)')

    # Test 7: multiple triggers
    print('\nTest 7 - multiple triggers (Quality + Debt + Hard Stop):')
    d = check_thesis('TRAPCO', entry_price=100, current_price=70,
                     piotroski=3, roe=14, debt_equity=2.1,
                     engine_a_score=55, months_held=12)
    print(f'  verdict: {d.verdict}  ({d.facts[-1][1]} triggers)')

    print('\n' + '=' * 64)
    print('Self-test complete. Path B catches value traps - any one of')
    print('six triggers forces a full EXIT. The dead-money timer is')
    print('waived once PE-expansion booking has begun.')
    print('=' * 64)
