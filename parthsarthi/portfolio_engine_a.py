"""
portfolio_engine_a.py
Parthsarthi Capital - Phase 5, Item 5.8
PORTFOLIO MASTER - ENGINE A LINKAGE.

The final Portfolio Master module. Engine A (the Director) reads
the macro regime and produces one number, 0-100. This module is the
single connection point that translates that number into commands
the whole portfolio obeys.

Engine A's score does two things, and this module makes both
explicit and consistent across B, C and D:

1. SETS THE EQUITY BUDGET
   The score maps to a regime band and an equity fraction; the
   capital allocator (5.1) then splits that budget 30/30/40. This
   module exposes the regime so every part of the system reads the
   same value.

2. SETS THE OPERATING GATE
   Beyond sizing, the score gates engine BEHAVIOUR:
     EXIT-ALL (score <= 20)  - close every equity position
     FREEZE   (score <= 30)  - keep holdings, allow NO new entries
     NORMAL   (score  > 30)  - engines operate normally

The gate must be applied identically by all three engines - a
freeze that only B obeys is not a freeze. This module is the one
place the gate is defined, so B, C and D cannot drift apart.

This module does not compute the Engine A score - Engine A does
that. It receives the score and broadcasts a consistent regime
instruction to the rest of the system.
"""

from reasoning_engine import Decision
from portfolio_capital import regime_for_score, allocate


# ---- operating-gate thresholds (consistent with the engine exit modules) ----
GATE_EXIT_ALL = 20      # score <= this -> close all equity positions
GATE_FREEZE   = 30      # score <= this -> no new entries, hold existing


def operating_gate(engine_a_score):
    """
    Translate the Engine A score into the portfolio-wide operating gate.
    Returns one of: 'EXIT-ALL', 'FREEZE', 'NORMAL'.
    """
    if engine_a_score is None:
        return 'NORMAL'
    if engine_a_score <= GATE_EXIT_ALL:
        return 'EXIT-ALL'
    if engine_a_score <= GATE_FREEZE:
        return 'FREEZE'
    return 'NORMAL'


def engine_a_directive(engine_a_score, total_portfolio):
    """
    The single Engine A directive the whole Portfolio Master obeys.

    Returns a Decision carrying:
      - the regime and equity budget (sizing side)
      - the operating gate (behaviour side)
      - the explicit per-engine instruction for this cycle

    Every engine reads THIS directive - none computes the gate itself.
    """
    regime, fraction = regime_for_score(engine_a_score)
    gate = operating_gate(engine_a_score)
    alloc = allocate(total_portfolio, engine_a_score)

    # per-engine instruction depends on the gate
    if gate == 'EXIT-ALL':
        instruction = ('CLOSE all equity positions across B, C and D. '
                       'Move to debt/gold (Engine E). No new entries.')
    elif gate == 'FREEZE':
        instruction = ('HOLD existing positions; manage exits normally. '
                       'NO new entries in B, C or D until the regime lifts.')
    else:
        instruction = ('Operate normally - entries, exits and rotation '
                        'all permitted within the engine budgets.')

    d = Decision('PM', 'ENGINE-A', f'DIRECTIVE-{gate}',
                 'Portfolio Master - Engine A Linkage')
    d.add_fact('Engine A score', str(engine_a_score))
    d.add_fact('Regime', f'{regime} ({fraction*100:.0f}% equity)')
    d.add_fact('Operating gate', gate)
    d.add_fact('Equity budget', f"{alloc['equity_budget']:,.0f}")
    d.add_fact('Engine budgets',
               f"B {alloc['engine_budgets']['B']:,.0f} | "
               f"C {alloc['engine_budgets']['C']:,.0f} | "
               f"D {alloc['engine_budgets']['D']:,.0f}")
    d.add_fact('Instruction to all engines', instruction)

    # margin = distance from the score to the nearest gate boundary
    if gate == 'NORMAL':
        d.set_margin('points above the FREEZE gate',
                     engine_a_score - GATE_FREEZE)
    elif gate == 'FREEZE':
        d.set_margin('points above the EXIT-ALL gate',
                     engine_a_score - GATE_EXIT_ALL)
    else:
        d.set_margin('points into EXIT-ALL territory',
                     GATE_EXIT_ALL - engine_a_score)

    d.set_counterfactual(
        f'-> FREEZE if the score falls to {GATE_FREEZE} or below; '
        f'-> EXIT-ALL at {GATE_EXIT_ALL} or below; the gate is applied '
        f'identically by B, C and D - none computes it independently')
    return d


def entries_permitted(engine_a_score):
    """Quick check: may engines open NEW positions this cycle?"""
    return operating_gate(engine_a_score) == 'NORMAL'


def must_liquidate(engine_a_score):
    """Quick check: must all equity positions be closed this cycle?"""
    return operating_gate(engine_a_score) == 'EXIT-ALL'


# ---- self-test ----
if __name__ == '__main__':
    print('=' * 64)
    print('PORTFOLIO MASTER - ENGINE A LINKAGE (5.8) - self-test')
    print('=' * 64)

    portfolio = 1000000

    # Test 1: operating gate across the score range
    print('\nTest 1 - operating gate by Engine A score:')
    for score in [85, 65, 50, 35, 28, 15]:
        gate = operating_gate(score)
        entries = entries_permitted(score)
        liq = must_liquidate(score)
        print(f'  A={score:3} -> gate {gate:9} '
              f'(new entries: {entries}, liquidate: {liq})')

    # Test 2: full directive - NORMAL regime
    print('\nTest 2 - Engine A directive, Active regime (score 55):')
    d = engine_a_directive(55, portfolio)
    print(f'  verdict: {d.verdict}')
    print(' ', d.reason_string())

    # Test 3: full directive - FREEZE regime
    print('\nTest 3 - Engine A directive, FREEZE regime (score 28):')
    d = engine_a_directive(28, portfolio)
    print(f'  verdict: {d.verdict}')
    print(' ', d.reason_string())

    # Test 4: full directive - EXIT-ALL regime
    print('\nTest 4 - Engine A directive, EXIT-ALL regime (score 15):')
    d = engine_a_directive(15, portfolio)
    print(f'  verdict: {d.verdict}')
    print(' ', d.reason_string())

    # Test 5: boundary - exactly at the FREEZE gate
    print('\nTest 5 - boundary check (score exactly 30):')
    print(f'  score 30 -> gate {operating_gate(30)}')
    print(f'  score 31 -> gate {operating_gate(31)}')
    print(f'  score 20 -> gate {operating_gate(20)}')
    print(f'  score 21 -> gate {operating_gate(21)}')

    print('\n' + '=' * 64)
    print('Self-test complete. Engine A linkage broadcasts ONE regime')
    print('directive - equity budget plus operating gate - that B, C')
    print('and D all obey identically. Phase 5 modules now connect.')
    print('=' * 64)
