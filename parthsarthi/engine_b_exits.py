"""
engine_b_exits.py
Parthsarthi Capital - Phase 2, Item 2.4
ENGINE B - EXIT TRIGGERS (Module 3).

Four exit triggers. ANY ONE firing closes the position immediately.
These override every other consideration, including profit stage.

  1. DVM Decay     - Momentum < 49 OR Durability < 45
  2. Velocity Crash- Momentum falls 15+ points week-on-week
  3. Hard Stop     - price -15% from the position's peak
  4. Engine A Gate - Engine A score <= 20 (exit all)
                     or <= 30 (freeze - no new entries, holds kept)

This module checks an open position against all four triggers and
returns an EXIT decision (with reason string) if any fires, or a
HOLD decision if the position survives all four.

It does NOT decide RIDE vs GUARD - that is the lifecycle module (2.2).
It does NOT manage trailing profit stops - that is module 2.5.
This module answers one question: "must this position be closed now?"
"""

from reasoning_engine import Decision


# ---- locked exit thresholds (Engine B framework) ----
DVM_MOMENTUM_FLOOR   = 49     # Momentum below this -> DVM Decay
DVM_DURABILITY_FLOOR = 45     # Durability below this -> DVM Decay
VELOCITY_CRASH_DROP  = 15     # week-on-week Momentum drop that triggers
HARD_STOP_PCT        = 15.0   # % fall from peak that triggers
ENGINE_A_EXIT        = 20     # Engine A score <= this -> exit all
ENGINE_A_FREEZE      = 30     # Engine A score <= this -> freeze (no adds)


def check_exit(ticker, durability, momentum, momentum_last_week,
               current_price, peak_price, engine_a_score):
    """
    Check an open Engine B position against all four exit triggers.

    Returns a Decision:
      verdict 'EXIT'  if any trigger fired (rule names the trigger)
      verdict 'HOLD'  if the position survives all four

    momentum_last_week - the Momentum score at the previous weekly
                         reading, for the velocity-crash check. Pass
                         None if there is no prior reading yet.
    """
    triggers = []   # list of (name, detail) for every trigger that fired

    # ---- Trigger 1: DVM Decay ----
    if momentum is not None and momentum < DVM_MOMENTUM_FLOOR:
        triggers.append(('DVM Decay',
                          f'Momentum {momentum:.0f} < {DVM_MOMENTUM_FLOOR}'))
    elif durability is not None and durability < DVM_DURABILITY_FLOOR:
        triggers.append(('DVM Decay',
                          f'Durability {durability:.0f} < {DVM_DURABILITY_FLOOR}'))

    # ---- Trigger 2: Velocity Crash ----
    if momentum is not None and momentum_last_week is not None:
        drop = momentum_last_week - momentum
        if drop >= VELOCITY_CRASH_DROP:
            triggers.append(('Velocity Crash',
                             f'Momentum fell {drop:.0f} pts week-on-week '
                             f'({momentum_last_week:.0f} -> {momentum:.0f}), '
                             f'threshold {VELOCITY_CRASH_DROP}'))

    # ---- Trigger 3: Hard Stop ----
    drawdown_pct = 0.0
    if peak_price and peak_price > 0:
        drawdown_pct = (peak_price - current_price) / peak_price * 100.0
        if drawdown_pct >= HARD_STOP_PCT:
            triggers.append(('Hard Stop',
                             f'price {current_price:.1f} is {drawdown_pct:.1f}% '
                             f'below peak {peak_price:.1f}, '
                             f'threshold {HARD_STOP_PCT}%'))

    # ---- Trigger 4: Engine A Gate ----
    if engine_a_score is not None and engine_a_score <= ENGINE_A_EXIT:
        triggers.append(('Engine A Gate',
                          f'Engine A score {engine_a_score} <= {ENGINE_A_EXIT} '
                          f'- regime exit-all'))

    # ---- build the decision ----
    if triggers:
        # if several fired, the decision names all of them; the first
        # is the primary rule
        primary = triggers[0][0]
        d = Decision('B', ticker, 'EXIT', f'Module 3 - {primary}')
        for name, detail in triggers:
            d.add_fact(name, detail)
        d.add_fact('Triggers fired', str(len(triggers)))
        # margin = how far past the threshold the worst trigger is
        d.set_margin('exit triggers fired', len(triggers))
        d.set_counterfactual(
            'would HOLD only if every listed trigger reversed - '
            'an exit trigger is absolute, it is not overridden by profit')
        return d

    # ---- survives all four -> HOLD ----
    d = Decision('B', ticker, 'HOLD', 'Module 3 - Exit Check (all clear)')
    d.add_fact('Momentum', f'{momentum:.0f}' if momentum is not None else 'n/a')
    d.add_fact('Durability', f'{durability:.0f}' if durability is not None else 'n/a')
    d.add_fact('Drawdown from peak', f'{drawdown_pct:.1f}%')
    d.add_fact('Engine A score', str(engine_a_score) if engine_a_score is not None else 'n/a')

    # margin = distance to the NEAREST trigger
    margins = []
    if momentum is not None:
        margins.append(('Momentum to DVM floor', momentum - DVM_MOMENTUM_FLOOR))
    if durability is not None:
        margins.append(('Durability to DVM floor', durability - DVM_DURABILITY_FLOOR))
    margins.append(('drawdown room to hard stop', HARD_STOP_PCT - drawdown_pct))
    nearest = min(margins, key=lambda m: m[1])
    d.set_margin(nearest[0], round(nearest[1], 1))
    d.set_counterfactual(
        f'-> EXIT if Momentum < {DVM_MOMENTUM_FLOOR} OR Durability < '
        f'{DVM_DURABILITY_FLOOR} OR price falls {HARD_STOP_PCT}% from peak '
        f'OR a 15-pt weekly Momentum crash OR Engine A score <= {ENGINE_A_EXIT}')
    return d


def engine_a_regime(engine_a_score):
    """
    Translate the Engine A score into the gate state for Engine B:
      EXIT-ALL  - close every position
      FREEZE    - keep holdings, allow no new entries
      NORMAL    - operate normally
    """
    if engine_a_score is None:
        return 'NORMAL'
    if engine_a_score <= ENGINE_A_EXIT:
        return 'EXIT-ALL'
    if engine_a_score <= ENGINE_A_FREEZE:
        return 'FREEZE'
    return 'NORMAL'


# ---- self-test ----
if __name__ == '__main__':
    print('=' * 64)
    print('ENGINE B EXIT TRIGGERS (Module 3) - self-test')
    print('=' * 64)

    # Test 1: healthy position - should HOLD
    print('\nTest 1 - healthy position (M 65, D 70, -4% from peak):')
    d = check_exit('TATASTEEL', durability=70, momentum=65,
                   momentum_last_week=63, current_price=144,
                   peak_price=150, engine_a_score=55)
    print(f'  verdict: {d.verdict}')
    print(' ', d.reason_string())

    # Test 2: DVM decay - Momentum below floor
    print('\nTest 2 - DVM Decay (Momentum 44):')
    d = check_exit('JSWSTEEL', durability=60, momentum=44,
                   momentum_last_week=50, current_price=880,
                   peak_price=920, engine_a_score=55)
    print(f'  verdict: {d.verdict}')
    print(' ', d.reason_string())

    # Test 3: velocity crash - 17-point weekly drop
    print('\nTest 3 - Velocity Crash (Momentum 68 -> 51):')
    d = check_exit('HEG', durability=72, momentum=51,
                   momentum_last_week=68, current_price=2000,
                   peak_price=2100, engine_a_score=55)
    print(f'  verdict: {d.verdict}')
    print(' ', d.reason_string())

    # Test 4: hard stop - 16% below peak
    print('\nTest 4 - Hard Stop (price 16% below peak):')
    d = check_exit('BHEL', durability=58, momentum=60,
                   momentum_last_week=62, current_price=210,
                   peak_price=250, engine_a_score=55)
    print(f'  verdict: {d.verdict}')
    print(' ', d.reason_string())

    # Test 5: Engine A gate - regime collapse
    print('\nTest 5 - Engine A Gate (score 18):')
    d = check_exit('MCX', durability=75, momentum=70,
                   momentum_last_week=70, current_price=5000,
                   peak_price=5100, engine_a_score=18)
    print(f'  verdict: {d.verdict}')
    print(' ', d.reason_string())

    # Test 6: multiple triggers fire at once
    print('\nTest 6 - multiple triggers (DVM decay + hard stop):')
    d = check_exit('USHAMART', durability=40, momentum=45,
                   momentum_last_week=55, current_price=300,
                   peak_price=400, engine_a_score=55)
    print(f'  verdict: {d.verdict}  ({d.facts[-1][1]} triggers)')
    print(' ', d.reason_string())

    # Test 7: Engine A regime translation
    print('\nTest 7 - Engine A regime gate states:')
    for score in [10, 25, 40, 80]:
        print(f'  Engine A score {score:3} -> {engine_a_regime(score)}')

    print('\n' + '=' * 64)
    print('Self-test complete. Any one of four triggers forces an EXIT;')
    print('a surviving position returns HOLD with distance to the')
    print('nearest trigger. Exit triggers are absolute.')
    print('=' * 64)
