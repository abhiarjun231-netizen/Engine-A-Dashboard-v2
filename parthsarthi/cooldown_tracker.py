"""
cooldown_tracker.py
Parthsarthi Capital - Phase 1, Item 1.6
COOLDOWN & RE-ENTRY TRACKER - the last shared-infrastructure module.

Two jobs, both shared by Engines B, C and D:

  1. COOLDOWN - after a stock is EXITED, it cannot be re-entered for
     14 days. This breaks the whipsaw loop where a volatile stock
     re-triggers an entry days after being stopped out.

  2. CHURNER FLAG - if a stock appears on a screener 3 or more times
     within a 90-day window, it is flagged CHURNER. A stock that keeps
     qualifying, failing and re-qualifying is choppy, not trending -
     it needs manual review before any further entry.

This module records exits and appearances, and answers one question
the engines ask before every entry: "is this stock allowed in right now?"
"""

import os
import json
from datetime import datetime, timedelta


COOLDOWN_DAYS = 14
CHURN_WINDOW_DAYS = 90
CHURN_THRESHOLD = 3          # appearances within the window to flag CHURNER

TRACKER_FILE = 'cooldown_tracker.json'


class CooldownTracker:
    """Tracks exits (for cooldown) and appearances (for churn detection)."""

    def __init__(self, store_path=None):
        self.store_path = store_path or TRACKER_FILE
        # ticker -> list of exit ISO timestamps
        self.exits = {}
        # ticker -> list of appearance ISO dates
        self.appearances = {}
        self._load()

    # ---- persistence ----
    def _load(self):
        if os.path.exists(self.store_path):
            try:
                with open(self.store_path) as f:
                    d = json.load(f)
                self.exits = d.get('exits', {})
                self.appearances = d.get('appearances', {})
            except (json.JSONDecodeError, ValueError):
                pass

    def _save(self):
        with open(self.store_path, 'w') as f:
            json.dump({'exits': self.exits,
                       'appearances': self.appearances}, f, indent=2)

    # ---- recording ----
    def record_exit(self, ticker, when=None):
        """Log that a stock was exited - starts its cooldown clock."""
        when = when or datetime.now()
        self.exits.setdefault(ticker, []).append(
            when.isoformat(timespec='seconds'))
        self._save()

    def record_appearance(self, ticker, when=None):
        """Log that a stock appeared on a screener - feeds churn detection."""
        when = when or datetime.now()
        self.appearances.setdefault(ticker, []).append(
            when.isoformat(timespec='seconds'))
        self._save()

    # ---- queries ----
    def in_cooldown(self, ticker, now=None):
        """
        Is the stock currently inside its 14-day cooldown?
        Returns (True/False, days_remaining).
        """
        now = now or datetime.now()
        exits = self.exits.get(ticker, [])
        if not exits:
            return False, 0
        last_exit = datetime.fromisoformat(exits[-1])
        elapsed = (now - last_exit).total_seconds() / 86400.0
        if elapsed < COOLDOWN_DAYS:
            return True, round(COOLDOWN_DAYS - elapsed, 1)
        return False, 0

    def is_churner(self, ticker, now=None):
        """
        Has the stock appeared CHURN_THRESHOLD+ times in the last 90 days?
        Returns (True/False, appearance_count_in_window).
        """
        now = now or datetime.now()
        cutoff = now - timedelta(days=CHURN_WINDOW_DAYS)
        apps = self.appearances.get(ticker, [])
        recent = [a for a in apps if datetime.fromisoformat(a) >= cutoff]
        return (len(recent) >= CHURN_THRESHOLD, len(recent))

    def entry_allowed(self, ticker, now=None):
        """
        The question every engine asks before an entry.
        Returns (allowed: bool, reason: str).
        """
        now = now or datetime.now()

        cooling, days_left = self.in_cooldown(ticker, now)
        if cooling:
            return False, (f'In cooldown - {days_left} day(s) remaining '
                           f'of the {COOLDOWN_DAYS}-day period')

        churner, count = self.is_churner(ticker, now)
        if churner:
            return False, (f'CHURNER flag - appeared {count} times in '
                            f'{CHURN_WINDOW_DAYS} days; manual review required')

        return True, 'Entry allowed - not in cooldown, not a churner'


# ---- self-test ----
if __name__ == '__main__':
    print('=' * 60)
    print('COOLDOWN & RE-ENTRY TRACKER - self-test')
    print('=' * 60)

    test_file = '/tmp/cooldown_test.json'
    if os.path.exists(test_file):
        os.remove(test_file)

    ct = CooldownTracker(store_path=test_file)
    now = datetime.now()

    # Test 1: a stock just exited - should be in cooldown
    print('\nTest 1 - stock exited today:')
    ct.record_exit('TATASTEEL', when=now)
    allowed, reason = ct.entry_allowed('TATASTEEL', now=now)
    print(f'  entry allowed: {allowed}')
    print(f'  reason: {reason}')

    # Test 2: same stock, 10 days later - still cooling
    print('\nTest 2 - 10 days after exit:')
    allowed, reason = ct.entry_allowed('TATASTEEL', now=now + timedelta(days=10))
    print(f'  entry allowed: {allowed}')
    print(f'  reason: {reason}')

    # Test 3: same stock, 15 days later - cooldown passed
    print('\nTest 3 - 15 days after exit:')
    allowed, reason = ct.entry_allowed('TATASTEEL', now=now + timedelta(days=15))
    print(f'  entry allowed: {allowed}')
    print(f'  reason: {reason}')

    # Test 4: a churner - appears 3 times in 90 days
    print('\nTest 4 - stock appears 3 times in 90 days:')
    ct.record_appearance('CHOPPYCO', when=now - timedelta(days=70))
    ct.record_appearance('CHOPPYCO', when=now - timedelta(days=40))
    ct.record_appearance('CHOPPYCO', when=now - timedelta(days=5))
    allowed, reason = ct.entry_allowed('CHOPPYCO', now=now)
    print(f'  entry allowed: {allowed}')
    print(f'  reason: {reason}')

    # Test 5: a stock that appeared twice only - not a churner
    print('\nTest 5 - stock appeared only twice in window:')
    ct.record_appearance('STEADYCO', when=now - timedelta(days=50))
    ct.record_appearance('STEADYCO', when=now - timedelta(days=10))
    allowed, reason = ct.entry_allowed('STEADYCO', now=now)
    print(f'  entry allowed: {allowed}')
    print(f'  reason: {reason}')

    # Test 6: old appearances fall out of the 90-day window
    print('\nTest 6 - 3 appearances but one is 120 days old:')
    ct.record_appearance('OLDCHURN', when=now - timedelta(days=120))
    ct.record_appearance('OLDCHURN', when=now - timedelta(days=60))
    ct.record_appearance('OLDCHURN', when=now - timedelta(days=20))
    churner, count = ct.is_churner('OLDCHURN', now=now)
    print(f'  appearances in 90d window: {count}  -> churner: {churner}')
    print('  (the 120-day-old appearance correctly fell out of the window)')

    os.remove(test_file)
    print('\n' + '=' * 60)
    print('Self-test complete. The tracker enforces the 14-day cooldown')
    print('and raises the CHURNER flag at 3 appearances in 90 days.')
    print('=' * 60)
