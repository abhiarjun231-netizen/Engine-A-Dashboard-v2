"""
portfolio_sizing.py
Parthsarthi Capital - Phase 5, Item 5.7
PORTFOLIO MASTER - POSITION SIZING.

The engine frameworks describe conviction-scaled sizing (a 10/10
conviction stock gets a bigger slice than a 7/10). The Portfolio
Master adds a maturity rule on top:

  Until the daily journal has VALIDATED that the conviction score
  actually predicts winners, every position is EQUAL-WEIGHTED.

Why: conviction-weighting amplifies the scoring model's errors. If
the score is wrong, conviction-weighting means you bet MORE on the
wrong thing. Equal-weight is the honest default until a track record
exists. The system starts in EQUAL-WEIGHT mode and is only switched
to CONVICTION-WEIGHT mode deliberately, once the journal earns it.

Sizing always respects two ceilings already built:
  - the engine's own capital budget (capital allocator, 5.1)
  - the 10% total-portfolio stock cap (stock cap, 5.2)

This module computes the rupee size for a new position, in whichever
mode is active, and never returns a size that breaches a ceiling.
"""

from reasoning_engine import Decision


# the two sizing modes
MODE_EQUAL      = 'EQUAL-WEIGHT'
MODE_CONVICTION = 'CONVICTION-WEIGHT'

# the per-stock master cap (mirrors portfolio_stockcap.py)
MASTER_STOCK_CAP_PCT = 10.0

# conviction-weight tiers (used only in CONVICTION-WEIGHT mode):
# conviction band -> fraction of the equal-weight slice
CONVICTION_TIERS = [
    (9, 1.30),    # conviction 9-10 -> 1.30x the equal slice
    (8, 1.15),    # conviction 8    -> 1.15x
    (7, 1.00),    # conviction 7    -> 1.00x (baseline)
]


def equal_weight_size(engine_budget, target_positions):
    """
    The equal-weight slice for one position in an engine.
    engine_budget    - the engine's total capital
    target_positions - the number of positions the engine targets
    """
    if target_positions <= 0:
        return 0.0
    return engine_budget / target_positions


def conviction_multiplier(conviction):
    """Multiplier on the equal slice, for CONVICTION-WEIGHT mode."""
    for floor, mult in CONVICTION_TIERS:
        if conviction >= floor:
            return mult
    return 1.00


def size_position(ticker, engine, conviction, engine_budget,
                  target_positions, total_equity, mode=MODE_EQUAL):
    """
    Compute the rupee size for a new position.

    mode - MODE_EQUAL (default) or MODE_CONVICTION.

    Returns a Decision carrying the sized amount and the reasoning.
    The size is capped at the 10% total-portfolio stock cap.
    """
    base = equal_weight_size(engine_budget, target_positions)
    stock_cap_value = total_equity * MASTER_STOCK_CAP_PCT / 100.0

    if mode == MODE_CONVICTION:
        mult = conviction_multiplier(conviction)
        raw_size = base * mult
        mode_note = (f'conviction-weighted: {mult:.2f}x the equal slice '
                     f'(conviction {conviction}/10)')
    else:
        mult = 1.00
        raw_size = base
        mode_note = ('equal-weighted: every position the same size until '
                     'the journal validates the conviction score')

    # apply the master stock cap
    capped = min(raw_size, stock_cap_value)
    was_capped = capped < raw_size

    d = Decision('PM', ticker, 'SIZE', 'Portfolio Master - Position Sizing')
    d.add_fact('Engine', engine)
    d.add_fact('Mode', mode)
    d.add_fact('Equal slice', f'{base:,.0f} '
               f'(budget {engine_budget:,.0f} / {target_positions} positions)')
    d.add_fact('Sizing basis', mode_note)
    d.add_fact('Raw size', f'{raw_size:,.0f}')
    if was_capped:
        d.add_fact('Stock cap applied',
                   f'capped to {capped:,.0f} (10% master cap)')
    d.add_fact('Final size', f'{capped:,.0f}')

    d.set_margin('headroom to the 10% stock cap',
                 round(stock_cap_value - capped, 0))
    if mode == MODE_EQUAL:
        d.set_counterfactual(
            'conviction-weighting is available but deliberately OFF - '
            'it is enabled only once the journal proves the conviction '
            'score predicts winners; equal-weight does not amplify a '
            'model error')
    else:
        d.set_counterfactual(
            'conviction-weighting is active - this should only be on '
            'after the journal has validated the conviction score; the '
            '10% stock cap still binds')
    return d


def recommend_mode(closed_trades, conviction_edge=None):
    """
    Advise which sizing mode the portfolio should be in.

    closed_trades   - number of closed trades in the journal
    conviction_edge - optional: measured win-rate gap between
                      high-conviction and low-conviction trades

    Returns a Decision. This is ADVISORY - the mode switch is a
    deliberate human decision, not automatic.
    """
    MIN_TRADES = 30   # a minimum sample before the score can be judged

    d = Decision('PM', 'SIZING-MODE', 'RECOMMEND',
                 'Portfolio Master - Sizing Mode')
    d.add_fact('Closed trades in journal', str(closed_trades))
    d.add_fact('Minimum sample needed', str(MIN_TRADES))

    if closed_trades < MIN_TRADES:
        d.add_fact('Recommendation', f'stay in {MODE_EQUAL} - too few '
                   f'closed trades to judge the conviction score')
        d.set_margin('trades short of the minimum sample',
                     MIN_TRADES - closed_trades)
        d.set_counterfactual(
            f'-> consider {MODE_CONVICTION} only after {MIN_TRADES}+ '
            f'closed trades show high-conviction picks genuinely '
            f'outperform low-conviction ones')
    elif conviction_edge is not None and conviction_edge > 0:
        d.add_fact('Conviction edge', f'+{conviction_edge:.1f}% win-rate gap')
        d.add_fact('Recommendation', f'{MODE_CONVICTION} may be justified - '
                   f'the journal shows a conviction edge')
        d.set_margin('measured conviction edge percent',
                     round(conviction_edge, 1))
        d.set_counterfactual(
            f'stay in {MODE_EQUAL} if the conviction edge were absent '
            f'or negative')
    else:
        d.add_fact('Recommendation', f'stay in {MODE_EQUAL} - the journal '
                   f'does not yet show a clear conviction edge')
        d.set_margin('no validated conviction edge', 0)
        d.set_counterfactual(
            f'-> {MODE_CONVICTION} only when the journal shows '
            f'high-conviction picks measurably outperform')
    return d


# ---- self-test ----
if __name__ == '__main__':
    print('=' * 64)
    print('PORTFOLIO MASTER - POSITION SIZING (5.7) - self-test')
    print('=' * 64)

    # Engine C budget on a Rs 10L portfolio, Active regime: 165,000
    engine_budget = 165000
    total_equity = 550000
    target_positions = 8

    # Test 1: equal-weight sizing (the default)
    print('\nTest 1 - equal-weight sizing, conviction 9:')
    d = size_position('PTC', 'C', 9, engine_budget, target_positions,
                      total_equity, mode=MODE_EQUAL)
    print(f'  verdict: {d.verdict}')
    print(' ', d.reason_string())

    # Test 2: conviction-weight sizing, same stock
    print('\nTest 2 - conviction-weight sizing, conviction 9 (1.30x):')
    d = size_position('PTC', 'C', 9, engine_budget, target_positions,
                      total_equity, mode=MODE_CONVICTION)
    print(f'  verdict: {d.verdict}')
    print(' ', d.reason_string())

    # Test 3: conviction-weight that would breach the stock cap
    print('\nTest 3 - conviction-weight, tiny target -> stock cap binds:')
    d = size_position('JSWSTEEL', 'D', 10, 400000, 3, total_equity,
                      mode=MODE_CONVICTION)
    print(f'  verdict: {d.verdict}')
    print(' ', d.reason_string())

    # Test 4: mode recommendation - too few trades
    print('\nTest 4 - sizing-mode recommendation, 12 closed trades:')
    d = recommend_mode(closed_trades=12)
    print(f'  verdict: {d.verdict}')
    print(' ', d.reason_string())

    # Test 5: mode recommendation - enough trades, conviction edge present
    print('\nTest 5 - 45 closed trades, +14% conviction edge:')
    d = recommend_mode(closed_trades=45, conviction_edge=14.0)
    print(f'  verdict: {d.verdict}')
    print(' ', d.reason_string())

    # Test 6: enough trades, no conviction edge
    print('\nTest 6 - 50 closed trades, no conviction edge:')
    d = recommend_mode(closed_trades=50, conviction_edge=0)
    print(f'  verdict: {d.verdict}')

    print('\n' + '=' * 64)
    print('Self-test complete. The system sizes equal-weight by default;')
    print('conviction-weighting is a deliberate upgrade, justified only')
    print('once the journal proves the conviction score has an edge.')
    print('=' * 64)
