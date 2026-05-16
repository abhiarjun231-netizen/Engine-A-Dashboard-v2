"""
engine_b_profit.py
Parthsarthi Capital - Phase 2, Item 2.5
ENGINE B - PROFIT MANAGEMENT (Module 4).

Engine B uses no fixed profit target. Winners run; a trailing stop
decides the exit. The stop ratchets upward through three milestones:

  +10% from entry  -> stop moves to entry price (position risk-free)
  +20% from entry  -> stop moves to +10%
  +30% from entry  -> stop trails at -10% from the running peak
  beyond +30%      -> stop keeps trailing -10% from each new peak

No partial booking - the whole position rides until the trailing
stop is hit. (Backtest basis: trailing-stop design ~42% CAGR vs
~27% for fixed profit booking.)

Also enforces the dead-money rule: a position flat within +/-5%
for 6 weeks is exited - idle capital is opportunity cost.

This module computes WHERE the trailing stop currently sits and
whether it (or the dead-money rule) has been hit. The four absolute
exit triggers live separately in Module 3 (2.4).
"""

from reasoning_engine import Decision


# ---- locked profit thresholds (Engine B framework) ----
MILESTONE_1 = 10.0    # +10% -> stop to entry
MILESTONE_2 = 20.0    # +20% -> stop to +10%
MILESTONE_3 = 30.0    # +30% -> trail -10% from peak
TRAIL_PCT   = 10.0    # trailing distance below peak, beyond milestone 3
DEAD_MONEY_FLAT_PCT = 5.0     # +/-5% counts as "flat"
DEAD_MONEY_WEEKS    = 6       # weeks flat -> exit


def trailing_stop(entry_price, peak_price):
    """
    Compute where the trailing stop currently sits, given the entry
    price and the highest price reached so far.
    Returns (stop_price, stage_label).
    """
    if entry_price <= 0:
        return 0.0, 'invalid'

    peak_gain_pct = (peak_price - entry_price) / entry_price * 100.0

    if peak_gain_pct >= MILESTONE_3:
        # trail 10% below the running peak
        stop = peak_price * (1 - TRAIL_PCT / 100.0)
        # never let the trail fall below the +10% lock from milestone 2
        floor = entry_price * (1 + MILESTONE_1 / 100.0)
        stop = max(stop, floor)
        stage = f'TRAILING (-{TRAIL_PCT:.0f}% from peak, past +{MILESTONE_3:.0f}%)'
    elif peak_gain_pct >= MILESTONE_2:
        # stop locked at +10%
        stop = entry_price * (1 + MILESTONE_1 / 100.0)
        stage = f'LOCKED at +{MILESTONE_1:.0f}% (peak passed +{MILESTONE_2:.0f}%)'
    elif peak_gain_pct >= MILESTONE_1:
        # stop at entry - position is risk-free
        stop = entry_price
        stage = f'RISK-FREE at entry (peak passed +{MILESTONE_1:.0f}%)'
    else:
        # below first milestone - no trailing stop yet (Module 3 hard stop applies)
        stop = None
        stage = f'no trail yet (peak gain {peak_gain_pct:.1f}% < +{MILESTONE_1:.0f}%)'

    return (round(stop, 2) if stop is not None else None), stage


def check_profit(ticker, entry_price, current_price, peak_price,
                 weeks_held=0, weeks_flat=0):
    """
    Assess an open Engine B position's profit status.

    Returns a Decision:
      'EXIT-TRAIL' - trailing stop has been hit
      'EXIT-DEAD'  - dead-money rule has been hit (6 weeks flat)
      'HOLD'       - position continues; stop level reported

    weeks_flat - consecutive weeks the position has stayed within
                 +/-5% of entry. Drives the dead-money rule.
    """
    gain_pct = ((current_price - entry_price) / entry_price * 100.0
                if entry_price > 0 else 0.0)
    stop, stage = trailing_stop(entry_price, peak_price)

    # ---- dead-money rule ----
    if weeks_flat >= DEAD_MONEY_WEEKS:
        d = Decision('B', ticker, 'EXIT-DEAD', 'Module 4 - Dead-Money Rule')
        d.add_fact('Position gain', f'{gain_pct:+.1f}%')
        d.add_fact('Weeks flat', f'{weeks_flat} (within +/-{DEAD_MONEY_FLAT_PCT:.0f}%)')
        d.add_fact('Threshold', f'{DEAD_MONEY_WEEKS} weeks')
        d.set_margin('weeks flat past threshold', weeks_flat - DEAD_MONEY_WEEKS)
        d.set_counterfactual(
            f'would HOLD if the position had moved beyond +/-'
            f'{DEAD_MONEY_FLAT_PCT:.0f}% within {DEAD_MONEY_WEEKS} weeks')
        return d

    # ---- trailing stop hit ----
    if stop is not None and current_price <= stop:
        d = Decision('B', ticker, 'EXIT-TRAIL', 'Module 4 - Trailing Stop')
        d.add_fact('Entry', f'{entry_price:.1f}')
        d.add_fact('Peak', f'{peak_price:.1f}')
        d.add_fact('Current price', f'{current_price:.1f}')
        d.add_fact('Trailing stop', f'{stop} ({stage})')
        locked_gain = (stop - entry_price) / entry_price * 100.0
        d.add_fact('Gain locked in', f'{locked_gain:+.1f}%')
        d.set_margin('price below trailing stop by',
                     round(stop - current_price, 2))
        d.set_counterfactual(
            'the trailing stop is hit - exit; the position would have '
            'continued only if price had stayed above the stop')
        return d

    # ---- position continues ----
    d = Decision('B', ticker, 'HOLD', 'Module 4 - Profit Management')
    d.add_fact('Entry', f'{entry_price:.1f}')
    d.add_fact('Current price', f'{current_price:.1f}')
    d.add_fact('Position gain', f'{gain_pct:+.1f}%')
    d.add_fact('Peak', f'{peak_price:.1f}')
    d.add_fact('Trailing stop', f'{stop} ({stage})' if stop is not None
               else f'none yet ({stage})')
    d.add_fact('Weeks flat', str(weeks_flat))

    if stop is not None:
        room = (current_price - stop) / current_price * 100.0
        d.set_margin('% above trailing stop', round(room, 1))
    else:
        d.set_margin('% to first milestone (+10%)',
                     round(MILESTONE_1 - gain_pct, 1))
    d.set_counterfactual(
        f'-> EXIT-TRAIL if price falls to the trailing stop; '
        f'stop ratchets up at +{MILESTONE_1:.0f}/+{MILESTONE_2:.0f}/'
        f'+{MILESTONE_3:.0f}% milestones; -> EXIT-DEAD if flat '
        f'{DEAD_MONEY_WEEKS} weeks')
    return d


# ---- self-test ----
if __name__ == '__main__':
    print('=' * 64)
    print('ENGINE B PROFIT MANAGEMENT (Module 4) - self-test')
    print('=' * 64)

    entry = 100.0

    # Test 1: position up 6% - below first milestone, no trail yet
    print('\nTest 1 - position +6% (below first milestone):')
    d = check_profit('TATASTEEL', entry, current_price=106, peak_price=106)
    print(f'  verdict: {d.verdict}')
    print(' ', d.reason_string())

    # Test 2: peak hit +12% - stop moves to entry (risk-free)
    print('\nTest 2 - peaked +12%, now +8% (stop at entry):')
    d = check_profit('JSWSTEEL', entry, current_price=108, peak_price=112)
    print(f'  verdict: {d.verdict}')
    print(' ', d.reason_string())

    # Test 3: peak +25% - stop locked at +10%
    print('\nTest 3 - peaked +25%, now +18% (stop locked +10%):')
    d = check_profit('HEG', entry, current_price=118, peak_price=125)
    print(f'  verdict: {d.verdict}')
    print(' ', d.reason_string())

    # Test 4: peak +50% - trailing 10% from peak
    print('\nTest 4 - peaked +50%, now +38% (trailing -10% from peak):')
    d = check_profit('BHEL', entry, current_price=138, peak_price=150)
    print(f'  verdict: {d.verdict}')
    print(' ', d.reason_string())

    # Test 5: trailing stop HIT
    print('\nTest 5 - peaked +40%, price fell to +26% (stop hit):')
    d = check_profit('MCX', entry, current_price=126, peak_price=140)
    print(f'  verdict: {d.verdict}')
    print(' ', d.reason_string())

    # Test 6: dead-money rule - flat 6 weeks
    print('\nTest 6 - position flat for 6 weeks:')
    d = check_profit('USHAMART', entry, current_price=102, peak_price=104,
                     weeks_held=6, weeks_flat=6)
    print(f'  verdict: {d.verdict}')
    print(' ', d.reason_string())

    print('\n' + '=' * 64)
    print('Self-test complete. The trailing stop ratchets up through')
    print('the +10/+20/+30% milestones, no partial booking, and the')
    print('dead-money rule frees idle capital after 6 flat weeks.')
    print('=' * 64)
