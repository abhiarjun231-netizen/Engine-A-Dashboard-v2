"""
portfolio_assignment.py
Parthsarthi Capital - Phase 5, Item 5.3
PORTFOLIO MASTER - THE ASSIGNMENT RULE.

The problem this solves:
A stock can qualify on more than one engine's screener at the same
time. On the May 16, 2026 data, eleven stocks qualified across both
the C2 and D1 screeners. Without a rule, three engines would each
try to buy the same name - triple-buying, triple concentration,
and three conflicting exit strategies for one position.

The Portfolio Master fix - the ASSIGNMENT RULE:
A multi-qualifying stock is assigned to exactly ONE engine, by a
fixed priority order:

  Priority 1 (highest) : D - Compounders   - longest-horizon, highest-
                                             conviction thesis
  Priority 2           : C - Value         - defined re-rating thesis
  Priority 3 (lowest)  : B - Momentum      - shortest-horizon thesis

The stock is bought ONCE, sized ONCE, by its assigned engine. The
fact it also qualified elsewhere is NOT wasted - it becomes the
Multi-Engine +3 conviction signal in the owning engine's score.

Multi-qualification is a CONVICTION REWARD, never a licence to
multiply the position. This module decides, for any stock, which
engine owns it - and exposes the cross-qualification set that each
engine's conviction module needs for its Multi-Engine signal.
"""

from reasoning_engine import Decision


# fixed priority order - highest priority first
ASSIGNMENT_PRIORITY = ['D', 'C', 'B']

ENGINE_NAME = {'B': 'Momentum', 'C': 'Value', 'D': 'Compounders'}


def assign_engine(qualifying_engines):
    """
    Given the set of engines a stock qualifies on, return the single
    engine that owns it, by the D > C > B priority order.

    qualifying_engines - iterable of engine codes, e.g. {'C', 'D'}
    Returns the owning engine code, or None if the set is empty.
    """
    quals = set(qualifying_engines)
    for eng in ASSIGNMENT_PRIORITY:
        if eng in quals:
            return eng
    return None


def assignment_decision(ticker, qualifying_engines):
    """
    Produce a Decision assigning a stock to its owning engine and
    describing the cross-qualification.

    Returns a Decision whose verdict is 'ASSIGN-<engine>'.
    """
    quals = set(qualifying_engines)
    owner = assign_engine(quals)

    if owner is None:
        d = Decision('PM', ticker, 'ASSIGN-NONE',
                     'Portfolio Master - Assignment Rule')
        d.add_fact('Issue', 'stock qualifies on no engine screener')
        d.set_margin('nothing to assign', 0)
        d.set_counterfactual('a stock must qualify on at least one engine '
                              'screener to be assigned')
        return d

    others = sorted(quals - {owner})
    multi = len(quals) > 1

    d = Decision('PM', ticker, f'ASSIGN-{owner}',
                 'Portfolio Master - Assignment Rule')
    d.add_fact('Qualifies on', ', '.join(sorted(quals)))
    d.add_fact('Assigned to', f'Engine {owner} ({ENGINE_NAME[owner]})')
    if multi:
        d.add_fact('Also qualified on',
                   ', '.join(f'{e} ({ENGINE_NAME[e]})' for e in others))
        d.add_fact('Multi-Engine signal',
                   f'+3 conviction in Engine {owner} - NOT a second buy')
    else:
        d.add_fact('Multi-Engine signal', 'none - single-engine qualifier')

    # margin = how many engines deep the priority had to go
    depth = ASSIGNMENT_PRIORITY.index(owner)
    d.set_margin('priority rank of the owning engine', depth + 1)

    if multi:
        d.set_counterfactual(
            f'the stock is bought once by Engine {owner} and owned by it '
            f'for its entire lifecycle; the cross-qualification only '
            f'feeds the Multi-Engine +3 conviction signal - it is never '
            f'a reason to buy the stock again in {", ".join(others)}')
    else:
        d.set_counterfactual(
            f'a single-engine qualifier is simply owned by Engine {owner}; '
            f'if it later also qualified elsewhere, ownership would not '
            f'change - the assignment is fixed at first entry')
    return d


def cross_qualification_sets(screener_membership):
    """
    Build, for each engine, the set of tickers that ALSO qualify on
    another engine - the input each engine's conviction module needs
    for its Multi-Engine signal.

    screener_membership - dict {engine: set_of_tickers}, e.g.
        {'B': {...}, 'C': {...}, 'D': {...}}

    Returns dict {engine: set_of_tickers_also_in_another_engine}.
    """
    out = {}
    for eng, tickers in screener_membership.items():
        others = set()
        for other_eng, other_tickers in screener_membership.items():
            if other_eng != eng:
                others |= other_tickers
        out[eng] = set(tickers) & others
    return out


# ---- self-test ----
if __name__ == '__main__':
    print('=' * 64)
    print('PORTFOLIO MASTER - THE ASSIGNMENT RULE (5.3) - self-test')
    print('=' * 64)

    # Test 1: priority order
    print('\nTest 1 - assignment by D > C > B priority:')
    for quals in [{'B'}, {'C'}, {'D'}, {'B', 'C'}, {'C', 'D'},
                  {'B', 'D'}, {'B', 'C', 'D'}]:
        owner = assign_engine(quals)
        print(f'  qualifies on {str(sorted(quals)):20} -> Engine {owner}')

    # Test 2: a stock qualifying in C and D -> assigned to D
    print('\nTest 2 - JSWSTEEL qualifies in C and D:')
    d = assignment_decision('JSWSTEEL', {'C', 'D'})
    print(f'  verdict: {d.verdict}')
    print(' ', d.reason_string())

    # Test 3: a single-engine qualifier
    print('\nTest 3 - PTC qualifies in C only:')
    d = assignment_decision('PTC', {'C'})
    print(f'  verdict: {d.verdict}')
    print(' ', d.reason_string())

    # Test 4: a triple-qualifier
    print('\nTest 4 - HINDZINC qualifies in B, C and D:')
    d = assignment_decision('HINDZINC', {'B', 'C', 'D'})
    print(f'  verdict: {d.verdict}')
    print(' ', d.reason_string())

    # Test 5: cross-qualification sets for the conviction modules
    print('\nTest 5 - cross-qualification sets (Multi-Engine signal input):')
    membership = {
        'B': {'HINDCOPPER', 'JSWSTEEL', 'HINDZINC'},
        'C': {'JSWSTEEL', 'PTC', 'HINDZINC'},
        'D': {'HINDZINC', 'FORCEMOT', 'JSWSTEEL'},
    }
    cross = cross_qualification_sets(membership)
    for eng in ['B', 'C', 'D']:
        print(f'  Engine {eng}: also-qualifies-elsewhere = {sorted(cross[eng])}')

    print('\n' + '=' * 64)
    print('Self-test complete. A multi-qualifying stock is assigned to')
    print('ONE engine by D > C > B priority, bought once; the cross-')
    print('qualification feeds the Multi-Engine +3 conviction signal.')
    print('=' * 64)
