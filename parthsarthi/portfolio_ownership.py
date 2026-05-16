"""
portfolio_ownership.py
Parthsarthi Capital - Phase 5, Item 5.4
PORTFOLIO MASTER - TOTAL-OWNERSHIP ENFORCEMENT.

The assignment rule (5.3) decides WHICH engine owns a stock at
entry. This module enforces what that ownership MEANS - and closes
the exit-conflict hole.

The principle:
  The engine that owns a stock at entry owns its ENTIRE lifecycle -
  entry, sizing, monitoring, AND exit. The other engine's parameters
  never apply, even though the stock also qualified there.

Why this matters - the exit conflict:
  Engine C exits a stock by PE-expansion booking (sell in thirds).
  Engine D never books profit (hold for years, exit only on thesis
  break). If JSWSTEEL is assigned to D but also qualified in C, it
  CANNOT have both exit rules. Total ownership resolves it: JSWSTEEL
  is managed entirely as a D compounder. Engine C's booking rules
  never touch it.

The hard rule enforced here:
  NO MID-LIFE ENGINE TRANSFERS. EVER.
  A position belongs to its owning engine from entry to exit. If a
  D-owned stock later stops qualifying for D but still qualifies for
  C, it does NOT transfer to C. It stays a D position under D's exit
  rules. If D's thesis-break fires, it exits fully. Any later C-screen
  qualification is a FRESH decision - new entry, new assignment, new
  lifecycle, after cooldown.

This module validates ownership operations and rejects any attempt
to transfer or cross-manage a live position.
"""

from reasoning_engine import Decision


class OwnershipViolation(Exception):
    """Raised when an operation would breach total-ownership."""
    pass


def owning_engine(ticker, positions):
    """
    Return the engine that owns a held ticker, or None if not held.
    positions - list of {ticker, engine, ...}
    """
    for p in positions:
        if p['ticker'] == ticker:
            return p['engine']
    return None


def validate_management(ticker, acting_engine, positions):
    """
    Validate that `acting_engine` is allowed to manage `ticker`.
    Any engine other than the owner attempting to act on a live
    position is an ownership violation.

    Returns a Decision: 'OWNERSHIP-OK' or 'OWNERSHIP-VIOLATION'.
    """
    owner = owning_engine(ticker, positions)

    if owner is None:
        # not held - no ownership to violate; this is a fresh-entry path
        d = Decision('PM', ticker, 'OWNERSHIP-OK',
                     'Portfolio Master - Ownership (not held)')
        d.add_fact('Status', 'stock is not currently held')
        d.add_fact('Acting engine', acting_engine)
        d.add_fact('Note', 'fresh entry - the assignment rule (5.3) governs')
        d.set_margin('no live position to protect', 0)
        d.set_counterfactual('once entered, the position is owned solely '
                              'by its assigned engine')
        return d

    if acting_engine == owner:
        d = Decision('PM', ticker, 'OWNERSHIP-OK',
                     'Portfolio Master - Ownership')
        d.add_fact('Owner', f'Engine {owner}')
        d.add_fact('Acting engine', f'Engine {acting_engine}')
        d.add_fact('Status', 'acting engine is the owner - management '
                             'permitted')
        d.set_margin('ownership confirmed', 1)
        d.set_counterfactual('only the owning engine may manage a live '
                              'position - entry, monitoring and exit')
        return d

    # a non-owner is attempting to act - violation
    d = Decision('PM', ticker, 'OWNERSHIP-VIOLATION',
                 'Portfolio Master - Ownership (violation)')
    d.add_fact('Owner', f'Engine {owner}')
    d.add_fact('Acting engine', f'Engine {acting_engine}')
    d.add_fact('Status', f'Engine {acting_engine} attempted to manage a '
                         f'position owned by Engine {owner}')
    d.add_fact('Decision', 'REJECTED - no cross-engine management')
    d.set_margin('ownership breach blocked', 0)
    d.set_counterfactual(
        f'Engine {acting_engine} may never apply its rules to a '
        f'position owned by Engine {owner}; the owning engine governs '
        f'the entire lifecycle including exit')
    return d


def validate_transfer(ticker, from_engine, to_engine, positions):
    """
    Validate a proposed mid-life engine transfer. ALL transfers are
    rejected - this is the hard rule. The function exists so the
    rejection is explicit and logged, not silent.

    Returns a Decision: always 'TRANSFER-REJECTED' for a live position.
    """
    owner = owning_engine(ticker, positions)

    d = Decision('PM', ticker, 'TRANSFER-REJECTED',
                 'Portfolio Master - No Mid-Life Transfers')
    d.add_fact('Current owner', f'Engine {owner}' if owner else 'not held')
    d.add_fact('Attempted transfer', f'{from_engine} -> {to_engine}')
    d.add_fact('Decision', 'REJECTED - mid-life engine transfers are '
                           'never permitted')
    d.set_margin('transfer blocked', 0)
    d.set_counterfactual(
        'a position belongs to its owning engine from entry to exit. '
        'If it stops qualifying for its engine, the engine exits it '
        'fully. Any later qualification elsewhere is a FRESH decision '
        '- new entry, new assignment, new lifecycle, after cooldown. '
        'Transfers would destroy the audit trail and create the very '
        'two-exit-rule conflict total ownership exists to prevent')
    return d


def exit_rule_for(ticker, positions):
    """
    State which engine's exit logic governs a held position.
    This is a clarity helper for the dashboard - it makes explicit
    that exit logic follows ownership, never qualification.
    """
    owner = owning_engine(ticker, positions)
    rules = {
        'B': 'Engine B exit triggers + trailing-stop ladder',
        'C': 'Engine C PE-expansion booking + thesis-break (Path B)',
        'D': 'Engine D thesis-break only - never books profit',
    }
    return owner, rules.get(owner, 'not held - no exit rule')


# ---- self-test ----
if __name__ == '__main__':
    print('=' * 64)
    print('PORTFOLIO MASTER - TOTAL-OWNERSHIP ENFORCEMENT (5.4) - self-test')
    print('=' * 64)

    positions = [
        {'ticker': 'JSWSTEEL', 'engine': 'D'},   # owned by D
        {'ticker': 'PTC', 'engine': 'C'},        # owned by C
        {'ticker': 'HINDCOPPER', 'engine': 'B'}, # owned by B
    ]

    # Test 1: owner manages its own position -> OK
    print('\nTest 1 - Engine D manages JSWSTEEL (which D owns):')
    d = validate_management('JSWSTEEL', 'D', positions)
    print(f'  verdict: {d.verdict}')
    print(' ', d.reason_string())

    # Test 2: a non-owner tries to manage -> VIOLATION
    print('\nTest 2 - Engine C tries to manage JSWSTEEL (owned by D):')
    d = validate_management('JSWSTEEL', 'C', positions)
    print(f'  verdict: {d.verdict}')
    print(' ', d.reason_string())

    # Test 3: a mid-life transfer attempt -> REJECTED
    print('\nTest 3 - attempt to transfer JSWSTEEL from D to C:')
    d = validate_transfer('JSWSTEEL', 'D', 'C', positions)
    print(f'  verdict: {d.verdict}')
    print(' ', d.reason_string())

    # Test 4: managing a stock not held -> OK (fresh entry path)
    print('\nTest 4 - Engine B acts on a stock not currently held:')
    d = validate_management('NEWCO', 'B', positions)
    print(f'  verdict: {d.verdict}')
    print(' ', d.reason_string())

    # Test 5: exit rule follows ownership
    print('\nTest 5 - which exit logic governs each held position:')
    for tk in ['JSWSTEEL', 'PTC', 'HINDCOPPER']:
        owner, rule = exit_rule_for(tk, positions)
        print(f'  {tk:13} owned by {owner} -> {rule}')

    print('\n' + '=' * 64)
    print('Self-test complete. The owning engine governs the entire')
    print('lifecycle. No cross-engine management, no mid-life transfers.')
    print('Exit logic follows ownership, never qualification.')
    print('=' * 64)
