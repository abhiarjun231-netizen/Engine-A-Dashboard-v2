"""
state_model.py
Parthsarthi Capital - Phase 1, Item 1.2
THE FIVE-STATE MODEL - shared state machine for Engines B, C, D.

Every stock the system has ever seen sits in exactly one state.
The intelligence layer is the rulebook that moves stocks between states.
This module owns the states, the legal transitions, and the transition log.

It does NOT decide WHEN to transition - that is the engines' job (conviction
scoring, exit triggers, churn handlers). This module enforces that only LEGAL
transitions happen, stamps every transition with a timestamp and reason, and
keeps the audit trail.

States (from the Master Intelligence Framework):
  NEW           - appeared on screen today, never assessed
  WATCH         - qualifies, assessed, not bought
  HELD          - owned, inside the lifecycle
  DETERIORATING - owned, but thesis weakening
  EXITED        - sold, in cooldown

Used by all three engines. Engine-specific lifecycle stages (e.g. Engine B's
SCOUT/STRIKE/RIDE or Engine D's promotion tiers) sit ON TOP of these five
shared states - they are tracked separately by each engine.
"""

import json
import os
from datetime import datetime


# ---- The five shared states ----
NEW           = 'NEW'
WATCH         = 'WATCH'
HELD          = 'HELD'
DETERIORATING = 'DETERIORATING'
EXITED        = 'EXITED'

ALL_STATES = [NEW, WATCH, HELD, DETERIORATING, EXITED]

# ---- Legal transitions ----
# A transition not in this map is rejected. This is the guard rail that
# stops an engine bug from moving a stock somewhere nonsensical.
LEGAL_TRANSITIONS = {
    NEW:           [WATCH, EXITED],              # assessed -> WATCH; or dropped
    WATCH:         [HELD, EXITED, NEW],          # bought -> HELD; passed/dropped; re-surfaced
    HELD:          [DETERIORATING, EXITED],      # thesis weakens; or sold
    DETERIORATING: [HELD, EXITED],               # recovers -> HELD; or sold
    EXITED:        [NEW],                        # cooldown passed, re-surfaces as NEW
}

# Human-readable meaning, for reason strings and reports
STATE_MEANING = {
    NEW:           'Appeared on screen, not yet assessed',
    WATCH:         'Qualifies, assessed, not bought',
    HELD:          'Owned, inside the lifecycle',
    DETERIORATING: 'Owned, thesis weakening',
    EXITED:        'Sold, in cooldown',
}


class IllegalTransition(Exception):
    """Raised when an engine attempts a transition not in LEGAL_TRANSITIONS."""
    pass


class StateModel:
    """
    Tracks the current state of every stock for one engine, and logs
    every transition. One StateModel instance per engine (B, C, D).
    """

    def __init__(self, engine_name, store_path=None):
        self.engine = engine_name
        self.store_path = store_path or f'state_{engine_name.lower()}.json'
        # {ticker: {'state': str, 'since': iso, 'engine': str}}
        self.states = {}
        # list of transition records
        self.log = []
        self._load()

    # ---- persistence ----
    def _load(self):
        if os.path.exists(self.store_path):
            try:
                with open(self.store_path) as f:
                    data = json.load(f)
                self.states = data.get('states', {})
                self.log = data.get('log', [])
            except (json.JSONDecodeError, ValueError):
                self.states, self.log = {}, []

    def _save(self):
        with open(self.store_path, 'w') as f:
            json.dump({'states': self.states, 'log': self.log}, f, indent=2)

    # ---- core API ----
    def get_state(self, ticker):
        """Current state of a ticker, or None if the system has never seen it."""
        rec = self.states.get(ticker)
        return rec['state'] if rec else None

    def register_new(self, ticker, reason='Appeared on screen'):
        """
        First time the system sees a ticker. Enters at NEW.
        If the ticker already exists, this is a no-op (it is not 'new').
        """
        if ticker in self.states:
            return False
        now = datetime.now().isoformat(timespec='seconds')
        self.states[ticker] = {'state': NEW, 'since': now, 'engine': self.engine}
        self._log_transition(ticker, None, NEW, reason)
        self._save()
        return True

    def transition(self, ticker, to_state, reason):
        """
        Move a ticker to a new state. Rejects illegal transitions.
        `reason` is mandatory - a transition without a reason is invalid
        (this is the reasoning-engine discipline from the framework).
        """
        if not reason or not str(reason).strip():
            raise ValueError('A transition must have a reason string.')
        if to_state not in ALL_STATES:
            raise ValueError(f'Unknown state: {to_state}')

        current = self.get_state(ticker)
        if current is None:
            raise IllegalTransition(
                f'{ticker} has no state - call register_new first.')

        if to_state not in LEGAL_TRANSITIONS.get(current, []):
            raise IllegalTransition(
                f'{ticker}: {current} -> {to_state} is not a legal transition. '
                f'Legal from {current}: {LEGAL_TRANSITIONS.get(current, [])}')

        now = datetime.now().isoformat(timespec='seconds')
        self.states[ticker] = {'state': to_state, 'since': now, 'engine': self.engine}
        self._log_transition(ticker, current, to_state, reason)
        self._save()
        return True

    def _log_transition(self, ticker, from_state, to_state, reason):
        self.log.append({
            'timestamp': datetime.now().isoformat(timespec='seconds'),
            'engine':    self.engine,
            'ticker':    ticker,
            'from':      from_state,
            'to':        to_state,
            'reason':    reason,
        })

    # ---- queries ----
    def tickers_in_state(self, state):
        """All tickers currently in a given state."""
        return sorted(t for t, r in self.states.items() if r['state'] == state)

    def summary(self):
        """Count of tickers per state."""
        out = {s: 0 for s in ALL_STATES}
        for r in self.states.values():
            out[r['state']] += 1
        return out

    def history(self, ticker):
        """Full transition history for one ticker."""
        return [e for e in self.log if e['ticker'] == ticker]


# ---- self-test ----
if __name__ == '__main__':
    print('=' * 56)
    print('FIVE-STATE MODEL - self-test (Engine B)')
    print('=' * 56)

    # fresh test store
    for f in ['state_btest.json']:
        if os.path.exists(f):
            os.remove(f)

    sm = StateModel('BTEST', store_path='state_btest.json')

    # 1. register three new stocks
    for tk in ['TATASTEEL', 'JSWSTEEL', 'HINDZINC']:
        sm.register_new(tk, 'Appeared on Momentum screen')
    print('\nAfter registering 3 NEW stocks:')
    print(' ', sm.summary())

    # 2. legal transitions
    sm.transition('TATASTEEL', WATCH, 'Conviction scored 8/10')
    sm.transition('TATASTEEL', HELD,  'STRIKE - conviction 8, capital allocated')
    sm.transition('JSWSTEEL',  WATCH, 'Conviction scored 5/10 - STALK')
    sm.transition('HINDZINC',  WATCH, 'Conviction scored 3/10 - SKIP')
    sm.transition('HINDZINC',  EXITED,'Dropped from screen while in WATCH')
    print('\nAfter a round of legal transitions:')
    print(' ', sm.summary())

    # 3. HELD -> DETERIORATING -> back to HELD
    sm.transition('TATASTEEL', DETERIORATING, 'Momentum slipped into grey zone')
    sm.transition('TATASTEEL', HELD,          'Momentum recovered above 59')
    print('\nTATASTEEL history:')
    for e in sm.history('TATASTEEL'):
        frm = e['from'] or 'start'
        print(f"  {frm:14} -> {e['to']:14}  {e['reason']}")

    # 4. illegal transition is rejected
    print('\nAttempting an ILLEGAL transition (EXITED -> HELD)...')
    try:
        sm.transition('HINDZINC', HELD, 'trying to skip cooldown')
        print('  ERROR: illegal transition was allowed!')
    except IllegalTransition as e:
        print(f'  Correctly rejected: {e}')

    # 5. transition without a reason is rejected
    print('\nAttempting a transition with NO reason...')
    try:
        sm.transition('JSWSTEEL', HELD, '')
        print('  ERROR: reasonless transition was allowed!')
    except ValueError as e:
        print(f'  Correctly rejected: {e}')

    print('\nFinal state summary:')
    for s in ALL_STATES:
        tks = sm.tickers_in_state(s)
        print(f'  {s:14} {len(tks)}  {tks}')

    print('\n' + '=' * 56)
    print('Self-test complete. State machine enforces legal transitions,')
    print('mandates reason strings, and logs a full audit trail.')
    print('=' * 56)

    os.remove('state_btest.json')
