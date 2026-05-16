"""
engine_c_lifecycle.py
Parthsarthi Capital - Phase 3, Item 3.2
ENGINE C - THE VALUE LIFECYCLE (HUNT to BOOK).

The shared five-state model tracks WHERE a stock is at the portfolio
level. This module adds the Engine-C-specific lifecycle stage - the
finer detail of where a value position is in its journey.

The value lifecycle has five stages. Unlike Engine B, there is no
fast "GUARD" panic stage - a value position weakening triggers a
thesis check, not urgency. Patience is structural.

  HUNT      - on screen, conviction not yet run
  ENGAGED   - conviction scored, sitting in WATCH
  HELD      - conviction cleared, capital allocated, bought cheap
  RE-RATING - position up 20%+ from entry, thesis intact -
              the market is recognising the value
  BOOK      - a PE-expansion booking trigger has fired -
              harvesting the re-rate

Stage <-> shared five-state mapping:
  HUNT             -> NEW
  ENGAGED          -> WATCH
  HELD / RE-RATING -> HELD
  BOOK             -> HELD (still partly held until fully booked out)

This module decides the STAGE from entry price and current price.
It does not place trades and does not fire the booking - the
PE-expansion booking engine (Module 2A, item 3.3) does that.
"""

from reasoning_engine import Decision


# ---- stage names ----
HUNT      = 'HUNT'
ENGAGED   = 'ENGAGED'
HELD      = 'HELD'
RE_RATING = 'RE-RATING'
BOOK      = 'BOOK'

# a position up this much from entry, thesis intact, is RE-RATING
RERATING_GAIN_PCT = 20.0

# map lifecycle stage -> shared five-state
STAGE_TO_STATE = {
    HUNT:      'NEW',
    ENGAGED:   'WATCH',
    HELD:      'HELD',
    RE_RATING: 'HELD',
    BOOK:      'HELD',
}


def stage_for_candidate(conviction_verdict):
    """
    For a stock NOT yet owned, the lifecycle stage follows the
    value conviction verdict:
      conviction not run        -> HUNT
      HOLD-FIRE / PASS          -> ENGAGED (waiting in WATCH)
      DEPLOY                    -> ENGAGED (ready to buy; becomes
                                   HELD once capital is allocated)
    """
    if conviction_verdict is None:
        return HUNT
    return ENGAGED   # DEPLOY, HOLD-FIRE and PASS all sit in WATCH/ENGAGED


def stage_for_holding(entry_price, current_price, booking_started=False,
                      thesis_intact=True):
    """
    For an OPEN position, decide the lifecycle stage.

    booking_started - True once a PE-expansion booking trigger has fired.
    thesis_intact   - False if a thesis-break condition is present
                      (handled by Module 2B; passed in here so the
                       lifecycle reflects it).

    Returns (stage, reason_detail).
    """
    if entry_price <= 0:
        return HELD, 'invalid entry price'

    gain_pct = (current_price - entry_price) / entry_price * 100.0

    # booking in progress takes precedence
    if booking_started:
        return BOOK, (f'PE-expansion booking under way '
                      f'(position up {gain_pct:+.1f}% from entry)')

    # re-rating: up 20%+ with thesis intact
    if gain_pct >= RERATING_GAIN_PCT and thesis_intact:
        return RE_RATING, (f'up {gain_pct:+.1f}% from entry '
                           f'(>= +{RERATING_GAIN_PCT:.0f}%) - '
                           f'the market is recognising the value')

    # otherwise simply HELD - value can sit quietly, that is normal
    return HELD, (f'held, up {gain_pct:+.1f}% from entry - '
                  f'a value position drifting quietly is a normal hold')


def assess_holding(ticker, entry_price, current_price,
                   booking_started=False, thesis_intact=True):
    """
    Assess an open Engine C position and return a Decision describing
    its lifecycle stage with a full reason string.
    """
    stage, detail = stage_for_holding(entry_price, current_price,
                                      booking_started, thesis_intact)
    gain_pct = ((current_price - entry_price) / entry_price * 100.0
                if entry_price > 0 else 0.0)

    d = Decision('C', ticker, stage, 'Module 2 - Value Lifecycle')
    d.add_fact('Entry', f'{entry_price:.1f}')
    d.add_fact('Current price', f'{current_price:.1f}')
    d.add_fact('Position gain', f'{gain_pct:+.1f}%')
    d.add_fact('Shared state', STAGE_TO_STATE[stage])
    d.add_fact('Assessment', detail)

    if stage == RE_RATING:
        d.set_margin('gain above the RE-RATING threshold by',
                     round(gain_pct - RERATING_GAIN_PCT, 1))
        d.set_counterfactual(
            '-> BOOK once a PE-expansion booking trigger fires; '
            '-> HELD only if the gain fell back below '
            f'+{RERATING_GAIN_PCT:.0f}%')
    elif stage == BOOK:
        d.set_margin('booking in progress', 0)
        d.set_counterfactual('booking proceeds in thirds at +30/50/80% '
                              'PE expansion until the position is fully exited')
    else:  # HELD
        d.set_margin('gain to the RE-RATING threshold',
                     round(RERATING_GAIN_PCT - gain_pct, 1))
        d.set_counterfactual(
            f'-> RE-RATING when the position is up +{RERATING_GAIN_PCT:.0f}% '
            f'with thesis intact; a quiet or falling value position with '
            f'intact fundamentals is still a normal HELD')
    return d


# ---- self-test ----
if __name__ == '__main__':
    print('=' * 62)
    print('ENGINE C VALUE LIFECYCLE - self-test')
    print('=' * 62)

    # Test 1: candidate stages
    print('\nTest 1 - candidate lifecycle stages:')
    for verdict in [None, 'PASS', 'HOLD-FIRE', 'DEPLOY']:
        stage = stage_for_candidate(verdict)
        print(f'  conviction={str(verdict):10} -> stage {stage:8} '
              f'(state {STAGE_TO_STATE[stage]})')

    # Test 2: freshly held, small gain -> HELD
    print('\nTest 2 - held position, +5% (quiet hold):')
    d = assess_holding('PTC', entry_price=100, current_price=105)
    print(f'  stage: {d.verdict}')
    print(' ', d.reason_string())

    # Test 3: up 25%, thesis intact -> RE-RATING
    print('\nTest 3 - held position, +25% (re-rating):')
    d = assess_holding('JSWSTEEL', entry_price=100, current_price=125)
    print(f'  stage: {d.verdict}')
    print(' ', d.reason_string())

    # Test 4: value position DOWN 12%, thesis intact -> still HELD
    print('\nTest 4 - held position, -12% but thesis intact:')
    d = assess_holding('SHARDACROP', entry_price=100, current_price=88)
    print(f'  stage: {d.verdict}')
    print(' ', d.reason_string())
    print('  (note: a value stock falling is NOT an exit - it stays HELD)')

    # Test 5: booking has started -> BOOK
    print('\nTest 5 - position up 35%, PE-booking started:')
    d = assess_holding('HINDZINC', entry_price=100, current_price=135,
                       booking_started=True)
    print(f'  stage: {d.verdict}')
    print(' ', d.reason_string())

    # Test 6: up 25% but thesis broken -> NOT re-rating, stays HELD
    print('\nTest 6 - up 25% but thesis broken (handled by Module 2B):')
    stage, detail = stage_for_holding(100, 125, thesis_intact=False)
    print(f'  stage: {stage}  ({detail})')

    print('\n' + '=' * 62)
    print('Self-test complete. The value lifecycle has no fast panic')
    print('stage - a falling value position stays HELD while its thesis')
    print('is intact. RE-RATING and BOOK mark the harvest phase.')
    print('=' * 62)
