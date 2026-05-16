"""
engine_b_reentry.py
Parthsarthi Capital - Phase 2, Item 2.7
ENGINE B - RE-ENTRY & CHURNER LOGIC (Module 6).

When a stock the system has EXITED reappears on the momentum screen,
this module decides whether it may be re-entered.

The rules (from the Engine B framework):
  - Reappears within 14-day cooldown        -> ignored, absolute
  - Reappears after cooldown, exited by Hard Stop
        -> treated as NEW, full conviction re-score, must clear 7
  - Reappears after cooldown, exited by DVM Decay / Velocity / Gate
        -> treated as NEW, but the Fresh Qualifier signal does NOT
           apply (it is a returnee, not a fresh name)
  - Reappears 3+ times in 90 days           -> CHURNER flag,
        manual review required before any re-entry

This module sits on top of the shared cooldown_tracker (Phase 1.6).
The tracker answers cooldown + churn timing; this module adds the
Engine-B-specific rule about whether Fresh Qualifier applies.
"""

from reasoning_engine import Decision
from cooldown_tracker import CooldownTracker


# exit reasons that, on re-entry, still allow the Fresh Qualifier signal.
# Hard Stop is a clean price-stop - a returnee after a hard stop is
# treated fully fresh. DVM/Velocity/Gate exits are thesis-decay exits -
# a returnee is a returnee, Fresh Qualifier is withheld.
FRESH_OK_AFTER = {'Hard Stop'}
FRESH_DENIED_AFTER = {'DVM Decay', 'Velocity Crash', 'Engine A Gate'}


def evaluate_reentry(ticker, last_exit_reason, tracker, now=None):
    """
    Decide whether an exited stock that has reappeared may be re-entered.

    last_exit_reason - the Module 3 trigger name from the prior exit
                       ('Hard Stop', 'DVM Decay', 'Velocity Crash',
                        'Engine A Gate'), or None if not recorded.
    tracker          - a shared CooldownTracker instance.

    Returns a Decision with one of:
      RE-ENTRY-BLOCKED   - still in cooldown
      CHURNER-REVIEW     - flagged churner, needs manual review
      RE-ENTRY-ALLOWED   - may be re-scored as NEW; the decision states
                           whether the Fresh Qualifier signal applies
    """
    allowed, reason = tracker.entry_allowed(ticker, now=now)

    # ---- blocked by cooldown ----
    if not allowed and 'cooldown' in reason.lower():
        d = Decision('B', ticker, 'RE-ENTRY-BLOCKED', 'Module 6 - Cooldown')
        d.add_fact('Status', reason)
        d.add_fact('Last exit reason', last_exit_reason or 'unknown')
        d.set_margin('cooldown still active', 0)
        d.set_counterfactual('-> RE-ENTRY-ALLOWED once the 14-day '
                              'cooldown elapses, if not flagged CHURNER')
        return d

    # ---- blocked by churner flag ----
    if not allowed and 'churner' in reason.lower():
        d = Decision('B', ticker, 'CHURNER-REVIEW', 'Module 6 - CHURNER Flag')
        d.add_fact('Status', reason)
        d.add_fact('Last exit reason', last_exit_reason or 'unknown')
        d.set_margin('manual review required', 0)
        d.set_counterfactual('manual review must clear the CHURNER flag '
                              'before any re-entry - repeated whipsaw is '
                              'a quality warning, not an opportunity')
        return d

    # ---- re-entry allowed: decide on the Fresh Qualifier signal ----
    fresh_applies = last_exit_reason in FRESH_OK_AFTER

    d = Decision('B', ticker, 'RE-ENTRY-ALLOWED', 'Module 6 - Re-Entry')
    d.add_fact('Cooldown', 'elapsed')
    d.add_fact('Last exit reason', last_exit_reason or 'unknown')
    d.add_fact('Treated as', 'NEW - full conviction re-score required')
    if fresh_applies:
        d.add_fact('Fresh Qualifier', 'APPLIES (clean Hard Stop exit)')
    else:
        d.add_fact('Fresh Qualifier', 'WITHHELD (returnee after a '
                                       'thesis-decay exit)')
    d.set_margin('re-entry conditions met', 1)
    d.set_counterfactual(
        'the stock is re-scored from scratch; it must clear conviction '
        '7 again to STRIKE - re-entry permission is not a buy signal')
    return d


# ---- self-test ----
if __name__ == '__main__':
    import os
    from datetime import datetime, timedelta

    print('=' * 64)
    print('ENGINE B RE-ENTRY & CHURNER LOGIC (Module 6) - self-test')
    print('=' * 64)

    test_file = '/tmp/reentry_test.json'
    if os.path.exists(test_file):
        os.remove(test_file)

    tracker = CooldownTracker(store_path=test_file)
    now = datetime.now()

    # Test 1: reappears within cooldown -> BLOCKED
    print('\nTest 1 - exited 5 days ago, reappears (within cooldown):')
    tracker.record_exit('TATASTEEL', when=now - timedelta(days=5))
    d = evaluate_reentry('TATASTEEL', 'Hard Stop', tracker, now=now)
    print(f'  verdict: {d.verdict}')
    print(' ', d.reason_string())

    # Test 2: cooldown elapsed, exited by Hard Stop -> Fresh APPLIES
    print('\nTest 2 - exited 20 days ago by Hard Stop, reappears:')
    tracker2 = CooldownTracker(store_path='/tmp/reentry_t2.json')
    tracker2.record_exit('JSWSTEEL', when=now - timedelta(days=20))
    d = evaluate_reentry('JSWSTEEL', 'Hard Stop', tracker2, now=now)
    print(f'  verdict: {d.verdict}')
    print(' ', d.reason_string())

    # Test 3: cooldown elapsed, exited by DVM Decay -> Fresh WITHHELD
    print('\nTest 3 - exited 20 days ago by DVM Decay, reappears:')
    tracker3 = CooldownTracker(store_path='/tmp/reentry_t3.json')
    tracker3.record_exit('HEG', when=now - timedelta(days=20))
    d = evaluate_reentry('HEG', 'DVM Decay', tracker3, now=now)
    print(f'  verdict: {d.verdict}')
    print(' ', d.reason_string())

    # Test 4: churner - 3 appearances in 90 days
    print('\nTest 4 - stock appeared 3 times in 90 days (CHURNER):')
    tracker4 = CooldownTracker(store_path='/tmp/reentry_t4.json')
    tracker4.record_appearance('CHOPPYCO', when=now - timedelta(days=70))
    tracker4.record_appearance('CHOPPYCO', when=now - timedelta(days=40))
    tracker4.record_appearance('CHOPPYCO', when=now - timedelta(days=5))
    d = evaluate_reentry('CHOPPYCO', 'Velocity Crash', tracker4, now=now)
    print(f'  verdict: {d.verdict}')
    print(' ', d.reason_string())

    # cleanup
    for f in [test_file, '/tmp/reentry_t2.json', '/tmp/reentry_t3.json',
              '/tmp/reentry_t4.json']:
        if os.path.exists(f):
            os.remove(f)

    print('\n' + '=' * 64)
    print('Self-test complete. Re-entry is blocked during cooldown,')
    print('blocked for churners, and otherwise allowed as a NEW re-score')
    print('- with Fresh Qualifier applied only after a clean Hard Stop.')
    print('=' * 64)
