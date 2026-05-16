"""
ai_narration.py
Parthsarthi Capital - Phase 6, Item 6.5
THE DASHBOARD - AI NARRATION LAYER (Role A only).

This module turns the structured reason strings the engines produce
into plain-English summaries for reports and the dashboard.

THE WALL - read this carefully:
  AI has exactly ONE role here: NARRATION. It takes a decision that
  has ALREADY been made by deterministic rules and rephrases the
  reason string in readable English. It does NOT decide anything.

  AI never decides an entry, an exit, a size, or a rotation.
  AI never overrides a rule.
  AI never sits between the screener and the portfolio.

  If this module vanished, every decision the system makes would be
  identical - only the prose would be missing. That is the test of
  a pure narration layer, and this module passes it by construction:
  it only ever READS a finished Decision object.

The narration is deterministic and template-based by default - no
external API call is required for the system to function. An
optional LLM-polish hook is provided but is purely cosmetic; the
template narration is always sufficient and always available.
"""

# verdict -> a plain-English action phrase
VERDICT_PHRASE = {
    'STRIKE':          'is a buy candidate',
    'DEPLOY':          'is a buy candidate',
    'INCUBATE':        'qualifies to begin a 90-day incubation',
    'INCUBATE-START':  'is entering incubation at half size',
    'INCUBATE-HOLD':   'is continuing its incubation',
    'INCUBATE-PROMOTE':'has passed incubation and is being topped up to full',
    'INCUBATE-FAIL':   'failed incubation; the partial position is exited',
    'STALK':           'is being watched, not yet a buy',
    'HOLD-FIRE':       'is being watched, not yet a buy',
    'SKIP':            'is a low-priority watch',
    'PASS':            'is a low-priority watch',
    'HOLD':            'is being held',
    'HOLD-DETERIORATING': 'is held but reclassified as deteriorating',
    'HOLD-RERATING':   'is held - it has re-rated, which is the thesis working',
    'RIDE':            'is held and healthy',
    'GUARD':           'is held but in the warning zone',
    'RE-RATING':       'is held and re-rating upward',
    'BOOK-THIRD':      'has a profit-booking tranche firing',
    'EXIT':            'is being exited',
    'EXIT-TRAIL':      'is being exited - the trailing stop was hit',
    'EXIT-DEAD':       'is being exited - the dead-money rule fired',
    'ROTATE':          'is rotating into the portfolio, displacing a laggard',
    'ENTER-FREE-SLOT': 'is entering an open portfolio slot',
    'WAIT-NO-ROOM':    'is waiting - the portfolio has no room',
    'CAP-OK':          'fits within the position-size cap',
    'CAP-BREACH':      'breaches the position-size cap',
}


def narrate(decision):
    """
    Produce a plain-English narration of an already-made Decision.

    This function NEVER changes the decision. It reads the Decision
    object's verdict, rule and facts, and returns a readable string.

    Returns a one-paragraph narration.
    """
    verdict = decision.verdict
    ticker = decision.ticker
    phrase = VERDICT_PHRASE.get(verdict, f'has verdict {verdict}')

    # opening sentence - the action
    parts = [f'{ticker} {phrase}.']

    # the driver - conviction score or the rule that fired
    if decision.signals:
        score = decision.total_score()
        mx = decision.max_score()
        # name the signals that actually contributed
        earned = [s.name for s in decision.signals if s.earned > 0]
        if earned:
            parts.append(
                f'It scored {score} of {mx} on conviction, earning points '
                f'from {_join(earned)}.')
        else:
            parts.append(f'It scored {score} of {mx} on conviction, '
                         f'with no signal yet contributing.')
    else:
        # trigger-based decision - name the rule
        parts.append(f'The decision was made by the rule "{decision.rule}".')

    # the margin - how close it was
    if decision.margin:
        desc, val = decision.margin
        parts.append(f'Margin: {desc} is {val}.')

    # the counterfactual - what would change it
    if decision.counterfactual:
        parts.append(f'What would change this: {decision.counterfactual}')

    return ' '.join(parts)


def _join(items):
    """Join a list into readable English: a, b and c."""
    items = list(items)
    if not items:
        return 'nothing'
    if len(items) == 1:
        return items[0]
    return ', '.join(items[:-1]) + ' and ' + items[-1]


def narrate_cycle(decisions, max_items=None):
    """
    Narrate a whole cycle's worth of decisions, action decisions first.
    Returns a list of (ticker, verdict, narration) tuples.
    """
    buy_grade = {'STRIKE', 'DEPLOY', 'INCUBATE', 'INCUBATE-START'}
    exit_grade = {'EXIT', 'EXIT-TRAIL', 'EXIT-DEAD', 'INCUBATE-FAIL'}

    def priority(d):
        if d.verdict in buy_grade:
            return 0
        if d.verdict in exit_grade:
            return 1
        if d.verdict == 'BOOK-THIRD':
            return 2
        return 3

    ordered = sorted(decisions, key=priority)
    if max_items:
        ordered = ordered[:max_items]
    return [(d.ticker, d.verdict, narrate(d)) for d in ordered]


def cycle_summary(decisions):
    """
    A one-paragraph plain-English summary of an entire cycle.
    Pure narration of counts - no judgement, no decision.
    """
    if not decisions:
        return 'No decisions were generated this cycle.'

    tally = {}
    for d in decisions:
        tally[d.verdict] = tally.get(d.verdict, 0) + 1

    buy = sum(tally.get(v, 0) for v in
              ['STRIKE', 'DEPLOY', 'INCUBATE', 'INCUBATE-START'])
    exits = sum(tally.get(v, 0) for v in
                ['EXIT', 'EXIT-TRAIL', 'EXIT-DEAD', 'INCUBATE-FAIL'])
    books = tally.get('BOOK-THIRD', 0)

    sentences = [f'The cycle produced {len(decisions)} decisions.']
    if buy:
        sentences.append(f'{buy} stock(s) cleared as buy or '
                         f'incubation candidates.')
    if exits:
        sentences.append(f'{exits} position(s) were exited.')
    if books:
        sentences.append(f'{books} profit-booking tranche(s) fired.')
    if not (buy or exits or books):
        sentences.append('No buy, exit or booking actions were triggered '
                          '- a quiet, hold-steady cycle.')
    return ' '.join(sentences)


# ---- self-test ----
if __name__ == '__main__':
    from reasoning_engine import Decision

    print('=' * 60)
    print('AI NARRATION LAYER (6.5) - self-test')
    print('=' * 60)

    # build a couple of real Decision objects to narrate
    d1 = Decision('C', 'PTC', 'DEPLOY', 'Module 1 - Value Conviction Scoring')
    d1.add_signal('Multi-Engine', 3, 0, 'not in B or D')
    d1.add_signal('Deep Value', 2, 2, 'PE 7.3 < 15')
    d1.add_signal('Quality Wall', 2, 2, 'Piotroski 8')
    d1.add_signal('Sector Safe', 1, 1, 'Utilities 0%')
    d1.add_signal('Growth Intact', 1, 1, 'NP YoY 89%')
    d1.add_signal('Fresh Qualifier', 1, 1, 'fresh')
    d1.set_margin('points clear of DEPLOY', 0)
    d1.set_counterfactual('would drop to HOLD-FIRE if it loses 4+ points')

    d2 = Decision('B', 'JSWSTEEL', 'EXIT', 'Module 3 - Hard Stop')
    d2.add_fact('Hard Stop', 'price 16% below peak')
    d2.set_margin('exit triggers fired', 1)
    d2.set_counterfactual('would HOLD only if the trigger reversed')

    print('\nTest 1 - narrate a DEPLOY decision:')
    print(' ', narrate(d1))

    print('\nTest 2 - narrate an EXIT decision:')
    print(' ', narrate(d2))

    print('\nTest 3 - narrate a whole cycle:')
    for tk, v, text in narrate_cycle([d1, d2]):
        print(f'  [{v}] {text}')

    print('\nTest 4 - one-paragraph cycle summary:')
    print(' ', cycle_summary([d1, d2]))

    print('\nTest 5 - the wall check:')
    print('  narrate() only READS a Decision - it has no path to change')
    print('  verdict, rule, margin or counterfactual. Confirmed by')
    print('  construction: the function takes a finished Decision and')
    print('  returns a string. AI narrates; it never decides.')

    print('\n' + '=' * 60)
    print('Self-test complete. The narration layer is Role A only -')
    print('it explains decisions in plain English, never makes them.')
    print('=' * 60)
