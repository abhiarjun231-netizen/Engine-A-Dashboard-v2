"""
engine_d_churn.py
Parthsarthi Capital - Phase 4, Item 4.5
ENGINE D - THE CHURN HANDLER (Module 5).

A held Engine D stock drops off the D1 compounder screen, but no
Module 4 thesis-break trigger has fired.

Engine D's churn response is the CALMEST of all three engines. A
compounder is a multi-year hold; short-term screen churn is mostly
noise. The handler's default is to keep the position and re-classify.

Decision tree - why did the held compounder leave the screen?
  Module 4 trigger also fired       -> EXIT (thesis break governs)
  PEG rose above 1.5 but below 3.0  -> HOLD - the compounder
     (no longer "reasonably priced"    re-rated; this is success,
      but not yet a bubble)            not a warning
  Price fell below 200DMA, but
     fundamentals intact             -> HOLD - compounders endure
                                        drawdowns; this is normal
  A quality metric slipped, no
     Module 4 trigger yet            -> HOLD, reclassify
                                        DETERIORATING; the tier rules
                                        govern how fast this escalates
  Left the Nifty 500 universe        -> EXIT - outside the data
                                        mandate

For Engine D, leaving the screen is almost never an exit signal on
its own. Only a Module 4 thesis-break or a universe-exit closes a
compounder position. The churn handler mostly re-classifies and
watches - and there is no dead-money timer, because a quiet
compounder with growing fundamentals is still compounding.
"""

from reasoning_engine import Decision


# the D1 screener's PEG ceiling - above this the stock is no longer
# "reasonably priced" but it is not yet a bubble (bubble = PEG > 3.0)
SCREEN_PEG_CEILING = 1.5


def handle_churn(ticker, current_peg, entry_price, current_price,
                 quality_slipped=False, below_200dma=False,
                 left_universe=False, module4_fired=False):
    """
    Decide what to do with a HELD compounder that has left the screen.

    current_peg     - the stock's PEG TTM now
    quality_slipped - True if a quality metric weakened but no Module 4
                      trigger fired yet
    below_200dma    - True if price has fallen below its 200DMA
    left_universe   - True if it dropped out of Nifty 500 entirely
    module4_fired   - True if a Module 4 thesis-break also fired

    Returns a Decision.
    """
    gain_pct = ((current_price - entry_price) / entry_price * 100.0
                if entry_price > 0 else 0.0)

    # ---- Module 4 takes precedence ----
    if module4_fired:
        d = Decision('D', ticker, 'EXIT', 'Module 5 - Churn (Module 4 governs)')
        d.add_fact('Reason', 'a Module 4 thesis-break trigger also fired')
        d.add_fact('Position gain', f'{gain_pct:+.1f}%')
        d.set_margin('churn handler deferred to Module 4', 0)
        d.set_counterfactual('once a thesis-break trigger fires, Module 4 '
                              'governs - churn handling is irrelevant')
        return d

    # ---- left the universe entirely ----
    if left_universe:
        d = Decision('D', ticker, 'EXIT', 'Module 5 - Left Universe')
        d.add_fact('Reason', 'stock left the Nifty 500 universe entirely')
        d.add_fact('Position gain', f'{gain_pct:+.1f}%')
        d.set_margin('outside data mandate', 0)
        d.set_counterfactual('the system has no data mandate to hold a '
                              'stock outside its defined universe - exit')
        return d

    # ---- PEG rose above the screen ceiling (re-rated, not a bubble) ----
    if current_peg is not None and current_peg > SCREEN_PEG_CEILING:
        d = Decision('D', ticker, 'HOLD',
                     'Module 5 - Churn (re-rated, not a bubble)')
        d.add_fact('Current PEG', f'{current_peg:.2f} (above screen ceiling '
                   f'{SCREEN_PEG_CEILING}, below bubble line 3.0)')
        d.add_fact('Position gain', f'{gain_pct:+.1f}%')
        d.add_fact('Decision', 'HOLD - the compounder re-rated; this is '
                               'success, not a warning')
        d.set_margin('PEG room to the bubble exit (3.0)',
                     round(3.0 - current_peg, 2))
        d.set_counterfactual(
            'a re-rated compounder is held - Engine D never books profit; '
            'only PEG > 3.0 (Module 4 bubble trigger) would force an exit')
        return d

    # ---- price below 200DMA, fundamentals intact ----
    if below_200dma:
        d = Decision('D', ticker, 'HOLD',
                     'Module 5 - Churn (below 200DMA, thesis intact)')
        d.add_fact('Status', 'price below 200DMA, fundamentals intact')
        d.add_fact('Position gain', f'{gain_pct:+.1f}%')
        d.add_fact('Decision', 'HOLD - compounders endure drawdowns; '
                               'a price dip is not a thesis break')
        d.set_margin('compounder holding through a drawdown', 0)
        d.set_counterfactual(
            'a compounder below its 200DMA with intact fundamentals is a '
            'normal hold; there is no dead-money timer - a quiet compounder '
            'is still compounding')
        return d

    # ---- quality slipped but no hard trigger yet ----
    if quality_slipped:
        d = Decision('D', ticker, 'HOLD-DETERIORATING',
                     'Module 5 - Churn (quality slipped)')
        d.add_fact('Status', 'a quality metric weakened, no Module 4 '
                             'trigger yet')
        d.add_fact('Position gain', f'{gain_pct:+.1f}%')
        d.add_fact('Decision', 'HOLD, reclassify DETERIORATING - the tier '
                               'rules govern how fast this escalates')
        d.set_margin('watching for a Module 4 trigger', 0)
        d.set_counterfactual(
            '-> EXIT if a quality metric crosses a Module 4 threshold; '
            'for IMMORTAL/LEGENDARY tiers a soft breach needs 2 consecutive '
            'readings before it fires')
        return d

    # ---- left the screen for an unclassified reason ----
    d = Decision('D', ticker, 'HOLD-DETERIORATING',
                 'Module 5 - Churn (unclassified screen drop)')
    d.add_fact('Status', 'left the screen, reason not classified')
    d.add_fact('Current PEG', f'{current_peg:.2f}' if current_peg is not None else 'n/a')
    d.add_fact('Position gain', f'{gain_pct:+.1f}%')
    d.add_fact('Decision', 'HOLD, reclassify DETERIORATING - watch on the '
                           'next screen upload')
    d.set_margin('default conservative hold', 0)
    d.set_counterfactual('for a compounder, a screen drop alone is not an '
                          'exit; the next upload should clarify the reason')
    return d


# ---- self-test ----
if __name__ == '__main__':
    print('=' * 64)
    print('ENGINE D CHURN HANDLER (Module 5) - self-test')
    print('=' * 64)

    # Test 1: PEG rose above 1.5 - re-rated, HOLD
    print('\nTest 1 - left screen because PEG rose to 2.1 (re-rated):')
    d = handle_churn('HINDZINC', current_peg=2.1, entry_price=100,
                     current_price=145)
    print(f'  verdict: {d.verdict}')
    print(' ', d.reason_string())

    # Test 2: price below 200DMA, fundamentals intact -> HOLD
    print('\nTest 2 - left screen, price below 200DMA, thesis intact:')
    d = handle_churn('LUPIN', current_peg=0.9, entry_price=100,
                     current_price=90, below_200dma=True)
    print(f'  verdict: {d.verdict}')
    print(' ', d.reason_string())

    # Test 3: quality slipped, no hard trigger -> HOLD-DETERIORATING
    print('\nTest 3 - left screen, a quality metric slipped:')
    d = handle_churn('GVPIL', current_peg=0.8, entry_price=100,
                     current_price=110, quality_slipped=True)
    print(f'  verdict: {d.verdict}')
    print(' ', d.reason_string())

    # Test 4: left the universe -> EXIT
    print('\nTest 4 - left the Nifty 500 universe entirely:')
    d = handle_churn('FORCEMOT', current_peg=1.0, entry_price=100,
                     current_price=160, left_universe=True)
    print(f'  verdict: {d.verdict}')
    print(' ', d.reason_string())

    # Test 5: Module 4 also fired -> EXIT
    print('\nTest 5 - left screen AND a Module 4 trigger fired:')
    d = handle_churn('THYROCARE', current_peg=0.7, entry_price=100,
                     current_price=75, module4_fired=True)
    print(f'  verdict: {d.verdict}')
    print(' ', d.reason_string())

    print('\n' + '=' * 64)
    print('Self-test complete. Engine D treats a screen drop most calmly')
    print('of all - a re-rated compounder is HELD, a dip is HELD, and only')
    print('thesis-break or universe-exit forces EXIT. No dead-money timer.')
    print('=' * 64)
