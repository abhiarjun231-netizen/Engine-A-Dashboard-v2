"""
engine_b_lifecycle.py
Parthsarthi Capital - Phase 2, Item 2.2
ENGINE B - POSITION LIFECYCLE (6-stage momentum machine).

The shared five-state model (NEW/WATCH/HELD/DETERIORATING/EXITED)
tracks WHERE a stock is at the portfolio level. This module adds the
Engine-B-specific LIFECYCLE STAGE - the finer detail of where a
momentum position is in its journey:

  SCOUT   - on screen, conviction not yet run
  STALK   - conviction scored, sitting in WATCH
  STRIKE  - conviction >= 7, capital allocated, freshly bought
  RIDE    - position open and healthy (D >= 55 AND M >= 59)
  GUARD   - either score in the grey zone - warning, no adding
  EXIT    - an exit trigger fired - position closed

The stage and the shared state move together:
  SCOUT/STALK   -> shared state NEW or WATCH
  STRIKE/RIDE   -> shared state HELD
  GUARD         -> shared state DETERIORATING
  EXIT          -> shared state EXITED

This module decides the STAGE from the live scores; it does not place
trades and does not fire exits (Module 3 does exits). It answers:
"given this stock's current scores, what lifecycle stage is it in?"
"""

from reasoning_engine import Decision


# ---- stage names ----
SCOUT  = 'SCOUT'
STALK  = 'STALK'
STRIKE = 'STRIKE'
RIDE   = 'RIDE'
GUARD  = 'GUARD'
EXIT   = 'EXIT'

# ---- health thresholds for an OPEN position (from the framework) ----
RIDE_DURABILITY = 55      # D >= 55 AND
RIDE_MOMENTUM   = 59      # M >= 59  -> healthy RIDE
# below those (but not yet at exit floors) -> GUARD grey zone
GREY_DUR_FLOOR  = 45      # exit handled by Module 3; 45-55 is grey
GREY_MOM_FLOOR  = 49      # 49-59 is grey

# map lifecycle stage -> shared five-state
STAGE_TO_STATE = {
    SCOUT:  'NEW',
    STALK:  'WATCH',
    STRIKE: 'HELD',
    RIDE:   'HELD',
    GUARD:  'DETERIORATING',
    EXIT:   'EXITED',
}


def stage_for_candidate(conviction_verdict):
    """
    For a stock NOT yet owned, the lifecycle stage follows the
    conviction verdict:
      conviction not run  -> SCOUT
      STALK / SKIP        -> STALK  (sitting in WATCH)
      STRIKE              -> STRIKE (ready to buy)
    """
    if conviction_verdict is None:
        return SCOUT
    if conviction_verdict == 'STRIKE':
        return STRIKE
    return STALK   # STALK and SKIP both wait in WATCH


def stage_for_holding(durability, momentum):
    """
    For an OPEN position, the lifecycle stage follows the live DVM scores:
      D >= 55 AND M >= 59            -> RIDE  (healthy)
      either score in the grey zone  -> GUARD (warning)
    Note: actual EXIT (scores below the floors) is decided by Module 3,
    not here. This function only distinguishes RIDE from GUARD.
    Returns (stage, reason_detail).
    """
    d_ok = durability is not None and durability >= RIDE_DURABILITY
    m_ok = momentum is not None and momentum >= RIDE_MOMENTUM

    if d_ok and m_ok:
        return RIDE, (f'D {durability:.0f} >= {RIDE_DURABILITY} and '
                      f'M {momentum:.0f} >= {RIDE_MOMENTUM} - healthy')

    # in grey zone - identify which score(s) slipped
    issues = []
    if not d_ok:
        issues.append(f'D {durability:.0f} below {RIDE_DURABILITY}')
    if not m_ok:
        issues.append(f'M {momentum:.0f} below {RIDE_MOMENTUM}')
    return GUARD, 'grey zone: ' + ', '.join(issues)


def assess_holding(ticker, durability, momentum):
    """
    Assess an open Engine B position and return a Decision describing
    its lifecycle stage (RIDE or GUARD) with a full reason string.
    """
    stage, detail = stage_for_holding(durability, momentum)
    shared_state = STAGE_TO_STATE[stage]

    d = Decision('B', ticker, stage, 'Module 2 - Position Lifecycle')
    d.add_fact('Durability', f'{durability:.0f}' if durability is not None else 'n/a')
    d.add_fact('Momentum',   f'{momentum:.0f}' if momentum is not None else 'n/a')
    d.add_fact('Shared state', shared_state)
    d.add_fact('Assessment', detail)

    if stage == RIDE:
        # margin = how far the weaker score is above its RIDE floor
        d_margin = (durability - RIDE_DURABILITY) if durability is not None else 0
        m_margin = (momentum - RIDE_MOMENTUM) if momentum is not None else 0
        weakest = min(d_margin, m_margin)
        d.set_margin('weaker score above RIDE floor by', round(weakest, 1))
        d.set_counterfactual(
            f'-> GUARD if Durability falls below {RIDE_DURABILITY} '
            f'OR Momentum falls below {RIDE_MOMENTUM}')
    else:  # GUARD
        d.set_margin('in grey zone - watching for exit', 0)
        d.set_counterfactual(
            f'-> RIDE if both scores recover (D>={RIDE_DURABILITY}, '
            f'M>={RIDE_MOMENTUM}); -> EXIT if Module 3 trigger fires')
    return d


# ---- self-test ----
if __name__ == '__main__':
    print('=' * 62)
    print('ENGINE B POSITION LIFECYCLE - self-test')
    print('=' * 62)

    # Test 1: candidate stages from conviction verdict
    print('\nTest 1 - candidate lifecycle stages:')
    for verdict in [None, 'SKIP', 'STALK', 'STRIKE']:
        stage = stage_for_candidate(verdict)
        print(f'  conviction={str(verdict):8} -> stage {stage:7} '
              f'(state {STAGE_TO_STATE[stage]})')

    # Test 2: a healthy open position -> RIDE
    print('\nTest 2 - healthy open position (D 72, M 68):')
    d = assess_holding('TATASTEEL', 72, 68)
    print(f'  stage: {d.verdict}')
    print(' ', d.reason_string())

    # Test 3: a slipping position -> GUARD
    print('\nTest 3 - slipping position (D 50, M 66):')
    d = assess_holding('JSWSTEEL', 50, 66)
    print(f'  stage: {d.verdict}')
    print(' ', d.reason_string())

    # Test 4: both scores in grey zone -> GUARD
    print('\nTest 4 - both scores weak (D 48, M 52):')
    d = assess_holding('HINDZINC', 48, 52)
    print(f'  stage: {d.verdict}')
    print(' ', d.reason_string())

    # Test 5: borderline - exactly at RIDE floors
    print('\nTest 5 - borderline (D 55, M 59 - exactly at floors):')
    stage, detail = stage_for_holding(55, 59)
    print(f'  stage: {stage}  ({detail})')

    print('\n' + '=' * 62)
    print('Self-test complete. Lifecycle assigns SCOUT/STALK/STRIKE to')
    print('candidates and RIDE/GUARD to open positions, each mapped to')
    print('the shared five-state model with a full reason string.')
    print('=' * 62)
