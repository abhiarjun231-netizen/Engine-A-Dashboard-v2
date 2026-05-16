"""
engine_b_execution.py
Parthsarthi Capital - Phase 2, Item 2.3
ENGINE B - EXECUTION LAYER (Module 1B).

Conviction scoring (2.1) decides WHICH momentum stock to buy.
This module decides WHEN and AT WHAT LEVEL - the precise entry.

Momentum is hot money; a sloppy entry bleeds the edge. This layer
adds price/volume precision that DVM scores (end-of-day) cannot give.

The rules (from the Engine B framework, Module 1B):
  1. Entry trigger : price breaks the 20-day high on volume
                     >= 1.5x the 20-day average volume.
  2. Entry zone    : from the breakout level to +1xATR above it.
  3. Do-not-chase  : if price is already beyond +2xATR above the
                     breakout, WAIT for a pullback.
  4. Gap guardrail : if the stock gaps up > 3-4% at the open, WAIT.
  5. Stop          : ATR-based - 1.5xATR below the entry price.

IMPORTANT - data dependency:
This module needs intraday/recent OHLC + volume per stock:
20-day high, 20-day average volume, ATR(14), current price,
previous close. The Trendlyne screener CSV does NOT carry these.
They come from a live data feed (Angel One) wired in Phase 6.
So this module is built to ACCEPT a price-data dict and apply the
rules. The data fetch itself is a separate, later wiring task.
"""

from reasoning_engine import Decision


# ---- locked execution thresholds (Engine B framework) ----
VOLUME_MULTIPLE   = 1.5     # breakout volume vs 20-day average
CHASE_ATR_LIMIT   = 2.0     # do not chase beyond +2xATR above breakout
GAP_GUARD_PCT     = 3.5     # gap-up beyond this % at open -> wait
STOP_ATR_MULTIPLE = 1.5     # stop = entry - 1.5xATR


class PriceData:
    """
    The intraday/recent price snapshot one stock needs for execution.
    In production this is populated from the Angel One feed.
    """

    def __init__(self, ticker, current_price, prev_close,
                 high_20d, avg_volume_20d, current_volume, atr_14):
        self.ticker = ticker
        self.current_price = current_price
        self.prev_close = prev_close
        self.high_20d = high_20d            # 20-day high (breakout level)
        self.avg_volume_20d = avg_volume_20d
        self.current_volume = current_volume
        self.atr_14 = atr_14                # Average True Range (14)

    def gap_pct(self):
        """Opening gap vs previous close, in %."""
        if self.prev_close == 0:
            return 0.0
        return (self.current_price - self.prev_close) / self.prev_close * 100.0

    def volume_ratio(self):
        """Current volume as a multiple of the 20-day average."""
        if self.avg_volume_20d == 0:
            return 0.0
        return self.current_volume / self.avg_volume_20d

    def atr_above_breakout(self):
        """How many ATRs the current price sits above the 20-day high."""
        if self.atr_14 == 0:
            return 0.0
        return (self.current_price - self.high_20d) / self.atr_14


def evaluate_entry(pd):
    """
    Apply the Module 1B execution rules to a stock that has already
    cleared conviction (STRIKE). Returns a Decision with one of:
      ENTER       - all conditions met, buy now
      WAIT-GAP    - gapped up too much, wait for it to settle
      WAIT-CHASE  - price too extended above breakout, wait for pullback
      WAIT-SETUP  - breakout / volume not yet confirmed
    plus the entry zone and the ATR-based stop level.
    """
    gap = pd.gap_pct()
    vol_ratio = pd.volume_ratio()
    atr_dist = pd.atr_above_breakout()
    broke_out = pd.current_price > pd.high_20d
    vol_ok = vol_ratio >= VOLUME_MULTIPLE

    # entry zone and stop (computed regardless, for the report)
    zone_low = pd.high_20d
    zone_high = pd.high_20d + pd.atr_14
    stop = round(pd.current_price - STOP_ATR_MULTIPLE * pd.atr_14, 2)

    # ---- decision cascade ----
    if gap > GAP_GUARD_PCT:
        verdict = 'WAIT-GAP'
        rule = 'Module 1B - Gap Guardrail'
        note = (f'gapped up {gap:.1f}% (limit {GAP_GUARD_PCT}%) - '
                f'do not chase the gap')
    elif not broke_out:
        verdict = 'WAIT-SETUP'
        rule = 'Module 1B - Breakout Trigger'
        note = (f'price {pd.current_price:.1f} has not broken the '
                f'20-day high {pd.high_20d:.1f}')
    elif not vol_ok:
        verdict = 'WAIT-SETUP'
        rule = 'Module 1B - Volume Confirmation'
        note = (f'breakout on weak volume - {vol_ratio:.2f}x avg, '
                f'needs >= {VOLUME_MULTIPLE}x')
    elif atr_dist > CHASE_ATR_LIMIT:
        verdict = 'WAIT-CHASE'
        rule = 'Module 1B - Do-Not-Chase'
        note = (f'price is {atr_dist:.1f}xATR above breakout '
                f'(limit {CHASE_ATR_LIMIT}x) - wait for a pullback')
    else:
        verdict = 'ENTER'
        rule = 'Module 1B - Execution Layer'
        note = (f'breakout confirmed on {vol_ratio:.2f}x volume, '
                f'price {atr_dist:.1f}xATR above breakout - within entry zone')

    # ---- build the Decision ----
    d = Decision('B', pd.ticker, verdict, rule)
    d.add_fact('Current price', f'{pd.current_price:.1f}')
    d.add_fact('20-day high', f'{pd.high_20d:.1f}')
    d.add_fact('Gap', f'{gap:+.1f}%')
    d.add_fact('Volume', f'{vol_ratio:.2f}x avg')
    d.add_fact('Entry zone', f'{zone_low:.1f} - {zone_high:.1f}')
    d.add_fact('ATR stop', f'{stop}')
    d.add_fact('Assessment', note)

    if verdict == 'ENTER':
        d.set_margin('ATRs of room before do-not-chase limit',
                     round(CHASE_ATR_LIMIT - atr_dist, 2))
        d.set_counterfactual(
            f'would WAIT if gap exceeded {GAP_GUARD_PCT}% OR price '
            f'extended beyond {CHASE_ATR_LIMIT}xATR above breakout')
    else:
        d.set_margin('execution condition not yet met', 0)
        d.set_counterfactual(
            'ENTER once breakout + volume confirm and price is within '
            'the entry zone (breakout to +1xATR), with no excessive gap')
    return d


# ---- self-test ----
if __name__ == '__main__':
    print('=' * 64)
    print('ENGINE B EXECUTION LAYER (Module 1B) - self-test')
    print('=' * 64)

    # Test 1: clean breakout - should ENTER
    print('\nTest 1 - clean breakout on strong volume:')
    pd1 = PriceData('TATASTEEL', current_price=142.0, prev_close=139.5,
                    high_20d=140.0, avg_volume_20d=1_000_000,
                    current_volume=1_800_000, atr_14=4.0)
    d = evaluate_entry(pd1)
    print(f'  verdict: {d.verdict}')
    print(' ', d.reason_string())

    # Test 2: gapped up too much - WAIT-GAP
    print('\nTest 2 - gapped up 5% at open:')
    pd2 = PriceData('JSWSTEEL', current_price=945.0, prev_close=900.0,
                    high_20d=920.0, avg_volume_20d=500_000,
                    current_volume=1_200_000, atr_14=25.0)
    d = evaluate_entry(pd2)
    print(f'  verdict: {d.verdict}')
    print(' ', d.reason_string())

    # Test 3: not broken out yet - WAIT-SETUP
    print('\nTest 3 - price below the 20-day high:')
    pd3 = PriceData('HINDZINC', current_price=435.0, prev_close=433.0,
                    high_20d=450.0, avg_volume_20d=800_000,
                    current_volume=900_000, atr_14=12.0)
    d = evaluate_entry(pd3)
    print(f'  verdict: {d.verdict}')
    print(' ', d.reason_string())

    # Test 4: breakout but weak volume - WAIT-SETUP
    print('\nTest 4 - breakout on weak volume (1.1x):')
    pd4 = PriceData('HEG', current_price=2010.0, prev_close=1995.0,
                    high_20d=2000.0, avg_volume_20d=300_000,
                    current_volume=330_000, atr_14=60.0)
    d = evaluate_entry(pd4)
    print(f'  verdict: {d.verdict}')
    print(' ', d.reason_string())

    # Test 5: extended too far above breakout - WAIT-CHASE
    print('\nTest 5 - price extended 2.5xATR above breakout:')
    pd5 = PriceData('BHEL', current_price=260.0, prev_close=255.0,
                    high_20d=250.0, avg_volume_20d=2_000_000,
                    current_volume=3_500_000, atr_14=4.0)
    d = evaluate_entry(pd5)
    print(f'  verdict: {d.verdict}')
    print(' ', d.reason_string())

    print('\n' + '=' * 64)
    print('Self-test complete. The execution layer confirms breakout +')
    print('volume, enforces the gap and do-not-chase guards, and outputs')
    print('a precise entry zone and ATR stop. Needs a live price feed.')
    print('=' * 64)
