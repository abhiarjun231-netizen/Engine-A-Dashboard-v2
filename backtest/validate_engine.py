"""
validate_engine.py
Generates a synthetic 18-year dataset that exercises every regime band,
runs the backtest engine on it, and plots the result.

Purpose: prove the simulation logic is correct BEFORE we invest hours
reconstructing real historical scores. If the synthetic run shows sensible
behavior (drawdown smaller than Nifty in crashes, less upside in bull runs,
positive long-run alpha if scoring is informative), the engine logic is sound.
"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from backtest_engine import simulate_portfolio, compute_metrics, regime_attribution

np.random.seed(42)


def make_synthetic_data():
    """216 months of synthetic but realistic-feeling Indian market data.

    Built-in regime events:
      - 2008 GFC: scores crash, equity crashes, gold rallies
      - 2020 COVID: same pattern, shorter
      - 2022 vol cluster: scores oscillate mid-band
    """
    dates = pd.date_range('2008-01-31', '2025-12-31', freq='ME')
    n = len(dates)

    # Engine A scores: slow cycle around 50, noise added, then crisis overrides
    base   = 50 + 20 * np.sin(np.linspace(0, 6 * np.pi, n))
    noise  = np.random.normal(0, 8, n)
    scores = np.clip(base + noise, 10, 90)

    # GFC: Sep 2008 - Mar 2009 (months 8-14): score collapses 75 -> 15
    scores[8:15] = np.linspace(75, 15, 7)
    # COVID: Mar-May 2020 (months 146-148): 60 -> 20
    scores[146:149] = np.linspace(60, 20, 3)
    # 2022 vol cluster: months 168-180
    scores[168:180] = np.random.uniform(30, 55, 12)

    # Nifty PE: anti-correlated with score (cheap when fearful), realistic 14-32
    nifty_pe = 22 - (scores - 50) * 0.15 + np.random.normal(0, 1.5, n)
    nifty_pe = np.clip(nifty_pe, 14, 32)

    # Equity returns: drift biased by score, vol ~5.5%/mo
    # (score above 50 -> mildly bullish next month, below 50 -> mildly bearish)
    eq_drift = 0.01 + (scores - 50) * 0.0003
    eq_ret = eq_drift + np.random.normal(0, 0.055, n)
    eq_ret[8:15]    = np.random.normal(-0.08, 0.04, 7)   # GFC
    eq_ret[146:149] = np.random.normal(-0.10, 0.03, 3)   # COVID

    # Debt: smooth, ~7% annual / ~1% monthly vol
    debt_ret = np.random.normal(0.006, 0.008, n)

    # Gold INR: ~10% annual, crisis hedge bumps
    gold_ret = np.random.normal(0.008, 0.04, n)
    gold_ret[8:15]    += 0.03
    gold_ret[146:149] += 0.04

    return pd.DataFrame({
        'date':           dates,
        'engine_a_score': scores,
        'nifty_pe':       nifty_pe,
        'nifty_ret_m':    eq_ret,
        'debt_ret_m':     debt_ret,
        'gold_ret_m':     gold_ret,
    })


def main():
    df  = make_synthetic_data()
    sim = simulate_portfolio(df, initial_capital=1_000_000)

    print("=" * 60)
    print("SYNTHETIC VALIDATION RUN  (Jan 2008 – Dec 2025, monthly)")
    print("=" * 60)

    print("\n--- PARTHSARTHI ENGINE A ---")
    for k, v in compute_metrics(sim['portfolio_nav']).items():
        print(f"  {k:15} {v}")
    print("\n--- NIFTY BUY-HOLD ---")
    for k, v in compute_metrics(sim['nifty_nav']).items():
        print(f"  {k:15} {v}")
    print("\n--- 60/40 BENCHMARK ---")
    for k, v in compute_metrics(sim['bench_6040_nav']).items():
        print(f"  {k:15} {v}")

    print("\n--- REGIME ATTRIBUTION ---")
    print(regime_attribution(sim).to_string(index=False))

    # Chart: brand colors from handover
    NAVY    = '#0A1628'
    SAFFRON = '#D97706'
    CREAM   = '#FDFBF5'

    fig, axes = plt.subplots(3, 1, figsize=(11, 12), facecolor=CREAM)
    for ax in axes:
        ax.set_facecolor(CREAM)
        for spine in ax.spines.values():
            spine.set_color(NAVY); spine.set_linewidth(0.7)
        ax.tick_params(colors=NAVY)

    # NAV comparison
    axes[0].plot(sim['date'], sim['portfolio_nav'] / 1e5,
                 label='Parthsarthi', color=SAFFRON, lw=2.2)
    axes[0].plot(sim['date'], sim['nifty_nav'] / 1e5,
                 label='Nifty Buy-Hold', color=NAVY, lw=1.5, alpha=0.85)
    axes[0].plot(sim['date'], sim['bench_6040_nav'] / 1e5,
                 label='60/40', color='gray', lw=1.4, alpha=0.7, ls='--')
    axes[0].set_title('Portfolio NAV  (Rs. Lakhs, starting Rs. 10L)',
                      color=NAVY, fontsize=13, fontweight='bold', pad=12)
    axes[0].legend(loc='upper left', frameon=False); axes[0].grid(alpha=0.2)

    # Score over time
    axes[1].plot(sim['date'], sim['engine_a_score'], color=NAVY, lw=1.1)
    for thr, label, col in [(75, 'FULL_DEPLOY', '#16a34a'),
                            (60, 'AGGRESSIVE',  '#65a30d'),
                            (45, 'ACTIVE',      SAFFRON),
                            (35, 'CAUTIOUS',    '#ea580c'),
                            (25, 'FREEZE',      '#dc2626')]:
        axes[1].axhline(thr, ls='--', color=col, alpha=0.45, lw=0.9)
        axes[1].text(sim['date'].iloc[-1], thr + 0.5, f' {label}',
                     fontsize=7, color=col, va='bottom')
    axes[1].set_title('Engine A Score Over Time',
                      color=NAVY, fontsize=13, fontweight='bold', pad=12)
    axes[1].grid(alpha=0.2); axes[1].set_ylim(0, 100)

    # Equity allocation
    axes[2].fill_between(sim['date'], 0, sim['equity_pct'], color=SAFFRON, alpha=0.35)
    axes[2].plot(sim['date'], sim['equity_pct'], color=SAFFRON, lw=1.5)
    axes[2].set_title('Equity Allocation (%)',
                      color=NAVY, fontsize=13, fontweight='bold', pad=12)
    axes[2].grid(alpha=0.2); axes[2].set_ylim(0, 100)

    plt.tight_layout()
    plt.savefig('validation_chart.png', dpi=140, bbox_inches='tight', facecolor=CREAM)
    print(f"\nChart saved -> validation_chart.png")

    sim.to_csv('validation_simulation.csv', index=False)
    print(f"Simulation saved -> validation_simulation.csv")


if __name__ == '__main__':
    main()
