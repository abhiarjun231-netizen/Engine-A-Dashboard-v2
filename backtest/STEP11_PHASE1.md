# Step 11 Backtest Harness — Phase 1

**Status:** Engine built, synthetic validation passed.
**Next:** Phase 2 = historical data reconstruction + real 18-year run.

---

## What Phase 1 is

The deterministic simulation core. Takes a CSV of monthly signals and returns, applies the locked ALLOCATION_BANDS, and produces a NAV path with attribution. **No real market data yet** — that's Phase 2.

Why this split: the simulation logic and the historical-data scraping are two different risk profiles. Logic should be bulletproof. Data is messy and iterative. Validate logic on synthetic data first → trust real-data results later.

---

## Files

| File | Purpose | Lines |
|---|---|---|
| `backtest_engine.py` | Simulation core. Allocation, NAV, metrics, attribution. | ~150 |
| `validate_engine.py` | Generates 18yr synthetic data, runs engine, plots. | ~120 |
| `validation_chart.png` | Visual proof the engine reacts to scores correctly. | — |
| `validation_simulation.csv` | Full month-by-month simulation output from synthetic run. | — |

---

## Locked decisions baked in (from handover)

- `ALLOCATION_BANDS` exactly as specified — 75/60/45/35/25/0 thresholds → 85/70/55/40/25/10% equity
- PE bubble override: Nifty PE > 26 caps equity at 70%
- Non-equity split: 75% debt / 25% gold (matches Engine E Fortress design)
- **Signal convention:** score at month *t* sets weights applied to month *t+1* returns. No look-ahead bias.

---

## Synthetic validation result

18 years (Jan 2008 – Dec 2025), with engineered GFC + COVID + 2022 vol regimes baked in.

| Metric | Parthsarthi | Nifty B&H | 60/40 |
|---|---|---|---|
| CAGR | 6.22% | 0.40% | 3.89% |
| Sharpe | 0.63 | 0.12 | 0.37 |
| Max DD | **-33.13%** | -59.12% | -39.15% |
| Final NAV (₹10L start) | ₹29.5L | ₹9.6L | ₹18.5L |

**Read this carefully:** the synthetic data was *constructed* with score-return correlation, so alpha is guaranteed by design. **This is not proof the bands generate alpha in real markets.** It only proves the engine implements the bands correctly — drawdown protection scales as scores fall, equity allocation tracks score band, attribution math reconciles.

Phase 2 will use real Nifty/debt/gold returns + reconstructed scores. *That* result is the actual validation.

### Regime attribution (synthetic)

```
     regime  months  avg_ret  nifty_avg  alpha
     ACTIVE      57    0.73%      0.32%   +0.40%
 AGGRESSIVE      50    0.27%     -0.05%   +0.32%
   CAUTIOUS      45    1.03%      1.52%   -0.48%
     FREEZE      39    0.35%     -0.86%   +1.21%
   EXIT_ALL      15   -0.37%     -1.60%   +1.23%
FULL_DEPLOY      10    0.89%      0.76%   +0.13%
```

What this tells us: the engine produces strongest *relative* alpha in defensive regimes (FREEZE, EXIT_ALL) — which is the whole point of having them. CAUTIOUS shows negative alpha because in synthetic data the score sometimes lagged a recovery. Worth watching in real-data backtest.

---

## Phase 2 — what's needed before real backtest

**Required CSV columns:**

| Column | Source | Available from |
|---|---|---|
| date | — | — |
| engine_a_score | reconstructed from historical sub-inputs | partial |
| nifty_pe | NSE historical PE archive (CSV) | 2008+ |
| nifty_ret_m | yfinance `^NSEI` monthly | 2008+ |
| debt_ret_m | LIQUIDBEES.NS NAV / G-Sec index | 2008+ |
| gold_ret_m | yfinance gold INR or GOLDBEES.NS | 2008+ |

**Honest data availability for score reconstruction:**

| Component | Full 18yr? | Notes |
|---|---|---|
| C1 Valuation (PE, MCap/GDP) | partial | PE clean; MCap/GDP annual only |
| C2 Credit & Rates | partial | AAA spread series patchy pre-2014 |
| C3 Trend & Breadth | yes | Computable from price data |
| C4 Volatility | 2009+ | India VIX launched Mar 2008 |
| C5 Flows (FII/DII/SIP) | partial | FII/DII 2008+; SIP only 2016+ |
| C6 Macro India | partial | CPI new series 2011+; GST 2017+; PMI paid |
| C7 Global | yes | All yfinance |
| C8 Crude | yes | Brent on yfinance |

**Realistic Phase 2 deliverable:** tiered backtest — full 8-component reconstruction for 2018–2026 (rigorous), partial 5-component reconstruction for 2008–2017 (indicative, with defaults for missing components).

---

## How to run Phase 1 yourself

In Colab from your phone:

```python
!pip install -q pandas numpy matplotlib
# Upload backtest_engine.py and validate_engine.py to Colab
!python validate_engine.py
```

Output: prints metrics table, saves `validation_chart.png` and `validation_simulation.csv`.

To run on your own CSV with the right columns:

```python
from backtest_engine import run_full_backtest
r = run_full_backtest('your_data.csv')
print(r['parthsarthi_metrics'])
```

---

## What I need from you before Phase 2

1. **Logic check.** Eyeball the chart. Does the equity-allocation response to score look right? Does the NAV path behave the way an Engine A user would expect?
2. **Debt proxy call.** For real backtest: LIQUIDBEES (overnight, ~6-7%) or 10Y G-Sec total return (~7-8%, more volatile)? My default is LIQUIDBEES since that's what the live system parks cash in.
3. **Missing-data handling.** When a sub-input is unavailable in the historical window, default to *median score* (neutral, conservative), or *drop the component and rescale to 100*? My default is median-fill — preserves the score scale, treats unknown as neutral.

Reply with go-aheads or overrides on those three, and I start Phase 2.

जय श्री कृष्ण।
