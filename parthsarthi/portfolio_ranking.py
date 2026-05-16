"""
portfolio_ranking.py
Parthsarthi Capital - Phase 5, Item 5.6
PORTFOLIO MASTER - FULL-PORTFOLIO RANKING & ROTATION.

Engine C has its own ranking module (3.5) that rotates within
Engine C's slots. This module is the PORTFOLIO-LEVEL version: when
the whole book is at the holdings ceiling, it decides whether a
strong new candidate should displace the single weakest position
ANYWHERE across B, C and D.

The rules build on Engine C's rotation logic, raised to the
portfolio level:
  - Rank every held position, all engines, weakest conviction first.
  - A new candidate may rotate out the weakest holding only if:
       it beats that holding by 3+ conviction points, AND
       the weakest holding is not actively WORKING.
  - "Working" is engine-specific:
       Engine B  - stage RIDE
       Engine C  - stage RE-RATING
       Engine D  - any position past incubation that is on-screen
  - Incumbency wins ties; a working position is never rotated out.
  - Ownership note: the candidate enters under its OWN assigned
    engine (assignment rule 5.3); the rotated-out holding exits
    under ITS engine's exit logic. Rotation never transfers a
    position between engines.

This is the layer that makes capital genuinely scarce across the
WHOLE portfolio, not just within one engine.
"""

from reasoning_engine import Decision


ROTATION_GAP = 3       # conviction-point advantage needed to rotate

# stages that count as "actively working" - never rotated out
WORKING_STAGES = {
    'B': {'RIDE'},
    'C': {'RE-RATING'},
    'D': {'HELD', 'IMMORTAL', 'LEGENDARY', 'ESTABLISHED', 'SEEDLING'},
    # Engine D: a confirmed compounder past incubation is always
    # "working" - it is a multi-year hold, never rotated for a
    # momentum or value candidate. Only its own thesis-break exits it.
}


def is_working(position):
    """True if a held position is actively working and must not be rotated."""
    eng = position.get('engine')
    stage = position.get('stage')
    return stage in WORKING_STAGES.get(eng, set())


def rank_portfolio(positions):
    """All held positions, weakest conviction first."""
    return sorted(positions, key=lambda p: p.get('conviction', 0))


def evaluate_portfolio_rotation(new_ticker, new_engine, new_conviction,
                                positions, holdings_hard_max=30):
    """
    Decide, at the portfolio level, whether a new candidate enters
    and - if the book is full - whether it rotates out the weakest
    non-working holding anywhere across B/C/D.

    Returns a Decision with one of:
      ENTER-FREE-SLOT       - book not full; candidate enters
      ROTATE                - book full; candidate displaces the
                              weakest non-working holding
      WAIT-PORTFOLIO-FULL   - book full; no rotation justified
    """
    n_held = len(positions)

    # ---- free slot ----
    if n_held < holdings_hard_max:
        d = Decision('PM', new_ticker, 'ENTER-FREE-SLOT',
                     'Portfolio Master - Ranking (free slot)')
        d.add_fact('New candidate', f'{new_ticker} (Engine {new_engine}, '
                   f'conviction {new_conviction}/10)')
        d.add_fact('Portfolio', f'{n_held}/{holdings_hard_max} - slot available')
        d.set_margin('open slots in the portfolio', holdings_hard_max - n_held)
        d.set_counterfactual('the candidate enters under its own assigned '
                              'engine - no rotation needed')
        return d

    # ---- book full: find the weakest non-working holding ----
    ranked = rank_portfolio(positions)
    weakest_rotatable = None
    for p in ranked:
        if not is_working(p):
            weakest_rotatable = p
            break

    # every holding is working - nothing can be rotated
    if weakest_rotatable is None:
        d = Decision('PM', new_ticker, 'WAIT-PORTFOLIO-FULL',
                     'Portfolio Master - Ranking (all positions working)')
        d.add_fact('New candidate', f'{new_ticker} (conviction {new_conviction}/10)')
        d.add_fact('Portfolio', f'{n_held}/{holdings_hard_max} - all working')
        d.add_fact('Decision', 'no rotation - every held position is '
                               'actively working')
        d.set_margin('candidate waits in WATCH', 0)
        d.set_counterfactual('a working position is never rotated out - '
                              'the candidate waits for a non-working slot')
        return d

    gap = new_conviction - weakest_rotatable.get('conviction', 0)

    # ---- gap large enough -> ROTATE ----
    if gap >= ROTATION_GAP:
        d = Decision('PM', new_ticker, 'ROTATE',
                     'Portfolio Master - Ranking (rotation)')
        d.add_fact('New candidate', f'{new_ticker} (Engine {new_engine}, '
                   f'conviction {new_conviction}/10)')
        d.add_fact('Weakest non-working holding',
                   f"{weakest_rotatable['ticker']} (Engine "
                   f"{weakest_rotatable['engine']}, "
                   f"{weakest_rotatable.get('conviction')}/10, "
                   f"stage {weakest_rotatable.get('stage')})")
        d.add_fact('Conviction gap', f'+{gap} (threshold +{ROTATION_GAP})')
        d.add_fact('Action', f"EXIT {weakest_rotatable['ticker']} under "
                   f"Engine {weakest_rotatable['engine']} exit logic; "
                   f"ENTER {new_ticker} under Engine {new_engine}")
        d.set_margin('conviction gap past the rotation threshold by',
                     gap - ROTATION_GAP)
        d.set_counterfactual(
            f'would WAIT if the gap were below +{ROTATION_GAP} or if the '
            f'weakest holding were working; rotation never transfers a '
            f'position - each side moves under its own engine')
        return d

    # ---- gap too small -> incumbency wins ----
    d = Decision('PM', new_ticker, 'WAIT-PORTFOLIO-FULL',
                 'Portfolio Master - Ranking (gap too small)')
    d.add_fact('New candidate', f'{new_ticker} (conviction {new_conviction}/10)')
    d.add_fact('Weakest non-working holding',
               f"{weakest_rotatable['ticker']} "
               f"({weakest_rotatable.get('conviction')}/10)")
    d.add_fact('Conviction gap', f'+{gap} (needs +{ROTATION_GAP})')
    d.add_fact('Decision', 'incumbency wins - candidate waits in WATCH')
    d.set_margin('conviction gap short of the rotation threshold by',
                 ROTATION_GAP - gap)
    d.set_counterfactual(
        f'-> ROTATE only if the candidate beats the weakest non-working '
        f'holding by +{ROTATION_GAP} or more; churn has a cost')
    return d


# ---- self-test ----
if __name__ == '__main__':
    print('=' * 64)
    print('PORTFOLIO MASTER - FULL-PORTFOLIO RANKING & ROTATION (5.6)')
    print('=' * 64)

    # a portfolio spanning all three engines
    def make_book(n):
        book = []
        for i in range(n):
            eng = 'BCD'[i % 3]
            # give a spread of convictions and stages
            conv = 5 + (i % 4)
            if eng == 'B':
                stage = 'RIDE' if i % 2 == 0 else 'GUARD'
            elif eng == 'C':
                stage = 'RE-RATING' if i % 3 == 0 else 'HELD'
            else:
                stage = 'HELD'   # D positions are always "working"
            book.append({'ticker': f'STK{i}', 'engine': eng,
                         'conviction': conv, 'stage': stage})
        return book

    # Test 1: free slot
    print('\nTest 1 - portfolio of 20, free slot:')
    d = evaluate_portfolio_rotation('NEWCO', 'C', 8, make_book(20))
    print(f'  verdict: {d.verdict}')
    print(' ', d.reason_string())

    # Test 2: full book, strong candidate, a weak non-working holding exists
    print('\nTest 2 - full book (30), strong candidate conviction 9:')
    book = make_book(30)
    # ensure there is a weak, non-working holding
    book[1] = {'ticker': 'LAGGARD', 'engine': 'C', 'conviction': 4,
               'stage': 'HELD'}
    d = evaluate_portfolio_rotation('STRONGCO', 'D', 9, book)
    print(f'  verdict: {d.verdict}')
    print(' ', d.reason_string())

    # Test 3: full book, gap too small
    print('\nTest 3 - full book, candidate conviction 6 (gap too small):')
    d = evaluate_portfolio_rotation('OKAYCO', 'B', 6, book)
    print(f'  verdict: {d.verdict}')
    print(' ', d.reason_string())

    # Test 4: full book, every position is working
    print('\nTest 4 - full book, every position working:')
    all_working = [{'ticker': f'W{i}', 'engine': 'D', 'conviction': 5,
                    'stage': 'HELD'} for i in range(30)]
    d = evaluate_portfolio_rotation('STRONGCO', 'C', 10, all_working)
    print(f'  verdict: {d.verdict}')
    print(' ', d.reason_string())

    print('\n' + '=' * 64)
    print('Self-test complete. At the holdings ceiling, a strong')
    print('candidate displaces the weakest NON-WORKING holding anywhere')
    print('across B/C/D - and rotation never transfers between engines.')
    print('=' * 64)
