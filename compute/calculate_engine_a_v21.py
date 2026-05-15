"""
============================================================
Engine A Dashboard v2.1
Compute Layer: Engine A Score Calculation
============================================================
Reads all CSVs from data/core/ and computes the Engine A score (0-100)
plus full component breakdown, regime determination, and allocation.

Inputs (CSVs):
  data/core/yfinance_global.csv  — global tickers
  data/core/angel_one_indian.csv — Nifty 50, India VIX
  data/core/bond_yields.csv      — India 10Y, 2Y G-Sec

Auxiliary (fetched live from yfinance for percentiles + moving averages):
  ^INDIAVIX  — 5Y history for VIX percentile
  ^NSEI      — 1Y history for Nifty 200 DMA
  BZ=F       — 1Y history for Brent 6M average
  GOLDBEES.NS — 1Y history for Gold 6M average
  ^TNX, INR=X — 60D history for direction calculations

Output:
  data/core/engine_a_current.json — latest score + full breakdown
  data/core/engine_a_history.csv  — append every run (for trend tracking)

Run: python compute/calculate_engine_a_v21.py
Cron: After every successful data fetch (separate workflow step)

Design principles:
  - Honest: missing data = PENDING_MANUAL, never faked
  - Partial scoring: shows "score / max_possible_today"
  - Audit-traceable: every sub-input shows its raw value
  - Graceful degradation: one component failure doesn't kill the whole score
  - No estimates: scores are computed from real data or flagged

Last updated: May 15, 2026
============================================================
"""

import json
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import pytz
import yfinance as yf


# ============================================================
# CONFIGURATION
# ============================================================

IST = pytz.timezone("Asia/Kolkata")

DATA_DIR = Path("data/core")
OUTPUT_JSON = DATA_DIR / "engine_a_current.json"
OUTPUT_HISTORY_CSV = DATA_DIR / "engine_a_history.csv"

# Input CSVs
YFINANCE_CSV = DATA_DIR / "yfinance_global.csv"
ANGEL_ONE_CSV = DATA_DIR / "angel_one_indian.csv"
BONDS_CSV = DATA_DIR / "bond_yields.csv"

# Allocation bands (hysteresis simplified for v1 — entry threshold only)
# In v2 we'll add proper hysteresis once we have score history
ALLOCATION_BANDS = [
    # (min_score_pct_of_max_to_enter, regime_name, equity_pct)
    (75, "FULL_DEPLOY", 85),
    (60, "AGGRESSIVE",  70),
    (45, "ACTIVE",      55),
    (35, "CAUTIOUS",    40),
    (25, "FREEZE",      25),
    (0,  "EXIT_ALL",    10),
]


# ============================================================
# HELPERS
# ============================================================

def now_ist() -> str:
    return datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S")


def read_latest_value(csv_path: Path, ticker: str) -> float | None:
    """Read the latest OK row for a given ticker from a CSV."""
    if not csv_path.exists():
        return None
    try:
        df = pd.read_csv(csv_path)
        # Filter for this ticker with OK status
        df = df[df["ticker"] == ticker]
        df = df[df["status"] == "OK"]
        if df.empty:
            return None
        return float(df.iloc[-1]["value"])
    except Exception as e:
        print(f"WARN: Failed to read {ticker} from {csv_path}: {e}")
        return None


def fetch_history(ticker: str, period: str) -> pd.DataFrame:
    """Fetch historical prices from yfinance with error handling."""
    try:
        data = yf.Ticker(ticker).history(period=period, auto_adjust=False)
        return data if not data.empty else pd.DataFrame()
    except Exception as e:
        print(f"WARN: yfinance history fetch failed for {ticker}: {e}")
        return pd.DataFrame()


def percentile_rank(series: pd.Series, value: float) -> float | None:
    """Return percentile rank (0-100) of value within series."""
    if series.empty or value is None:
        return None
    try:
        return float((series <= value).sum() / len(series) * 100)
    except Exception:
        return None


# ============================================================
# SCORING FUNCTIONS — One per sub-input
# ============================================================

# ---------- Component 1: Valuation (22 pts) ----------

def score_yield_gap(nifty_pe: float | None, gsec_10y: float | None) -> dict:
    """Earnings Yield Gap = (1/PE) - 10Y GSec.  10 pts."""
    if nifty_pe is None or gsec_10y is None:
        return {"value": None, "score": None, "max": 10, "status": "PENDING_MANUAL",
                "note": "Nifty PE manual entry needed" if gsec_10y else "No data"}
    try:
        earnings_yield = 100.0 / nifty_pe   # in %
        gap = earnings_yield - gsec_10y
        if gap > 1.0:    score = 10
        elif gap > 0:    score = 7
        elif gap > -1:   score = 5
        elif gap > -2:   score = 2
        else:            score = 0
        return {"value": round(gap, 3), "score": score, "max": 10, "status": "OK",
                "note": f"EY {earnings_yield:.2f}% - GSec {gsec_10y:.2f}% = {gap:+.2f}%"}
    except Exception as e:
        return {"value": None, "score": None, "max": 10, "status": "ERROR", "note": str(e)}


# ---------- Component 2: Credit & Rates (14 pts) ----------

def score_yield_curve(gsec_10y: float | None, gsec_2y: float | None) -> dict:
    """Yield Curve 10Y - 2Y.  3 pts."""
    if gsec_10y is None or gsec_2y is None:
        return {"value": None, "score": None, "max": 3, "status": "ERROR",
                "note": "Missing G-Sec data"}
    spread_bps = (gsec_10y - gsec_2y) * 100
    if spread_bps > 50:    score = 3
    elif spread_bps > 0:   score = 2
    elif spread_bps > -50: score = 1
    else:                  score = 0
    return {"value": round(spread_bps, 1), "score": score, "max": 3, "status": "OK",
            "note": f"10Y {gsec_10y:.3f}% - 2Y {gsec_2y:.3f}% = {spread_bps:+.1f} bps"}


# ---------- Component 3: Trend & Breadth (13 pts) ----------

def score_nifty_vs_200dma(nifty_current: float | None) -> dict:
    """Nifty 50 vs its 200-day SMA.  7 pts."""
    if nifty_current is None:
        return {"value": None, "score": None, "max": 7, "status": "ERROR",
                "note": "No Nifty 50 data"}
    hist = fetch_history("^NSEI", "1y")
    if hist.empty or len(hist) < 200:
        return {"value": None, "score": None, "max": 7, "status": "STALE",
                "note": "Insufficient history for 200 DMA"}
    sma_200 = float(hist["Close"].tail(200).mean())
    pct_diff = ((nifty_current - sma_200) / sma_200) * 100
    if pct_diff > 10:    score = 7
    elif pct_diff > 5:   score = 5
    elif pct_diff > 0:   score = 4
    elif pct_diff > -5:  score = 2
    else:                score = 0
    return {"value": round(pct_diff, 2), "score": score, "max": 7, "status": "OK",
            "note": f"Nifty {nifty_current:.0f} vs 200DMA {sma_200:.0f} = {pct_diff:+.2f}%"}


# ---------- Component 4: Volatility (10 pts) ----------

def score_vix_percentile(vix_current: float | None) -> dict:
    """India VIX vs 5Y percentile.  6 pts."""
    if vix_current is None:
        return {"value": None, "score": None, "max": 6, "status": "ERROR",
                "note": "No India VIX data"}
    hist = fetch_history("^INDIAVIX", "5y")
    if hist.empty:
        return {"value": None, "score": None, "max": 6, "status": "STALE",
                "note": "No VIX history available"}
    pctile = percentile_rank(hist["Close"], vix_current)
    if pctile is None:
        return {"value": None, "score": None, "max": 6, "status": "ERROR",
                "note": "Percentile calc failed"}
    if pctile < 30:    score = 6
    elif pctile < 60:  score = 4
    elif pctile < 80:  score = 2
    else:              score = 0
    return {"value": round(pctile, 1), "score": score, "max": 6, "status": "OK",
            "note": f"VIX {vix_current:.2f} = {pctile:.1f}th percentile of 5Y"}


def score_vix_vs_30d(vix_current: float | None) -> dict:
    """India VIX vs its 30-day moving average.  4 pts."""
    if vix_current is None:
        return {"value": None, "score": None, "max": 4, "status": "ERROR",
                "note": "No India VIX data"}
    hist = fetch_history("^INDIAVIX", "60d")
    if hist.empty or len(hist) < 30:
        return {"value": None, "score": None, "max": 4, "status": "STALE",
                "note": "Insufficient VIX history"}
    avg_30d = float(hist["Close"].tail(30).mean())
    pct_diff = ((vix_current - avg_30d) / avg_30d) * 100
    if pct_diff < -10:   score = 4
    elif pct_diff <= 10: score = 2
    else:                score = 0
    return {"value": round(pct_diff, 2), "score": score, "max": 4, "status": "OK",
            "note": f"VIX {vix_current:.2f} vs 30D avg {avg_30d:.2f} = {pct_diff:+.2f}%"}


# ---------- Component 7: Global Cross-Asset (12 pts) ----------

def score_us10y_direction(us10y_current: float | None) -> dict:
    """US 10Y direction over 30 days.  2 pts."""
    if us10y_current is None:
        return {"value": None, "score": None, "max": 2, "status": "ERROR",
                "note": "No US10Y data"}
    hist = fetch_history("^TNX", "60d")
    if hist.empty or len(hist) < 30:
        return {"value": None, "score": None, "max": 2, "status": "STALE",
                "note": "Insufficient US10Y history"}
    val_30d_ago = float(hist["Close"].iloc[-30])
    change_bps = (us10y_current - val_30d_ago) * 100
    if change_bps < -25:    score = 2
    elif change_bps < 0:    score = 1
    elif change_bps < 25:   score = 1
    else:                   score = 0
    return {"value": round(change_bps, 1), "score": score, "max": 2, "status": "OK",
            "note": f"US10Y {change_bps:+.1f} bps over 30D"}


def score_dxy(dxy_current: float | None) -> dict:
    """DXY level.  2 pts."""
    if dxy_current is None:
        return {"value": None, "score": None, "max": 2, "status": "ERROR",
                "note": "No DXY data"}
    if dxy_current < 100:   score = 2
    elif dxy_current < 104: score = 1
    else:                   score = 0
    return {"value": round(dxy_current, 2), "score": score, "max": 2, "status": "OK",
            "note": f"DXY {dxy_current:.2f}"}


def score_us_vix(us_vix_current: float | None) -> dict:
    """US VIX level.  3 pts."""
    if us_vix_current is None:
        return {"value": None, "score": None, "max": 3, "status": "ERROR",
                "note": "No US VIX data"}
    if us_vix_current < 15:    score = 3
    elif us_vix_current < 20:  score = 2
    elif us_vix_current < 25:  score = 1
    else:                      score = 0
    return {"value": round(us_vix_current, 2), "score": score, "max": 3, "status": "OK",
            "note": f"US VIX {us_vix_current:.2f}"}


def score_inr_direction(inr_current: float | None) -> dict:
    """INR/USD direction over 30 days.  2 pts."""
    if inr_current is None:
        return {"value": None, "score": None, "max": 2, "status": "ERROR",
                "note": "No INR data"}
    hist = fetch_history("INR=X", "60d")
    if hist.empty or len(hist) < 30:
        return {"value": None, "score": None, "max": 2, "status": "STALE",
                "note": "Insufficient INR history"}
    val_30d_ago = float(hist["Close"].iloc[-30])
    pct_change = ((inr_current - val_30d_ago) / val_30d_ago) * 100
    # NOTE: INR=X is "rupees per dollar". Rising = INR weakening.
    if pct_change < -1:    score = 2   # INR strengthening > 1%
    elif pct_change < 1:   score = 1   # Flat ±1%
    else:                  score = 0   # INR weakening > 1%
    return {"value": round(pct_change, 2), "score": score, "max": 2, "status": "OK",
            "note": f"INR/USD {pct_change:+.2f}% over 30D (positive = INR weaker)"}


def score_gold_inr(gold_current: float | None) -> dict:
    """GOLDBEES vs its 6-month average. 3 pts."""
    if gold_current is None:
        return {"value": None, "score": None, "max": 3, "status": "ERROR",
                "note": "No GOLDBEES data"}
    hist = fetch_history("GOLDBEES.NS", "1y")
    if hist.empty or len(hist) < 120:
        return {"value": None, "score": None, "max": 3, "status": "STALE",
                "note": "Insufficient GOLDBEES history"}
    avg_6m = float(hist["Close"].tail(120).mean())  # ~6 months of trading days
    pct_diff = ((gold_current - avg_6m) / avg_6m) * 100
    if pct_diff < -10:    score = 3
    elif pct_diff < 0:    score = 2
    elif pct_diff < 10:   score = 1
    else:                 score = 0
    return {"value": round(pct_diff, 2), "score": score, "max": 3, "status": "OK",
            "note": f"GOLDBEES {gold_current:.2f} vs 6M avg {avg_6m:.2f} = {pct_diff:+.2f}%"}


# ---------- Component 8: Crude (5 pts) ----------

def score_brent(brent_current: float | None) -> dict:
    """Brent Crude vs its 6-month average. 5 pts."""
    if brent_current is None:
        return {"value": None, "score": None, "max": 5, "status": "ERROR",
                "note": "No Brent data"}
    hist = fetch_history("BZ=F", "1y")
    if hist.empty or len(hist) < 120:
        return {"value": None, "score": None, "max": 5, "status": "STALE",
                "note": "Insufficient Brent history"}
    avg_6m = float(hist["Close"].tail(120).mean())
    pct_diff = ((brent_current - avg_6m) / avg_6m) * 100
    if pct_diff < -15:    score = 5
    elif pct_diff < -5:   score = 4
    elif pct_diff < 5:    score = 3
    elif pct_diff < 15:   score = 1
    else:                 score = 0
    return {"value": round(pct_diff, 2), "score": score, "max": 5, "status": "OK",
            "note": f"Brent ${brent_current:.2f} vs 6M avg ${avg_6m:.2f} = {pct_diff:+.2f}%"}


# ---------- Manual Placeholders (Tier 4 — entered via dashboard) ----------

def manual_placeholder(name: str, max_pts: int) -> dict:
    """Standard placeholder for sub-inputs requiring manual entry."""
    return {"value": None, "score": None, "max": max_pts, "status": "PENDING_MANUAL",
            "note": f"{name} — enter via dashboard (Tier 4 monthly)"}


# ============================================================
# REGIME DETERMINATION
# ============================================================

def determine_regime(score_pct: float) -> tuple[str, int]:
    """Map score % of max to regime + equity allocation %."""
    for min_pct, regime, equity_pct in ALLOCATION_BANDS:
        if score_pct >= min_pct:
            return regime, equity_pct
    return "EXIT_ALL", 10


# ============================================================
# MAIN COMPUTATION
# ============================================================

def compute_engine_a():
    print(f"[{now_ist()}] Starting Engine A v2.1 compute layer...")
    print("=" * 60)

    # ---- Load latest data from CSVs ----
    nifty_50      = read_latest_value(ANGEL_ONE_CSV, "NIFTY 50")
    india_vix     = read_latest_value(ANGEL_ONE_CSV, "INDIA VIX")
    us_10y        = read_latest_value(YFINANCE_CSV, "^TNX")
    dxy           = read_latest_value(YFINANCE_CSV, "DX-Y.NYB")
    us_vix        = read_latest_value(YFINANCE_CSV, "^VIX")
    inr           = read_latest_value(YFINANCE_CSV, "INR=X")
    brent         = read_latest_value(YFINANCE_CSV, "BZ=F")
    goldbees      = read_latest_value(YFINANCE_CSV, "GOLDBEES.NS")
    gsec_10y      = read_latest_value(BONDS_CSV, "india-10-year-bond-yield")
    gsec_2y       = read_latest_value(BONDS_CSV, "india-2-year-bond-yield")

    print(f"Loaded data:")
    print(f"  Nifty 50:    {nifty_50}")
    print(f"  India VIX:   {india_vix}")
    print(f"  US 10Y:      {us_10y}")
    print(f"  DXY:         {dxy}")
    print(f"  US VIX:      {us_vix}")
    print(f"  INR/USD:     {inr}")
    print(f"  Brent:       {brent}")
    print(f"  GOLDBEES:    {goldbees}")
    print(f"  G-Sec 10Y:   {gsec_10y}")
    print(f"  G-Sec 2Y:    {gsec_2y}")
    print("-" * 60)

    # ---- Score each sub-input ----
    components = {
        "C1_valuation": {
            "weight": 22, "name": "Valuation",
            "sub_inputs": {
                "yield_gap":        score_yield_gap(None, gsec_10y),
                "nifty_pe_pctile":  manual_placeholder("Nifty PE %ile", 6),
                "mcap_gdp_pctile":  manual_placeholder("MCap/GDP %ile", 6),
            }
        },
        "C2_credit_rates": {
            "weight": 14, "name": "Credit & Rates",
            "sub_inputs": {
                "aaa_spread_pctile":  manual_placeholder("AAA-GSec spread %ile", 8),
                "yield_curve_10y_2y": score_yield_curve(gsec_10y, gsec_2y),
                "credit_growth_yoy":  manual_placeholder("Bank credit growth YoY", 3),
            }
        },
        "C3_trend_breadth": {
            "weight": 13, "name": "Trend & Breadth",
            "sub_inputs": {
                "nifty_vs_200dma":      score_nifty_vs_200dma(nifty_50),
                "pct_above_200dma":     manual_placeholder("% Nifty 500 above 200 DMA", 6),
            }
        },
        "C4_volatility": {
            "weight": 10, "name": "Volatility",
            "sub_inputs": {
                "india_vix_pctile":  score_vix_percentile(india_vix),
                "vix_vs_30d_avg":    score_vix_vs_30d(india_vix),
            }
        },
        "C5_flows": {
            "weight": 12, "name": "Flows",
            "sub_inputs": {
                "fii_30d":   manual_placeholder("FII 30D net flow", 5),
                "dii_30d":   manual_placeholder("DII 30D net flow", 4),
                "sip_yoy":   manual_placeholder("SIP YoY%", 3),
            }
        },
        "C6_macro_india": {
            "weight": 12, "name": "Macro India",
            "sub_inputs": {
                "rbi_stance": manual_placeholder("RBI stance", 3),
                "cpi_yoy":    manual_placeholder("CPI YoY direction", 3),
                "pmi_mfg":    manual_placeholder("Manufacturing PMI", 3),
                "gst_yoy":    manual_placeholder("GST YoY%", 3),
            }
        },
        "C7_global_cross_asset": {
            "weight": 12, "name": "Global Cross-Asset",
            "sub_inputs": {
                "us_10y_direction": score_us10y_direction(us_10y),
                "dxy":              score_dxy(dxy),
                "us_vix":           score_us_vix(us_vix),
                "inr_direction":    score_inr_direction(inr),
                "gold_inr_vs_6m":   score_gold_inr(goldbees),
            }
        },
        "C8_crude": {
            "weight": 5, "name": "Crude",
            "sub_inputs": {
                "brent_vs_6m": score_brent(brent),
            }
        },
    }

    # ---- Aggregate scores ----
    total_score = 0
    total_max_available = 0
    total_max_possible = 100
    stale_inputs = []
    pending_manual = []

    for comp_key, comp in components.items():
        comp_score = 0
        comp_max_available = 0
        for sub_key, sub in comp["sub_inputs"].items():
            if sub["status"] == "OK":
                comp_score += sub["score"] if sub["score"] is not None else 0
                comp_max_available += sub["max"]
            elif sub["status"] == "PENDING_MANUAL":
                pending_manual.append(f"{comp_key}.{sub_key}")
            elif sub["status"] in ("STALE", "ERROR"):
                stale_inputs.append(f"{comp_key}.{sub_key}")
        comp["score"] = comp_score
        comp["max_available"] = comp_max_available
        comp["pct_of_max_available"] = round(
            (comp_score / comp_max_available * 100) if comp_max_available else 0, 1
        )
        total_score += comp_score
        total_max_available += comp_max_available

    score_pct = (total_score / total_max_available * 100) if total_max_available else 0
    regime, equity_pct = determine_regime(score_pct)

    # ---- Print breakdown ----
    print(f"\n{'Component':<28} {'Score':<10} {'Max Avail':<12} {'% of Max':<10}")
    print("-" * 60)
    for comp_key, comp in components.items():
        print(f"{comp['name']:<28} {comp['score']:<10} {comp['max_available']:<12} "
              f"{comp['pct_of_max_available']:.1f}%")
    print("-" * 60)
    print(f"\n📊 TOTAL SCORE:        {total_score} / {total_max_available} "
          f"(out of theoretical max {total_max_possible})")
    print(f"📈 SCORE % OF MAX:     {score_pct:.1f}%")
    print(f"🎯 REGIME:             {regime}")
    print(f"💼 EQUITY ALLOCATION:  {equity_pct}%")
    print(f"\n⏳ PENDING MANUAL:     {len(pending_manual)} sub-inputs")
    if pending_manual:
        for item in pending_manual:
            print(f"     - {item}")
    if stale_inputs:
        print(f"\n⚠️  STALE/ERROR:        {len(stale_inputs)} sub-inputs")
        for item in stale_inputs:
            print(f"     - {item}")
    print("=" * 60)

    # ---- Build output JSON ----
    output = {
        "schema_version": "v2.1",
        "computed_at_ist": now_ist(),
        "score": total_score,
        "max_available_today": total_max_available,
        "max_theoretical": total_max_possible,
        "score_pct_of_max_available": round(score_pct, 2),
        "regime": regime,
        "regime_equity_pct": equity_pct,
        "pending_manual_count": len(pending_manual),
        "stale_inputs_count": len(stale_inputs),
        "pending_manual": pending_manual,
        "stale_inputs": stale_inputs,
        "components": components,
        "raw_inputs": {
            "nifty_50": nifty_50,
            "india_vix": india_vix,
            "us_10y": us_10y,
            "dxy": dxy,
            "us_vix": us_vix,
            "inr_usd": inr,
            "brent_crude": brent,
            "goldbees": goldbees,
            "gsec_10y": gsec_10y,
            "gsec_2y": gsec_2y,
        }
    }

    # ---- Write JSON ----
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_JSON, "w") as f:
        json.dump(output, f, indent=2, default=str)
    print(f"\n✅ Wrote {OUTPUT_JSON}")

    # ---- Append to history CSV ----
    history_row = {
        "timestamp_ist": now_ist(),
        "score": total_score,
        "max_available": total_max_available,
        "score_pct": round(score_pct, 2),
        "regime": regime,
        "equity_pct": equity_pct,
        "pending_manual": len(pending_manual),
        "stale_count": len(stale_inputs),
    }
    history_df = pd.DataFrame([history_row])
    if OUTPUT_HISTORY_CSV.exists():
        history_df.to_csv(OUTPUT_HISTORY_CSV, mode="a", header=False, index=False)
    else:
        history_df.to_csv(OUTPUT_HISTORY_CSV, mode="w", header=True, index=False)
    print(f"✅ Appended to {OUTPUT_HISTORY_CSV}")

    print(f"\n[{now_ist()}] Compute layer done.\n")
    return output


if __name__ == "__main__":
    compute_engine_a()
