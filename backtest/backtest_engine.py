"""
backtest_engine.py
Parthsarthi Capital - Step 11 Backtest Harness, Phase 1
Simulation core for testing Engine A v2.1 allocation bands.

Inputs (CSV): date, engine_a_score, nifty_pe, nifty_ret_m, debt_ret_m, gold_ret_m
Outputs:      Portfolio NAV, performance vs benchmarks, regime attribution.

Locked from PARTHSARTHI_HANDOVER (May 16, 2026).
Do not modify ALLOCATION_BANDS or PE_BUBBLE_* without explicit re-validation.
"""

import pandas as pd
import numpy as np


# ----- LOCKED CONSTANTS (from handover) -----
ALLOCATION_BANDS = [
    (75, 'FULL_DEPLOY', 85),
    (60, 'AGGRESSIVE',  70),
    (45, 'ACTIVE',      55),
    (35, 'CAUTIOUS',    40),
    (25, 'FREEZE',      25),
    (0,  'EXIT_ALL',    10),
]
PE_BUBBLE_THRESHOLD = 26   # Nifty PE above this caps equity
PE_BUBBLE_CAP       = 70   # Equity ceiling when in bubble

# Engine E (Fortress) split of the non-equity sleeve.
# 75% debt / 25% gold matches BHARATBOND + GOLDBEES design from earlier sessions.
DEBT_SHARE_OF_NONEQ = 0.75
GOLD_SHARE_OF_NONEQ = 0.25


# ----- ALLOCATION LOGIC -----
def score_to_band(score: float):
    """Returns (regime_name, equity_pct) for a given Engine A score (0-100)."""
    for threshold, regime, equity_pct in ALLOCATION_BANDS:
        if score >= threshold:
            return regime, equity_pct
    return 'EXIT_ALL', 10  # floor


def apply_pe_safety(equity_pct: float, nifty_pe: float) -> float:
    """PE bubble override: cap equity at 70% if Nifty PE > 26."""
    if pd.notna(nifty_pe) and nifty_pe > PE_BUBBLE_THRESHOLD:
        return min(equity_pct, PE_BUBBLE_CAP)
    return equity_pct


def allocate(score: float, nifty_pe: float) -> dict:
    """Full allocation for one signal point. Returns regime + eq/db/gold %."""
    regime, eq = score_to_band(score)
    eq = apply_pe_safety(eq, nifty_pe)
    non_eq = 100 - eq
    return {
        'regime':     regime,
        'equity_pct': eq,
        'debt_pct':   non_eq * DEBT_SHARE_OF_NONEQ,
        'gold_pct':   non_eq * GOLD_SHARE_OF_NONEQ,
    }


# ----- SIMULATION -----
def simulate_portfolio(df: pd.DataFrame, initial_capital: float = 1_000_000) -> pd.DataFrame:
    """
    Run the backtest.

    df columns required:
      date            (datetime, month-end)
      engine_a_score  (0-100, signal at month t)
      nifty_pe        (for PE bubble override)
      nifty_ret_m     (decimal, e.g. 0.025)
      debt_ret_m
      gold_ret_m

    Signal convention: score at month t determines weights APPLIED TO month t+1 returns.
    This is the institutionally correct convention (no look-ahead bias).

    Returns df with simulation columns appended.
    """
    df = df.sort_values('date').reset_index(drop=True).copy()

    alloc = df.apply(lambda r: allocate(r['engine_a_score'], r.get('nifty_pe', np.nan)), axis=1)
    df['regime']     = alloc.apply(lambda a: a['regime'])
    df['equity_pct'] = alloc.apply(lambda a: a['equity_pct'])
    df['debt_pct']   = alloc.apply(lambda a: a['debt_pct'])
    df['gold_pct']   = alloc.apply(lambda a: a['gold_pct'])

    # Weights at month t apply to returns at month t+1 (shift weights forward)
    eq_w = df['equity_pct'].shift(1) / 100
    db_w = df['debt_pct'].shift(1)   / 100
    gd_w = df['gold_pct'].shift(1)   / 100

    df['portfolio_ret_m'] = (
        eq_w * df['nifty_ret_m'] +
        db_w * df['debt_ret_m'] +
        gd_w * df['gold_ret_m']
    )
    df.loc[0, 'portfolio_ret_m'] = 0  # first row has no prior signal

    df['portfolio_nav'] = initial_capital * (1 + df['portfolio_ret_m']).cumprod()
    df['nifty_nav']     = initial_capital * (1 + df['nifty_ret_m']).cumprod()

    # Static 60/40 benchmark (60% Nifty, 40% debt, monthly rebalance assumed)
    bench_6040 = 0.6 * df['nifty_ret_m'] + 0.4 * df['debt_ret_m']
    df['bench_6040_nav'] = initial_capital * (1 + bench_6040).cumprod()

    return df


# ----- METRICS -----
def compute_metrics(nav_series: pd.Series, freq: int = 12) -> dict:
    """CAGR, Sharpe, MaxDD, final NAV. freq=12 for monthly."""
    nav = nav_series.dropna()
    n = len(nav) - 1
    if n < 1:
        return {}

    total_ret = nav.iloc[-1] / nav.iloc[0] - 1
    cagr = (1 + total_ret) ** (freq / n) - 1

    rets = nav.pct_change().dropna()
    sharpe = (rets.mean() * freq) / (rets.std() * np.sqrt(freq)) if rets.std() > 0 else 0

    cummax   = nav.cummax()
    drawdown = (nav - cummax) / cummax
    max_dd   = drawdown.min()

    return {
        'CAGR':         f"{cagr*100:.2f}%",
        'Total Return': f"{total_ret*100:.2f}%",
        'Sharpe':       f"{sharpe:.2f}",
        'Max DD':       f"{max_dd*100:.2f}%",
        'Final NAV':    f"Rs.{nav.iloc[-1]:,.0f}",
    }


def regime_attribution(df: pd.DataFrame) -> pd.DataFrame:
    """Per-regime: months spent, avg monthly portfolio return, alpha vs Nifty."""
    g = df.groupby('regime').agg(
        months=('portfolio_ret_m', 'size'),
        avg_ret=('portfolio_ret_m', 'mean'),
        nifty_avg=('nifty_ret_m', 'mean'),
    )
    g['alpha_per_month'] = g['avg_ret'] - g['nifty_avg']
    g = g.sort_values('months', ascending=False)

    for col in ['avg_ret', 'nifty_avg', 'alpha_per_month']:
        g[col] = (g[col] * 100).round(2).astype(str) + '%'
    return g.reset_index()


# ----- ORCHESTRATOR -----
def run_full_backtest(input_csv: str, initial_capital: float = 1_000_000) -> dict:
    df = pd.read_csv(input_csv, parse_dates=['date'])
    sim = simulate_portfolio(df, initial_capital=initial_capital)
    return {
        'simulation':           sim,
        'parthsarthi_metrics':  compute_metrics(sim['portfolio_nav']),
        'nifty_metrics':        compute_metrics(sim['nifty_nav']),
        'bench_6040_metrics':   compute_metrics(sim['bench_6040_nav']),
        'regime_attribution':   regime_attribution(sim),
    }


if __name__ == '__main__':
    import sys
    csv_path = sys.argv[1] if len(sys.argv) > 1 else 'backtest_input.csv'
    print(f"Loading {csv_path}...")
    r = run_full_backtest(csv_path)

    print("\n=== PARTHSARTHI ENGINE A ===")
    for k, v in r['parthsarthi_metrics'].items(): print(f"  {k:15} {v}")
    print("\n=== NIFTY 50 (BUY-HOLD) ===")
    for k, v in r['nifty_metrics'].items():       print(f"  {k:15} {v}")
    print("\n=== STATIC 60/40 ===")
    for k, v in r['bench_6040_metrics'].items():  print(f"  {k:15} {v}")
    print("\n=== REGIME ATTRIBUTION ===")
    print(r['regime_attribution'].to_string(index=False))

    out = 'backtest_simulation_output.csv'
    r['simulation'].to_csv(out, index=False)
    print(f"\nFull simulation saved to {out}")
