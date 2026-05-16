"""
portfolio_stockcap.py
Parthsarthi Capital - Phase 5, Item 5.2
PORTFOLIO MASTER - TOTAL-PORTFOLIO STOCK CAP.

The concentration bomb this module defuses:
Each engine caps a single stock at 10% of THAT ENGINE's capital.
But a stock can be owned across the engine boundary - and three
separate 10% caps could stack into 30% exposure to one name.

The Portfolio Master fix - a master cap that overrides the
engine-level cap whenever they conflict:

  No single stock may exceed 10% of TOTAL EQUITY CAPITAL,
  summed across every engine that holds it.

In practice, with the assignment rule (item 5.3) ensuring one stock
is owned by only one engine, the summing is usually trivial - but
this module is the hard backstop. It is checked before every entry
and every top-up.

This module answers one question: "if we buy / add this much of
this stock, does total exposure stay within the 10% master cap?"
"""

from reasoning_engine import Decision


# the master cap: max % of TOTAL equity capital in any single stock
MASTER_STOCK_CAP_PCT = 10.0


def total_stock_exposure(ticker, positions):
    """
    Total rupee value held in one ticker, summed across all engines.

    positions - list of dicts {ticker, engine, current_value}
    """
    return sum(p.get('current_value', 0) for p in positions
               if p['ticker'] == ticker)


def check_stock_cap(ticker, proposed_value, total_equity, positions):
    """
    Check whether buying / adding `proposed_value` of `ticker` keeps
    total exposure within the master cap.

    proposed_value - rupee value of the intended new purchase / top-up
    total_equity   - the total equity capital (from the capital allocator)
    positions      - current positions across all engines

    Returns a Decision:
      CAP-OK      - the purchase fits within the master cap
      CAP-BREACH  - the purchase would breach the cap; it must be
                    reduced or rejected
      CAP-PARTIAL - the full purchase breaches, but a smaller amount
                    fits; the decision states the maximum allowed
    """
    if total_equity <= 0:
        d = Decision('PM', ticker, 'CAP-BREACH',
                     'Portfolio Master - Stock Cap (no capital)')
        d.add_fact('Issue', 'total equity capital is zero or unset')
        d.set_margin('cannot evaluate cap', 0)
        d.set_counterfactual('the capital allocator must set total equity '
                              'before any cap check can run')
        return d

    cap_value = total_equity * MASTER_STOCK_CAP_PCT / 100.0
    existing = total_stock_exposure(ticker, positions)
    after = existing + proposed_value
    after_pct = after / total_equity * 100.0
    existing_pct = existing / total_equity * 100.0

    # ---- fits within the cap ----
    if after <= cap_value:
        d = Decision('PM', ticker, 'CAP-OK',
                     'Portfolio Master - Stock Cap')
        d.add_fact('Existing exposure', f'{existing:,.0f} ({existing_pct:.1f}%)')
        d.add_fact('Proposed purchase', f'{proposed_value:,.0f}')
        d.add_fact('Exposure after', f'{after:,.0f} ({after_pct:.1f}%)')
        d.add_fact('Master cap', f'{cap_value:,.0f} ({MASTER_STOCK_CAP_PCT:.0f}%)')
        d.set_margin('headroom to the cap percent',
                     round(MASTER_STOCK_CAP_PCT - after_pct, 1))
        d.set_counterfactual(
            f'-> CAP-BREACH if the purchase pushed total exposure above '
            f'{MASTER_STOCK_CAP_PCT:.0f}% of total equity')
        return d

    # ---- breaches: is there room for a smaller amount? ----
    room = cap_value - existing
    if room > 0:
        d = Decision('PM', ticker, 'CAP-PARTIAL',
                     'Portfolio Master - Stock Cap (partial)')
        d.add_fact('Existing exposure', f'{existing:,.0f} ({existing_pct:.1f}%)')
        d.add_fact('Proposed purchase', f'{proposed_value:,.0f}')
        d.add_fact('Would reach', f'{after:,.0f} ({after_pct:.1f}%) - over cap')
        d.add_fact('Master cap', f'{cap_value:,.0f} ({MASTER_STOCK_CAP_PCT:.0f}%)')
        d.add_fact('Maximum allowed now', f'{room:,.0f}')
        d.set_margin('rupees the purchase must be reduced by',
                     round(proposed_value - room, 0))
        d.set_counterfactual(
            f'the purchase must be cut to {room:,.0f} or less to stay '
            f'within the {MASTER_STOCK_CAP_PCT:.0f}% master cap')
        return d

    # ---- already at or over the cap ----
    d = Decision('PM', ticker, 'CAP-BREACH',
                 'Portfolio Master - Stock Cap (breach)')
    d.add_fact('Existing exposure', f'{existing:,.0f} ({existing_pct:.1f}%)')
    d.add_fact('Master cap', f'{cap_value:,.0f} ({MASTER_STOCK_CAP_PCT:.0f}%)')
    d.add_fact('Decision', 'existing exposure is already at/over the cap - '
                           'no further purchase permitted')
    d.set_margin('percent already over the cap',
                 round(existing_pct - MASTER_STOCK_CAP_PCT, 1))
    d.set_counterfactual(
        'no purchase is allowed; the stock is already at the master '
        'cap - this overrides any engine-level room')
    return d


# ---- self-test ----
if __name__ == '__main__':
    print('=' * 64)
    print('PORTFOLIO MASTER - TOTAL-PORTFOLIO STOCK CAP (5.2) - self-test')
    print('=' * 64)

    total_equity = 550000   # equity budget on a Rs 10L portfolio, Active regime

    # Test 1: fresh buy, well within cap
    print('\nTest 1 - fresh buy of 30,000 (no existing exposure):')
    d = check_stock_cap('TATASTEEL', 30000, total_equity, positions=[])
    print(f'  verdict: {d.verdict}')
    print(' ', d.reason_string())

    # Test 2: the concentration-bomb case - stock held in 2 engines
    print('\nTest 2 - JSWSTEEL held in C (30k) and D (25k), buy 20k more:')
    positions = [
        {'ticker': 'JSWSTEEL', 'engine': 'C', 'current_value': 30000},
        {'ticker': 'JSWSTEEL', 'engine': 'D', 'current_value': 25000},
    ]
    d = check_stock_cap('JSWSTEEL', 20000, total_equity, positions)
    print(f'  verdict: {d.verdict}')
    print(' ', d.reason_string())

    # Test 3: purchase that would breach -> CAP-PARTIAL
    print('\nTest 3 - HINDZINC has 40k, buy 30k more (cap is 55k):')
    positions = [{'ticker': 'HINDZINC', 'engine': 'D',
                  'current_value': 40000}]
    d = check_stock_cap('HINDZINC', 30000, total_equity, positions)
    print(f'  verdict: {d.verdict}')
    print(' ', d.reason_string())

    # Test 4: already at the cap -> CAP-BREACH
    print('\nTest 4 - PTC already at 55k (the 10% cap), buy more:')
    positions = [{'ticker': 'PTC', 'engine': 'C', 'current_value': 55000}]
    d = check_stock_cap('PTC', 10000, total_equity, positions)
    print(f'  verdict: {d.verdict}')
    print(' ', d.reason_string())

    # Test 5: exactly at the cap boundary
    print('\nTest 5 - buy exactly up to the cap (55,000):')
    d = check_stock_cap('SHARDACROP', 55000, total_equity, positions=[])
    print(f'  verdict: {d.verdict}')

    print('\n' + '=' * 64)
    print('Self-test complete. The master cap limits any single stock to')
    print('10% of TOTAL equity, summed across engines - overriding the')
    print('per-engine cap and defusing the cross-engine concentration risk.')
    print('=' * 64)
