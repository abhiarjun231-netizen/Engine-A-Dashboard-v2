"""
engine_c_ranking.py
Parthsarthi Capital - Phase 3, Item 3.5
ENGINE C - RANKING & ROTATION (Module 5).

The institutional discipline: capital is scarce. This module answers
the question Engine C's entry filter alone cannot - "when the
portfolio is full and a new candidate clears conviction, what now?"

The rotation rule (from the Engine C framework):
  - Identify the weakest current holding by conviction score.
  - If the new candidate beats the weakest holding by 3 OR MORE
    conviction points, AND the weakest holding is not itself in
    RE-RATING (not currently working) - ROTATE: exit the laggard,
    deploy into the new candidate.
  - If the gap is under 3 points, the new candidate waits in WATCH.
    Incumbency wins ties - churn has a cost.
  - A position in RE-RATING is never rotated out. Never sell a
    winner to chase a maybe.

This module turns Engine C from a screener-follower into a portfolio:
every slot must continuously justify itself.
"""

from reasoning_engine import Decision


# minimum conviction-point advantage a challenger needs to force a rotation
ROTATION_GAP = 3
# the holdings ceiling per engine
MAX_POSITIONS = 10


def rank_holdings(holdings):
    """
    Sort current holdings weakest-first by conviction score.
    holdings: list of {ticker, conviction, stage}
    """
    return sorted(holdings, key=lambda h: h.get('conviction', 0))


def evaluate_rotation(new_ticker, new_conviction, holdings):
    """
    Decide whether a new DEPLOY-grade candidate should enter, and if
    the portfolio is full, whether it rotates out a weak holding.

    holdings - list of {ticker, conviction, stage} for current Engine C
               positions. 'stage' is the value-lifecycle stage.

    Returns a Decision with one of:
      ENTER-FREE-SLOT - portfolio not full, candidate simply enters
      ROTATE          - portfolio full; candidate replaces a laggard
      WAIT-NO-ROOM    - portfolio full; candidate not strong enough to
                        rotate, waits in WATCH
    """
    n_held = len(holdings)

    # ---- free slot available ----
    if n_held < MAX_POSITIONS:
        d = Decision('C', new_ticker, 'ENTER-FREE-SLOT',
                     'Module 5 - Ranking (free slot)')
        d.add_fact('New candidate conviction', f'{new_conviction}/10')
        d.add_fact('Portfolio', f'{n_held}/{MAX_POSITIONS} - slot available')
        d.set_margin('open slots remaining', MAX_POSITIONS - n_held)
        d.set_counterfactual('no rotation needed - the candidate enters '
                              'directly into an open slot')
        return d

    # ---- portfolio full: consider rotation ----
    ranked = rank_holdings(holdings)
    weakest = ranked[0]
    gap = new_conviction - weakest.get('conviction', 0)
    weakest_working = weakest.get('stage') == 'RE-RATING'

    # weakest holding is actively working - never rotate it out
    if weakest_working:
        d = Decision('C', new_ticker, 'WAIT-NO-ROOM',
                     'Module 5 - Ranking (weakest is working)')
        d.add_fact('New candidate conviction', f'{new_conviction}/10')
        d.add_fact('Weakest holding', f"{weakest['ticker']} "
                   f"({weakest.get('conviction')}/10, stage RE-RATING)")
        d.add_fact('Decision', 'no rotation - the weakest holding is in '
                               'RE-RATING and is never rotated out')
        d.set_margin('candidate waits in WATCH', 0)
        d.set_counterfactual('never sell a winner to chase a maybe - the '
                              'candidate waits until a non-working slot frees up')
        return d

    # gap large enough to rotate
    if gap >= ROTATION_GAP:
        d = Decision('C', new_ticker, 'ROTATE',
                     'Module 5 - Ranking (rotation)')
        d.add_fact('New candidate conviction', f'{new_conviction}/10')
        d.add_fact('Weakest holding', f"{weakest['ticker']} "
                   f"({weakest.get('conviction')}/10, stage {weakest.get('stage')})")
        d.add_fact('Conviction gap', f'+{gap} (threshold +{ROTATION_GAP})')
        d.add_fact('Action', f"EXIT {weakest['ticker']}, DEPLOY {new_ticker}")
        d.set_margin('conviction gap past rotation threshold by',
                     gap - ROTATION_GAP)
        d.set_counterfactual(
            f'would WAIT if the gap were below +{ROTATION_GAP} '
            f'OR if {weakest["ticker"]} were in RE-RATING')
        return d

    # gap too small - incumbency wins
    d = Decision('C', new_ticker, 'WAIT-NO-ROOM',
                 'Module 5 - Ranking (gap too small)')
    d.add_fact('New candidate conviction', f'{new_conviction}/10')
    d.add_fact('Weakest holding', f"{weakest['ticker']} "
               f"({weakest.get('conviction')}/10, stage {weakest.get('stage')})")
    d.add_fact('Conviction gap', f'+{gap} (needs +{ROTATION_GAP} to rotate)')
    d.add_fact('Decision', 'incumbency wins - candidate waits in WATCH')
    d.set_margin('conviction gap short of rotation threshold by',
                 ROTATION_GAP - gap)
    d.set_counterfactual(
        f'-> ROTATE if the candidate scored +{ROTATION_GAP} or more above '
        f'the weakest holding; churn has a cost, ties go to the incumbent')
    return d


# ---- self-test ----
if __name__ == '__main__':
    print('=' * 64)
    print('ENGINE C RANKING & ROTATION (Module 5) - self-test')
    print('=' * 64)

    # Test 1: free slot - candidate just enters
    print('\nTest 1 - portfolio 6/10, free slot:')
    holdings_small = [
        {'ticker': 'PTC', 'conviction': 7, 'stage': 'HELD'},
        {'ticker': 'JSWSTEEL', 'conviction': 8, 'stage': 'RE-RATING'},
        {'ticker': 'SHARDACROP', 'conviction': 7, 'stage': 'HELD'},
        {'ticker': 'GESHIP', 'conviction': 6, 'stage': 'HELD'},
        {'ticker': 'HINDZINC', 'conviction': 7, 'stage': 'HELD'},
        {'ticker': 'FORCEMOT', 'conviction': 6, 'stage': 'HELD'},
    ]
    d = evaluate_rotation('NEWCO', 8, holdings_small)
    print(f'  verdict: {d.verdict}')
    print(' ', d.reason_string())

    # full portfolio of 10
    holdings_full = holdings_small + [
        {'ticker': 'FIEMIND', 'conviction': 5, 'stage': 'HELD'},
        {'ticker': 'GVPIL', 'conviction': 7, 'stage': 'HELD'},
        {'ticker': 'CHENNPETRO', 'conviction': 6, 'stage': 'HELD'},
        {'ticker': 'GOKULAGRO', 'conviction': 7, 'stage': 'HELD'},
    ]

    # Test 2: full portfolio, strong candidate -> ROTATE
    print('\nTest 2 - portfolio full (10/10), candidate conviction 9:')
    d = evaluate_rotation('STRONGCO', 9, holdings_full)
    print(f'  verdict: {d.verdict}')
    print(' ', d.reason_string())

    # Test 3: full portfolio, candidate gap too small -> WAIT
    print('\nTest 3 - portfolio full, candidate conviction 7 (gap +2):')
    d = evaluate_rotation('OKAYCO', 7, holdings_full)
    print(f'  verdict: {d.verdict}')
    print(' ', d.reason_string())

    # Test 4: weakest holding is RE-RATING -> never rotate it
    print('\nTest 4 - full portfolio, weakest holding is RE-RATING:')
    holdings_weak_working = [
        {'ticker': 'WORKINGCO', 'conviction': 5, 'stage': 'RE-RATING'},
    ] + [{'ticker': f'H{i}', 'conviction': 8, 'stage': 'HELD'}
         for i in range(9)]
    d = evaluate_rotation('STRONGCO', 9, holdings_weak_working)
    print(f'  verdict: {d.verdict}')
    print(' ', d.reason_string())

    print('\n' + '=' * 64)
    print('Self-test complete. Rotation fires only when a candidate beats')
    print('the weakest holding by 3+ points AND that holding is not')
    print('working. Incumbency wins ties; winners are never rotated out.')
    print('=' * 64)
