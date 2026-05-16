"""
reasoning_engine.py
Parthsarthi Capital - Phase 1, Item 1.3
THE REASONING ENGINE - structured reason-string generator.

Every decision the system makes must emit a reason string. A decision
without one is invalid. This module builds those reason strings in a
consistent, auditable format used by Engines B, C and D.

A reason string has five mandatory parts (from the Master Framework):
  1. VERDICT      - what was decided (e.g. STRIKE, EXIT, HOLD)
  2. RULE         - the exact rule/module that fired
  3. NUMBERS      - every threshold and the actual value behind it
  4. MARGIN       - how close the decision was to flipping
  5. COUNTERFACTUAL - what specific change would flip the decision

The point: when a regulator, a client, or the builder asks "why did the
system do that?", the answer is this string - deterministic, complete,
not an opinion.

This module does NOT make decisions. Engines make decisions and hand the
facts here; this module formats them into the locked reason-string shape.
"""

from datetime import datetime


class Signal:
    """One scored signal within a decision - e.g. one conviction component."""

    def __init__(self, name, points, earned, detail):
        self.name = name          # e.g. 'Momentum Surge'
        self.points = points      # max points this signal can contribute
        self.earned = earned      # points actually earned (0 if not met)
        self.detail = detail      # e.g. 'Mom 71, needs >70'

    def render(self):
        return f'{self.name} +{self.earned} ({self.detail})'


class Decision:
    """
    A single decision the system is about to log. An engine builds one of
    these, then calls .reason_string() to get the auditable output.
    """

    def __init__(self, engine, ticker, verdict, rule):
        self.engine = engine            # 'B' / 'C' / 'D'
        self.ticker = ticker
        self.verdict = verdict          # 'STRIKE', 'EXIT', 'HOLD', etc.
        self.rule = rule                # which module/trigger fired
        self.signals = []               # list of Signal (for scored decisions)
        self.facts = []                 # list of (label, value) for trigger decisions
        self.margin = None              # (description, value)
        self.counterfactual = None      # str
        self.timestamp = datetime.now().isoformat(timespec='seconds')

    # ---- builders ----
    def add_signal(self, name, points, earned, detail):
        self.signals.append(Signal(name, points, earned, detail))
        return self

    def add_fact(self, label, value):
        self.facts.append((label, value))
        return self

    def set_margin(self, description, value):
        self.margin = (description, value)
        return self

    def set_counterfactual(self, text):
        self.counterfactual = text
        return self

    # ---- validation ----
    def validate(self):
        """
        A reason string must be complete. Returns (ok, list_of_missing).
        The framework rule: a decision row without a complete reason is invalid.
        """
        missing = []
        if not self.verdict:
            missing.append('verdict')
        if not self.rule:
            missing.append('rule')
        if not self.signals and not self.facts:
            missing.append('numbers (no signals or facts)')
        if self.margin is None:
            missing.append('margin')
        if not self.counterfactual:
            missing.append('counterfactual')
        return (len(missing) == 0, missing)

    # ---- output ----
    def total_score(self):
        """Sum of earned points across all signals."""
        return sum(s.earned for s in self.signals)

    def max_score(self):
        return sum(s.points for s in self.signals)

    def reason_string(self):
        """
        Build the full auditable reason string. Raises if incomplete -
        an invalid decision must not be silently logged.
        """
        ok, missing = self.validate()
        if not ok:
            raise ValueError(
                f'Incomplete reason string for {self.ticker}: missing {missing}')

        parts = []
        # 1. verdict
        head = f'{self.verdict}'
        if self.signals:
            head += f' . Conviction {self.total_score()}/{self.max_score()}'
        parts.append(head)
        # 2. rule
        parts.append(f'Rule: {self.rule}')
        # 3. numbers
        if self.signals:
            parts.append(' . '.join(s.render() for s in self.signals))
        if self.facts:
            parts.append(' . '.join(f'{k}: {v}' for k, v in self.facts))
        # 4. margin
        desc, val = self.margin
        parts.append(f'Margin ({desc}): {val}')
        # 5. counterfactual
        parts.append(f'Counterfactual: {self.counterfactual}')

        return ' | '.join(parts)

    def as_dict(self):
        """Structured form, for the journal and dashboard."""
        return {
            'timestamp': self.timestamp,
            'engine': self.engine,
            'ticker': self.ticker,
            'verdict': self.verdict,
            'rule': self.rule,
            'score': self.total_score() if self.signals else None,
            'max_score': self.max_score() if self.signals else None,
            'signals': [
                {'name': s.name, 'points': s.points,
                 'earned': s.earned, 'detail': s.detail}
                for s in self.signals
            ],
            'facts': [{'label': k, 'value': v} for k, v in self.facts],
            'margin': {'description': self.margin[0], 'value': self.margin[1]}
                       if self.margin else None,
            'counterfactual': self.counterfactual,
            'reason_string': self.reason_string(),
        }


# ---- self-test ----
if __name__ == '__main__':
    print('=' * 60)
    print('REASONING ENGINE - self-test')
    print('=' * 60)

    # --- Test 1: a scored conviction decision (Engine B STALK) ---
    print('\nTest 1 - Engine B conviction decision (STALK):')
    d = Decision('B', 'TATASTEEL', 'STALK', 'Module 1 - Conviction Scoring')
    d.add_signal('Multi-Engine',       3, 0, 'not in C or D')
    d.add_signal('Durability Fortress',2, 0, 'Dur 75, needs >75')
    d.add_signal('Momentum Surge',     2, 2, 'Mom 71')
    d.add_signal('Sector Safe',        1, 0, 'Metals 32% of book')
    d.add_signal('Volume Confirm',     1, 1, 'delivery above avg')
    d.add_signal('Fresh Qualifier',    1, 1, 'first appearance')
    d.set_margin('points to STRIKE', -2)
    d.set_counterfactual('STRIKE if Metals drops below 30% OR Durability > 75')
    print(' ', d.reason_string())

    # --- Test 2: a trigger-based exit decision (Engine C Path B) ---
    print('\nTest 2 - Engine C thesis-break exit:')
    e = Decision('C', 'SOMECO', 'EXIT', 'Module 2B - Thesis-Break')
    e.add_fact('Trigger', 'Quality Collapse')
    e.add_fact('Piotroski', '4 (threshold <5)')
    e.add_fact('Held', '7 months')
    e.add_fact('P&L at exit', '+6%')
    e.set_margin('Piotroski below threshold by', 1)
    e.set_counterfactual('would NOT have exited if Piotroski had stayed >= 5')
    print(' ', e.reason_string())

    # --- Test 3: incomplete decision is rejected ---
    print('\nTest 3 - incomplete decision (no counterfactual):')
    f = Decision('D', 'TESTCO', 'INCUBATE', 'Module 1')
    f.add_signal('Elite Growth', 2, 2, '3Yr growth 30%')
    f.set_margin('points to threshold', 1)
    # deliberately NOT setting counterfactual
    ok, missing = f.validate()
    print(f'  validate() -> ok={ok}, missing={missing}')
    try:
        f.reason_string()
        print('  ERROR: incomplete reason string was allowed!')
    except ValueError as ex:
        print(f'  Correctly rejected: {ex}')

    # --- Test 4: structured dict output ---
    print('\nTest 4 - structured dict (for journal/dashboard):')
    dd = d.as_dict()
    print(f"  ticker={dd['ticker']}  verdict={dd['verdict']}  "
          f"score={dd['score']}/{dd['max_score']}")
    print(f"  signals logged: {len(dd['signals'])}")
    print(f"  reason_string present: {bool(dd['reason_string'])}")

    print('\n' + '=' * 60)
    print('Self-test complete. The reasoning engine builds complete,')
    print('auditable reason strings and rejects incomplete decisions.')
    print('=' * 60)
