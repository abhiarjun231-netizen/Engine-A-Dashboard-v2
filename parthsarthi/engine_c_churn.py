"""
engine_c_churn.py
Parthsarthi Capital - Phase 3, Item 3.7
ENGINE C - THE CHURN HANDLER (Module 7).

A held Engine C stock drops off the C2 value screen, but no Module 2B
thesis-break trigger has fired.

Engine C's churn response is the CALMEST of the engines. A value
stock leaving the screen is often GOOD news - its price rose enough
to push PE above 25, which means the value thesis is working. The
handler must not panic-sell a winner.

Decision tree - why did the held stock leave the screen?
  Module 2B trigger also fired      -> EXIT (thesis break governs)
  PE rose above 25 (re-rated up)    -> HOLD, reclassify RE-RATING -
                                       this is the thesis working
  A quality metric slipped, no 2B
     trigger yet                    -> HOLD, reclassify DETERIORATING,
                                       watch closely
  Price fell below 200DMA, but
     fundamentals intact            -> HOLD - value can sit below
                                       its 200DMA; the dead-money
                                       timer is the backstop
  Left the Nifty 500 universe       -> EXIT - outside the data mandate

In Engine B, leaving the screen is a warning. In Engine C, it is
usually neutral or good. The handler's job is to tell "re-rated up
and out" from "quietly rotting".
"""

from reasoning_engine import Decision


# the C2 screener's PE ceiling - a stock above this has "priced out"
SCREEN_PE_CEILING = 25.0


def handle_churn(ticker, current_pe, entry_price, current_price,
                 quality_slipped=False, below_200dma=False,
                 left_universe=False, module2b_fired=False):
    """
    Decide what to do with a HELD value stock that has left the screen.

    current_pe       - the stock's PE TTM now
    quality_slipped  - True if a quality metric weakened but no Module
                       2B trigger fired yet
    below_200dma     - True if price has fallen below its 200DMA
    left_universe    - True if it dropped out of Nifty 500 entirely
    module2b_fired   - True if a Module 2B thesis-break also fired

    Returns a Decision.
    """
    gain_pct = ((current_price - entry_price) / entry_price * 100.0
                if entry_price > 0 else 0.0)

    # ---- Module 2B takes precedence ----
    if module2b_fired:
        d = Decision('C', ticker, 'EXIT', 'Module 7 - Churn (Module 2B governs)')
        d.add_fact('Reason', 'a Module 2B thesis-break trigger also fired')
        d.add_fact('Position gain', f'{gain_pct:+.1f}%')
        d.set_margin('churn handler deferred to Module 2B', 0)
        d.set_counterfactual('once a thesis-break trigger fires, Module 2B '
                              'governs - churn handling is irrelevant')
        return d

    # ---- left the universe entirely ----
    if left_universe:
        d = Decision('C', ticker, 'EXIT', 'Module 7 - Left Universe')
        d.add_fact('Reason', 'stock left the Nifty 500 universe entirely')
        d.add_fact('Position gain', f'{gain_pct:+.1f}%')
        d.set_margin('outside data mandate', 0)
        d.set_counterfactual('the system has no data mandate to hold a '
                              'stock outside its defined universe - exit')
        return d

    # ---- re-rated up: PE above the screen ceiling ----
    if current_pe is not None and current_pe > SCREEN_PE_CEILING:
        d = Decision('C', ticker, 'HOLD-RERATING',
                     'Module 7 - Churn (re-rated up)')
        d.add_fact('Current PE', f'{current_pe:.1f} (above screen ceiling '
                   f'{SCREEN_PE_CEILING:.0f})')
        d.add_fact('Position gain', f'{gain_pct:+.1f}%')
        d.add_fact('Decision', 'HOLD, reclassify RE-RATING - the value '
                               'thesis is working')
        d.set_margin('PE above the screen ceiling by',
                     round(current_pe - SCREEN_PE_CEILING, 1))
        d.set_counterfactual(
            'this is the thesis succeeding - continue holding and let '
            'PE-expansion booking (Module 2A) harvest the re-rating')
        return d

    # ---- quality slipped but no hard trigger yet ----
    if quality_slipped:
        d = Decision('C', ticker, 'HOLD-DETERIORATING',
                     'Module 7 - Churn (quality slipped)')
        d.add_fact('Status', 'a quality metric weakened, no Module 2B '
                             'trigger yet')
        d.add_fact('Position gain', f'{gain_pct:+.1f}%')
        d.add_fact('Decision', 'HOLD, reclassify DETERIORATING - watch closely')
        d.set_margin('watching for a Module 2B trigger', 0)
        d.set_counterfactual(
            '-> EXIT if a quality metric crosses a Module 2B threshold '
            'on the next screen; until then it is a watched hold')
        return d

    # ---- price below 200DMA, fundamentals intact ----
    if below_200dma:
        d = Decision('C', ticker, 'HOLD',
                     'Module 7 - Churn (below 200DMA, thesis intact)')
        d.add_fact('Status', 'price below 200DMA, fundamentals intact')
        d.add_fact('Position gain', f'{gain_pct:+.1f}%')
        d.add_fact('Decision', 'HOLD - a value stock can sit below its '
                               '200DMA; the dead-money timer is the backstop')
        d.set_margin('value position holding through weakness', 0)
        d.set_counterfactual(
            'a value stock below its 200DMA with intact fundamentals is a '
            'normal hold; the 18-month dead-money timer is the only '
            'time-based backstop')
        return d

    # ---- left the screen for an unclassified reason ----
    d = Decision('C', ticker, 'HOLD-DETERIORATING',
                 'Module 7 - Churn (unclassified screen drop)')
    d.add_fact('Status', 'left the screen, reason not classified')
    d.add_fact('Current PE', f'{current_pe:.1f}' if current_pe is not None else 'n/a')
    d.add_fact('Position gain', f'{gain_pct:+.1f}%')
    d.add_fact('Decision', 'HOLD, reclassify DETERIORATING - watch on the '
                           'next screen upload')
    d.set_margin('default conservative hold', 0)
    d.set_counterfactual('the next screen upload should clarify why the '
                          'stock left; until then it is a watched hold')
    return d


# ---- self-test ----
if __name__ == '__main__':
    print('=' * 64)
    print('ENGINE C CHURN HANDLER (Module 7) - self-test')
    print('=' * 64)

    # Test 1: PE rose above 25 - re-rated up, HOLD-RERATING
    print('\nTest 1 - left screen because PE rose to 28 (re-rated up):')
    d = handle_churn('JSWSTEEL', current_pe=28, entry_price=100,
                     current_price=135)
    print(f'  verdict: {d.verdict}')
    print(' ', d.reason_string())

    # Test 2: quality slipped, no hard trigger -> HOLD-DETERIORATING
    print('\nTest 2 - left screen, a quality metric slipped:')
    d = handle_churn('PTC', current_pe=20, entry_price=100,
                     current_price=105, quality_slipped=True)
    print(f'  verdict: {d.verdict}')
    print(' ', d.reason_string())

    # Test 3: price below 200DMA, fundamentals intact -> HOLD
    print('\nTest 3 - left screen, price below 200DMA, thesis intact:')
    d = handle_churn('SHARDACROP', current_pe=18, entry_price=100,
                     current_price=92, below_200dma=True)
    print(f'  verdict: {d.verdict}')
    print(' ', d.reason_string())

    # Test 4: left the universe -> EXIT
    print('\nTest 4 - left the Nifty 500 universe entirely:')
    d = handle_churn('HINDZINC', current_pe=19, entry_price=100,
                     current_price=130, left_universe=True)
    print(f'  verdict: {d.verdict}')
    print(' ', d.reason_string())

    # Test 5: Module 2B also fired -> EXIT
    print('\nTest 5 - left screen AND a Module 2B trigger fired:')
    d = handle_churn('GESHIP', current_pe=16, entry_price=100,
                     current_price=80, module2b_fired=True)
    print(f'  verdict: {d.verdict}')
    print(' ', d.reason_string())

    print('\n' + '=' * 64)
    print('Self-test complete. Engine C treats a screen drop calmly:')
    print('a re-rated stock is HELD as a winner, a slipping one is')
    print('watched, and only universe-exit or thesis-break forces EXIT.')
    print('=' * 64)
