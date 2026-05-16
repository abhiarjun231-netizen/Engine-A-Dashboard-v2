"""
engine_b_churn.py
Parthsarthi Capital - Phase 2, Item 2.6
ENGINE B - THE CHURN HANDLER (Module 5).

The hard case: a stock the system HOLDS drops off the momentum
screen, but no Module 3 exit trigger has fired.

This is a distinct event from DVM Decay. A stock can leave the
screen because Durability slipped 66 -> 63 (off-screen) without ever
crossing the 45 exit floor. The four exit triggers do not see this.
The churn handler does.

The principle: a screener dropping a held name is a SOFT warning,
not a hard signal. The response scales with how much profit is
already banked:
  - deep in profit  -> trust the trailing stop, HOLD
  - marginal profit -> tighten the stop, give a short leash
  - underwater      -> screen and price agree, EXIT
  - left the universe entirely -> EXIT regardless

This module is called only for HELD stocks absent from today's
screen. If a Module 3 trigger also fired, Module 3 governs and this
handler is not consulted.
"""

from reasoning_engine import Decision


# profit threshold that separates "deep" from "marginal" (the +10%
# milestone where the trailing stop first becomes active)
PROFIT_DEEP_PCT = 10.0


def handle_churn(ticker, entry_price, current_price,
                 left_universe=False, module3_fired=False):
    """
    Decide what to do with a HELD stock that has left the screen.

    left_universe  - True if the stock dropped out of the Nifty 500
                     universe entirely (not just a score slip).
    module3_fired  - True if a Module 3 exit trigger also fired; in
                     that case Module 3 governs and churn is moot.

    Returns a Decision with one of:
      EXIT                  - close the position
      HOLD-DETERIORATING    - keep it, reclassify to DETERIORATING
      GUARD-TIGHTEN         - keep it, tighten stop to entry price
    """
    gain_pct = ((current_price - entry_price) / entry_price * 100.0
                if entry_price > 0 else 0.0)

    # ---- Module 3 takes precedence ----
    if module3_fired:
        d = Decision('B', ticker, 'EXIT', 'Module 5 - Churn (Module 3 governs)')
        d.add_fact('Reason', 'a Module 3 exit trigger also fired')
        d.add_fact('Position gain', f'{gain_pct:+.1f}%')
        d.set_margin('churn handler deferred to Module 3', 0)
        d.set_counterfactual('churn handling is irrelevant once a hard '
                             'exit trigger has fired - Module 3 governs')
        return d

    # ---- left the universe entirely ----
    if left_universe:
        d = Decision('B', ticker, 'EXIT', 'Module 5 - Left Universe')
        d.add_fact('Reason', 'stock left the Nifty 500 universe entirely')
        d.add_fact('Position gain', f'{gain_pct:+.1f}%')
        d.set_margin('outside data mandate', 0)
        d.set_counterfactual('the system has no data mandate to hold a '
                             'stock outside its defined universe - exit')
        return d

    # ---- left only by score slip: scale response to profit ----
    if gain_pct > PROFIT_DEEP_PCT:
        # deep in profit - trailing stop active, let it run
        d = Decision('B', ticker, 'HOLD-DETERIORATING',
                     'Module 5 - Churn (deep profit)')
        d.add_fact('Position gain', f'{gain_pct:+.1f}%')
        d.add_fact('Status', f'above +{PROFIT_DEEP_PCT:.0f}% - trailing stop active')
        d.add_fact('Decision', 'HOLD, reclassify DETERIORATING')
        d.set_margin('profit above the deep threshold by',
                     round(gain_pct - PROFIT_DEEP_PCT, 1))
        d.set_counterfactual(
            '-> EXIT if the trailing stop is hit OR a Module 3 trigger '
            'fires; the screen drop alone does not force an exit while '
            'profit is protected')
        return d

    elif gain_pct >= 0:
        # marginal profit - tighten stop to entry, short leash
        d = Decision('B', ticker, 'GUARD-TIGHTEN',
                     'Module 5 - Churn (marginal profit)')
        d.add_fact('Position gain', f'{gain_pct:+.1f}%')
        d.add_fact('Status', f'between entry and +{PROFIT_DEEP_PCT:.0f}%')
        d.add_fact('Decision', 'GUARD - tighten stop to entry price')
        d.set_margin('profit above breakeven by', round(gain_pct, 1))
        d.set_counterfactual(
            '-> EXIT if price falls back to entry (stop now tightened '
            'there); -> HOLD-DETERIORATING if the position runs past '
            f'+{PROFIT_DEEP_PCT:.0f}%')
        return d

    else:
        # underwater - screen and price both negative, exit
        d = Decision('B', ticker, 'EXIT', 'Module 5 - Churn (underwater)')
        d.add_fact('Position gain', f'{gain_pct:+.1f}%')
        d.add_fact('Status', 'below entry price')
        d.add_fact('Decision', 'EXIT - screen dropped it AND it is underwater')
        d.set_margin('position underwater by', round(gain_pct, 1))
        d.set_counterfactual(
            'would HOLD if the position were above entry; underwater '
            'plus a screen drop means no thesis remains - exit')
        return d


# ---- self-test ----
if __name__ == '__main__':
    print('=' * 64)
    print('ENGINE B CHURN HANDLER (Module 5) - self-test')
    print('=' * 64)

    # Test 1: deep profit, left screen by score slip -> HOLD
    print('\nTest 1 - held stock left screen, +14% in profit:')
    d = handle_churn('TATASTEEL', entry_price=100, current_price=114)
    print(f'  verdict: {d.verdict}')
    print(' ', d.reason_string())

    # Test 2: marginal profit -> GUARD-TIGHTEN
    print('\nTest 2 - held stock left screen, +4% in profit:')
    d = handle_churn('JSWSTEEL', entry_price=100, current_price=104)
    print(f'  verdict: {d.verdict}')
    print(' ', d.reason_string())

    # Test 3: underwater -> EXIT
    print('\nTest 3 - held stock left screen, -6% underwater:')
    d = handle_churn('HEG', entry_price=100, current_price=94)
    print(f'  verdict: {d.verdict}')
    print(' ', d.reason_string())

    # Test 4: left the Nifty 500 universe entirely -> EXIT
    print('\nTest 4 - held stock left the Nifty 500 universe (+20% profit):')
    d = handle_churn('BHEL', entry_price=100, current_price=120,
                     left_universe=True)
    print(f'  verdict: {d.verdict}')
    print(' ', d.reason_string())

    # Test 5: Module 3 also fired -> EXIT (Module 3 governs)
    print('\nTest 5 - left screen AND a Module 3 trigger fired:')
    d = handle_churn('MCX', entry_price=100, current_price=130,
                     module3_fired=True)
    print(f'  verdict: {d.verdict}')
    print(' ', d.reason_string())

    # Test 6: exactly at breakeven -> GUARD-TIGHTEN
    print('\nTest 6 - held stock left screen, exactly at entry (0%):')
    d = handle_churn('USHAMART', entry_price=100, current_price=100)
    print(f'  verdict: {d.verdict}')

    print('\n' + '=' * 64)
    print('Self-test complete. The churn handler scales its response to')
    print('banked profit: deep -> HOLD, marginal -> tighten, underwater')
    print('-> EXIT; left-universe and Module-3 cases exit outright.')
    print('=' * 64)
