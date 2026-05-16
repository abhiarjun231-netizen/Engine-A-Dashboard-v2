"""
engine_c_reunderwrite.py
Parthsarthi Capital - Phase 3, Item 3.6
ENGINE C - QUARTERLY RE-UNDERWRITE (Module 6).

Engine C reacts to events - a screen drop, a thesis-break trigger.
This module adds a SCHEDULED discipline: every 90 days, each held
position is formally re-scored from scratch, as if deciding to buy
it fresh today.

Why this matters: a holding can slowly decay - conviction drifting
from 8 down to 5 - without ever tripping a hard thesis-break trigger.
The 18-month dead-money timer would eventually catch it, but that is
a long time to hold a position the system would no longer buy.
The quarterly re-underwrite catches slow decay early.

It does NOT auto-exit. It produces one of:
  RE-UNDERWRITE-PASS    - holding still clears conviction 7; keep it
  RE-UNDERWRITE-REVIEW  - holding would no longer clear 7; flag it
                          for manual review and ranking consideration
  RE-UNDERWRITE-DUE     - 90 days have passed; re-scoring is due

The actual re-score reuses the value conviction module (3.1).
"""

from reasoning_engine import Decision


REUNDERWRITE_DAYS = 90       # quarterly cadence
CONVICTION_FLOOR  = 7        # a holding should still clear DEPLOY-grade


def is_reunderwrite_due(days_since_last, now_days=None):
    """True if 90+ days have passed since the last re-underwrite."""
    return days_since_last >= REUNDERWRITE_DAYS


def reunderwrite(ticker, days_since_last, fresh_conviction,
                 entry_conviction=None):
    """
    Run the quarterly re-underwrite check for one holding.

    days_since_last   - days since this holding was last re-underwritten
                        (or since entry, for the first review)
    fresh_conviction  - the conviction score if the stock were scored
                        fresh TODAY (from the value conviction module)
    entry_conviction  - the conviction score at original entry, for
                        the drift comparison

    Returns a Decision.
    """
    # not yet due
    if not is_reunderwrite_due(days_since_last):
        d = Decision('C', ticker, 'RE-UNDERWRITE-PASS',
                     'Module 6 - Re-Underwrite (not yet due)')
        d.add_fact('Days since last review', str(days_since_last))
        d.add_fact('Next review in', f'{REUNDERWRITE_DAYS - days_since_last} days')
        d.set_margin('days until re-underwrite is due',
                     REUNDERWRITE_DAYS - days_since_last)
        d.set_counterfactual(f'-> RE-UNDERWRITE-DUE after '
                              f'{REUNDERWRITE_DAYS} days since the last review')
        return d

    # due - and we have a fresh score, so evaluate it
    drift = None
    if entry_conviction is not None:
        drift = fresh_conviction - entry_conviction

    if fresh_conviction >= CONVICTION_FLOOR:
        d = Decision('C', ticker, 'RE-UNDERWRITE-PASS',
                     'Module 6 - Re-Underwrite (passed)')
        d.add_fact('Days since last review', str(days_since_last))
        d.add_fact('Fresh conviction', f'{fresh_conviction}/10')
        if drift is not None:
            d.add_fact('Drift from entry', f'{drift:+d} points')
        d.add_fact('Verdict', f'still clears conviction {CONVICTION_FLOOR} - keep')
        d.set_margin('fresh conviction above the floor by',
                     fresh_conviction - CONVICTION_FLOOR)
        d.set_counterfactual(
            f'-> RE-UNDERWRITE-REVIEW if a future re-score falls below '
            f'conviction {CONVICTION_FLOOR}')
        return d

    # due, and fails the floor - flag for review
    d = Decision('C', ticker, 'RE-UNDERWRITE-REVIEW',
                 'Module 6 - Re-Underwrite (review)')
    d.add_fact('Days since last review', str(days_since_last))
    d.add_fact('Fresh conviction', f'{fresh_conviction}/10')
    if drift is not None:
        d.add_fact('Drift from entry', f'{drift:+d} points')
    d.add_fact('Verdict', f'would no longer clear conviction '
                          f'{CONVICTION_FLOOR} if scored fresh today')
    d.set_margin('fresh conviction below the floor by',
                 CONVICTION_FLOOR - fresh_conviction)
    d.set_counterfactual(
        'this holding would not be bought today - flag for manual '
        'review and ranking consideration; it is a rotation candidate. '
        'Note: this flags, it does not auto-exit - only Path A booking '
        'or a Path B thesis-break trigger closes a position')
    return d


# ---- self-test ----
if __name__ == '__main__':
    print('=' * 64)
    print('ENGINE C QUARTERLY RE-UNDERWRITE (Module 6) - self-test')
    print('=' * 64)

    # Test 1: review not yet due (40 days)
    print('\nTest 1 - 40 days since last review (not due):')
    d = reunderwrite('PTC', days_since_last=40, fresh_conviction=8,
                     entry_conviction=8)
    print(f'  verdict: {d.verdict}')
    print(' ', d.reason_string())

    # Test 2: due, holding still strong -> PASS
    print('\nTest 2 - 95 days, fresh conviction 8 (still strong):')
    d = reunderwrite('JSWSTEEL', days_since_last=95, fresh_conviction=8,
                     entry_conviction=7)
    print(f'  verdict: {d.verdict}')
    print(' ', d.reason_string())

    # Test 3: due, conviction has decayed -> REVIEW
    print('\nTest 3 - 100 days, conviction decayed 8 -> 5:')
    d = reunderwrite('SHARDACROP', days_since_last=100, fresh_conviction=5,
                     entry_conviction=8)
    print(f'  verdict: {d.verdict}')
    print(' ', d.reason_string())

    # Test 4: due, conviction exactly at floor -> PASS
    print('\nTest 4 - 90 days exactly, fresh conviction 7 (at floor):')
    d = reunderwrite('HINDZINC', days_since_last=90, fresh_conviction=7,
                     entry_conviction=7)
    print(f'  verdict: {d.verdict}')

    # Test 5: due check helper
    print('\nTest 5 - is_reunderwrite_due helper:')
    for days in [30, 89, 90, 120]:
        print(f'  {days:3} days since last -> due: {is_reunderwrite_due(days)}')

    print('\n' + '=' * 64)
    print('Self-test complete. Every 90 days each holding is re-scored;')
    print('one that would no longer clear conviction 7 is FLAGGED for')
    print('review - it is not auto-exited. Slow decay is caught early.')
    print('=' * 64)
