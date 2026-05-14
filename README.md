# Engine A Dashboard v2.1

Institutional-grade market regime model for Indian equities.

**Status:** Build in progress  
**Last updated:** May 14, 2026  
**Built by:** Abhishek (mobile-only, zero coding background, learning in public)

---

## What This Is

A 5-engine investment system for Indian equity, debt, and gold markets.
Engine A (The Director) is the macro regime scorer that allocates capital
across the other engines based on an 8-component composite score (0-100).

## Architecture

- **Core data** drives Engine A score (sacred, validated, backtested)
- **Reference data** powers daily report (display-only, never affects score)
- **Dual deployment:** Streamlit admin dashboard + GitHub Pages public dashboard
- **Compute layer:** GitHub Actions cron writes CSVs; dashboards read CSVs

## Engine A Components (100 pts total)

1. Valuation (22 pts)
2. Credit & Rates (14 pts)
3. Trend & Breadth (13 pts)
4. Volatility (10 pts)
5. Flows (12 pts)
6. Macro India (12 pts)
7. Global Cross-Asset (12 pts)
8. Crude (5 pts)

## Build Phases

- **Phase 1** (M1–M5): Data pipeline automation
- **Phase 2** (M6–M8): Production UI + dashboards
- **Phase 3** (M9–M10): Daily market report (3 AM IST cron)
- **Phase 4** (M11): Backtest validation

## License

MIT
