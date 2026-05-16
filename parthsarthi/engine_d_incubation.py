"""
engine_d_incubation.py
Parthsarthi Capital - Phase 4, Item 4.2
ENGINE D - THE 90-DAY INCUBATION ENGINE (Module 2).

Engine D does not commit full capital at entry. A stock that clears
conviction (INCUBATE, score >= 7) enters a 90-day incubation at HALF
the target size. It must prove the thesis before the system commits
the rest.

The mechanic:
  Day 0   : conviction cleared -> deploy 50% of target size.
            State: INCUBATING.
  Day 0-90: the stock must REMAIN on the D1 screen and hold
            conviction >= 6 at each reading.
  Day 90  : if still qualifying -> top up to 100% of target.
            State: HELD (a confirmed compounder).
  Anytime : if it drops off-screen OR conviction falls below 6
            during incubation -> EXIT the 50% partial position.
            The thesis did not prove out.

Why half-size: for a multi-year hold, 90 days of confirmation before
full commitment is cheap insurance. A failed incubation costs half
as much as a full-size mistake.

This module tracks the incubation day-count and decides the next
action for an incubating position.
"""

from reasoning_engine import Decision


INCUBATION_DAYS       = 90      # incubation period
INCUBATION_MIN_SCORE  = 6       # conviction must stay at/above this
INCUBATION_FRACTION   = 0.50    # fraction of target deployed at entry


def begin_incubation(ticker, conviction, target_value):
    """
    Start a new incubation for a stock that cleared conviction 7+.
    Returns a Decision describing the partial entry.
    """
    deploy_value = target_value * INCUBATION_FRACTION
    d = Decision('D', ticker, 'INCUBATE-START', 'Module 2 - Incubation (begin)')
    d.add_fact('Conviction', f'{conviction}/10')
    d.add_fact('Target size', f'{target_value:,.0f}')
    d.add_fact('Deploy now', f'{deploy_value:,.0f} ({INCUBATION_FRACTION*100:.0f}% of target)')
    d.add_fact('Incubation period', f'{INCUBATION_DAYS} days')
    d.set_margin('conviction above the incubation floor by',
                 conviction - INCUBATION_MIN_SCORE)
    d.set_counterfactual(
        f'-> top up to full at day {INCUBATION_DAYS} if still on-screen '
        f'with conviction >= {INCUBATION_MIN_SCORE}; -> EXIT the partial '
        f'if it drops off-screen or conviction falls below '
        f'{INCUBATION_MIN_SCORE} during incubation')
    return d


def assess_incubation(ticker, days_incubating, current_conviction,
                      on_screen, target_value):
    """
    Assess a position currently in incubation.

    Returns a Decision with one of:
      INCUBATE-FAIL   - dropped off-screen or conviction fell below 6;
                        exit the 50% partial position
      INCUBATE-PROMOTE- 90 days passed, still qualifying; top up to
                        100% target, state becomes HELD
      INCUBATE-HOLD   - still inside the 90-day window, still
                        qualifying; continue incubating
    """
    # ---- incubation failure: off-screen or conviction collapsed ----
    if not on_screen:
        d = Decision('D', ticker, 'INCUBATE-FAIL',
                     'Module 2 - Incubation (failed: off-screen)')
        d.add_fact('Days incubating', str(days_incubating))
        d.add_fact('Reason', 'dropped off the D1 screen during incubation')
        d.add_fact('Action', 'EXIT the 50% partial position')
        d.set_margin('incubation failed before day 90', 0)
        d.set_counterfactual(
            'the thesis did not prove out; a failed incubation costs '
            'half a position - that is the mechanic working as designed')
        return d

    if current_conviction < INCUBATION_MIN_SCORE:
        d = Decision('D', ticker, 'INCUBATE-FAIL',
                     'Module 2 - Incubation (failed: conviction)')
        d.add_fact('Days incubating', str(days_incubating))
        d.add_fact('Current conviction', f'{current_conviction}/10')
        d.add_fact('Reason', f'conviction fell below the incubation floor '
                             f'of {INCUBATION_MIN_SCORE}')
        d.add_fact('Action', 'EXIT the 50% partial position')
        d.set_margin('conviction below the incubation floor by',
                     INCUBATION_MIN_SCORE - current_conviction)
        d.set_counterfactual(
            f'would have continued incubating if conviction had stayed '
            f'>= {INCUBATION_MIN_SCORE}')
        return d

    # ---- 90 days passed, still qualifying -> promote to full ----
    if days_incubating >= INCUBATION_DAYS:
        topup = target_value * (1 - INCUBATION_FRACTION)
        d = Decision('D', ticker, 'INCUBATE-PROMOTE',
                     'Module 2 - Incubation (promote to HELD)')
        d.add_fact('Days incubating', str(days_incubating))
        d.add_fact('Current conviction', f'{current_conviction}/10')
        d.add_fact('Action', f'top up {topup:,.0f} to reach 100% target')
        d.add_fact('New state', 'HELD - a confirmed compounder')
        d.set_margin('days past the incubation threshold',
                     days_incubating - INCUBATION_DAYS)
        d.set_counterfactual(
            'the thesis proved out over 90 days - full capital is now '
            'committed; the position enters the SEEDLING promotion tier')
        return d

    # ---- still inside the window, still qualifying -> continue ----
    d = Decision('D', ticker, 'INCUBATE-HOLD',
                 'Module 2 - Incubation (continuing)')
    d.add_fact('Days incubating', str(days_incubating))
    d.add_fact('Current conviction', f'{current_conviction}/10')
    d.add_fact('Status', f'{INCUBATION_DAYS - days_incubating} days until '
                         f'the promotion decision')
    d.set_margin('days remaining in incubation',
                 INCUBATION_DAYS - days_incubating)
    d.set_counterfactual(
        f'-> INCUBATE-PROMOTE at day {INCUBATION_DAYS} if still qualifying; '
        f'-> INCUBATE-FAIL if it drops off-screen or conviction falls '
        f'below {INCUBATION_MIN_SCORE}')
    return d


# ---- self-test ----
if __name__ == '__main__':
    print('=' * 64)
    print('ENGINE D 90-DAY INCUBATION ENGINE (Module 2) - self-test')
    print('=' * 64)

    # Test 1: begin a new incubation
    print('\nTest 1 - begin incubation (conviction 8, target 100000):')
    d = begin_incubation('HINDZINC', conviction=8, target_value=100000)
    print(f'  verdict: {d.verdict}')
    print(' ', d.reason_string())

    # Test 2: still incubating, day 45, still qualifying
    print('\nTest 2 - day 45, still on-screen, conviction 7:')
    d = assess_incubation('HINDZINC', days_incubating=45,
                          current_conviction=7, on_screen=True,
                          target_value=100000)
    print(f'  verdict: {d.verdict}')
    print(' ', d.reason_string())

    # Test 3: day 92, still qualifying -> promote to full
    print('\nTest 3 - day 92, still qualifying -> promote to HELD:')
    d = assess_incubation('HINDZINC', days_incubating=92,
                          current_conviction=7, on_screen=True,
                          target_value=100000)
    print(f'  verdict: {d.verdict}')
    print(' ', d.reason_string())

    # Test 4: dropped off-screen during incubation -> FAIL
    print('\nTest 4 - day 50, dropped off-screen -> incubation failed:')
    d = assess_incubation('FORCEMOT', days_incubating=50,
                          current_conviction=7, on_screen=False,
                          target_value=100000)
    print(f'  verdict: {d.verdict}')
    print(' ', d.reason_string())

    # Test 5: conviction collapsed during incubation -> FAIL
    print('\nTest 5 - day 60, conviction fell to 4 -> incubation failed:')
    d = assess_incubation('GVPIL', days_incubating=60,
                          current_conviction=4, on_screen=True,
                          target_value=100000)
    print(f'  verdict: {d.verdict}')
    print(' ', d.reason_string())

    # Test 6: day 90 exactly -> promote
    print('\nTest 6 - day 90 exactly, still qualifying:')
    d = assess_incubation('THYROCARE', days_incubating=90,
                          current_conviction=8, on_screen=True,
                          target_value=100000)
    print(f'  verdict: {d.verdict}')

    print('\n' + '=' * 64)
    print('Self-test complete. Incubation deploys 50% at entry, tops up')
    print('to 100% at day 90 if still qualifying, and exits the partial')
    print('if the thesis fails - a failed incubation costs half a mistake.')
    print('=' * 64)
