"""
============================================================
Engine A Dashboard v2.1
Compute Layer: Engine A Score Calculation — v2 (with manual inputs)
============================================================
v2 changes from v1:
  - Reads data/core/manual_inputs.csv and wires 12 manual fields into score
  - Nifty PE (manual) now feeds yield_gap calculation
  - 12 new scoring functions with institutional bands
  - PE Bubble safety override (Nifty PE > 26 caps equity at 70%)
  - Same JSON output schema (backward compatible with dashboard app.py)

Inputs (CSVs):
  data/core/yfinance_global.csv    — global tickers
  data/core/angel_one_indian.csv   — Nifty 50, India VIX
  data/core/bond_yields.csv        — India 10Y, 2Y G-Sec
  data/core/manual_inputs.csv      — 12 manual fields (NEW in v2)

Auxiliary (fetched live from yfinance):
  ^INDIAVIX, ^NSEI, BZ=F, GOLDBEES.NS, ^TNX, INR=X

Output:
  data/core/engine_a_current.json
  data/core/engine_a_history.csv

Run: python compute/calculate_engine_a_v21.py
Cron: After every successful data fetch

Design principles:
  - Honest: missing manual = PENDING_MANUAL, never faked
  - Partial scoring: shows "score / max_possible_today"
  - Sanity checks: numerical inputs validated against ranges
  - Graceful degradation: one field failure doesn't kill the whole score
  - No estimates: scores from real data or flagged

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

YFINANCE_CSV = DATA_DIR / "yfinance_global.csv"
ANGEL_ONE_CSV = DATA_DIR / "angel_one_indian.csv"
BONDS_CSV = DATA_DIR / "bond_yields.csv"
MANUAL_INPUTS_CSV = DATA_DIR / "manual_inputs.csv"   # NEW in v2

ALLOCATION_BANDS = [
    (75, "FULL_DEPLOY", 85),
    (60, "AGGRESSIVE",  70),
    (45, "ACTIVE",      55),
    (35, "CAUTIOUS",    40),
    (25, "FREEZE",      25),
    (0,  "EXIT_ALL",    10),
]

# Sanity ranges for manual numeric inputs (must match form widget bounds)
MANUAL_RANGES = {
    "nifty_pe_ttm":       (5.0,    50.0),
    "nifty_pe_pctile":    (0.0,    100.0),
    "mcap_gdp_ratio":     (10.0,   400.0),    # raw % (India range ~25-290%)
    "aaa_spread_bps":     (0.0,    500.0),    # raw basis points
    "credit_growth_yoy":  (-10.0,  30.0),
    "pct_above_200dma":   (0.0,    100.0),
    "fii_latest_month":   (-200000.0, 200000.0),   # single month total
    "dii_latest_month":   (-100000.0, 200000.0),   # single month total
    "sip_yoy":            (-30.0,  50.0),
    "cpi_yoy_latest":     (-2.0,   15.0),     # raw CPI %
    "pmi_mfg":            (30.0,   70.0),
    "gst_yoy":            (-30.0,  50.0),
}

# PE Bubble safety override threshold (per strategy doc)
PE_BUBBLE_THRESHOLD = 26.0
PE_BUBBLE_EQUITY_CAP = 70


# ============================================================
# HELPERS
# ============================================================

def now_ist() -> str:
    return datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S")


def read_latest_value(csv_path: Path, ticker: str):
    """Read the latest OK row for a given ticker from a CSV."""
    if not csv_path.exists():
        return None
    try:
        df = pd.read_csv(csv_path)
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


def percentile_rank(series: pd.Series, value: float):
    """Return percentile rank (0-100) of value within series."""
    if series.empty or value is None:
        return None
    try:
        return float((series <= value).sum() / len(series) * 100)
    except Exception:
        return None


def load_manual_inputs_df() -> pd.DataFrame:
    """
    NEW in v2.1: Return FULL manual_inputs.csv as DataFrame for history lookups
    (e.g. CPI direction needs last 3 saves of cpi_yoy_latest).
    Empty DataFrame if CSV missing.
    """
    cols = ["timestamp_ist", "field", "value", "note"]
    if not MANUAL_INPUTS_CSV.exists():
        return pd.DataFrame(columns=cols)
    try:
        df = pd.read_csv(MANUAL_INPUTS_CSV)
        if df.empty:
            return pd.DataFrame(columns=cols)
        df = df.sort_values("timestamp_ist")
        return df
    except Exception as e:
        print(f"WARN: Failed to load manual_inputs.csv as DataFrame: {e}")
        return pd.DataFrame(columns=cols)


def get_field_history(df: pd.DataFrame, field: str, n: int = 3) -> list:
    """
    Return last n numeric values for a field, oldest -> newest.
    Used by score_cpi_yoy_with_direction to derive 3M trend automatically.
    """
    if df.empty:
        return []
    field_df = df[df["field"] == field]
    if field_df.empty:
        return []
    values = []
    for _, row in field_df.tail(n).iterrows():
        try:
            v = float(row["value"])
            values.append(v)
        except (TypeError, ValueError):
            continue
    return values


def load_manual_inputs() -> dict:
    """
    Read manual_inputs.csv (long format) and return latest value
    per field. Returns dict: {field_key: value}.

    Empty dict if CSV missing or empty — every field will be PENDING_MANUAL.
    """
    if not MANUAL_INPUTS_CSV.exists():
        print(f"INFO: {MANUAL_INPUTS_CSV} not found — all manual fields PENDING")
        return {}
    try:
        df = pd.read_csv(MANUAL_INPUTS_CSV)
        if df.empty:
            print(f"INFO: {MANUAL_INPUTS_CSV} is empty (header-only) — all manual PENDING")
            return {}
        df = df.sort_values("timestamp_ist")
        latest = df.groupby("field").tail(1)
        result = {}
        for _, row in latest.iterrows():
            key = str(row["field"])
            val = row["value"]
            if pd.isna(val) or str(val).lower() == "nan":
                continue
            result[key] = val
        print(f"INFO: Loaded {len(result)} manual input(s): {list(result.keys())}")
        return result
    except Exception as e:
        print(f"WARN: Failed to load manual_inputs.csv: {e}")
        return {}


def _validate_numeric(value, field_key: str):
    """Convert to float and validate range. Returns (float_value, error_msg)."""
    if value is None:
        return None, "missing"
    try:
        v = float(value)
    except (TypeError, ValueError):
        return None, f"non-numeric: {value!r}"
    lo, hi = MANUAL_RANGES.get(field_key, (-1e9, 1e9))
    if not (lo <= v <= hi):
        return None, f"out of range [{lo}, {hi}]: {v}"
    return v, None


def _pending(name: str, max_pts: int) -> dict:
    return {"value": None, "score": None, "max": max_pts,
            "status": "PENDING_MANUAL",
            "note": f"{name} \u2014 enter via dashboard Admin tab"}


def _error(max_pts: int, msg: str) -> dict:
    return {"value": None, "score": None, "max": max_pts,
            "status": "ERROR", "note": msg}


# ============================================================
# SCORING FUNCTIONS — AUTO (unchanged from v1)
# ============================================================

# ---------- Component 1: Valuation (22 pts) ----------

def score_yield_gap(nifty_pe, gsec_10y) -> dict:
    """Earnings Yield Gap = (100/PE) - 10Y GSec.  10 pts.
    
    v2 change: nifty_pe now comes from manual_inputs.csv, not None.
    """
    if nifty_pe is None or gsec_10y is None:
        if gsec_10y is None:
            return _error(10, "Missing G-Sec 10Y")
        return _pending("Nifty PE TTM (drives yield gap)", 10)
    try:
        nifty_pe_f = float(nifty_pe)
        earnings_yield = 100.0 / nifty_pe_f
        gap = earnings_yield - gsec_10y
        if gap > 1.0:    score = 10
        elif gap > 0:    score = 7
        elif gap > -1:   score = 5
        elif gap > -2:   score = 2
        else:            score = 0
        return {"value": round(gap, 3), "score": score, "max": 10, "status": "OK",
                "note": f"EY {earnings_yield:.2f}% - GSec {gsec_10y:.2f}% = {gap:+.2f}% "
                        f"(PE {nifty_pe_f:.2f})"}
    except Exception as e:
        return _error(10, str(e))


# ---------- Component 2: Credit & Rates (auto part) ----------

def score_yield_curve(gsec_10y, gsec_2y) -> dict:
    """Yield Curve 10Y - 2Y.  3 pts."""
    if gsec_10y is None or gsec_2y is None:
        return _error(3, "Missing G-Sec data")
    spread_bps = (gsec_10y - gsec_2y) * 100
    if spread_bps > 50:    score = 3
    elif spread_bps > 0:   score = 2
    elif spread_bps > -50: score = 1
    else:                  score = 0
    return {"value": round(spread_bps, 1), "score": score, "max": 3, "status": "OK",
            "note": f"10Y {gsec_10y:.3f}% - 2Y {gsec_2y:.3f}% = {spread_bps:+.1f} bps"}


# ---------- Component 3: Trend & Breadth (auto part) ----------

def score_nifty_vs_200dma(nifty_current) -> dict:
    """Nifty 50 vs its 200-day SMA.  7 pts."""
    if nifty_current is None:
        return _error(7, "No Nifty 50 data")
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


# ---------- Component 4: Volatility (10 pts, both auto) ----------

def score_vix_percentile(vix_current) -> dict:
    """India VIX vs 5Y percentile.  6 pts."""
    if vix_current is None:
        return _error(6, "No India VIX data")
    hist = fetch_history("^INDIAVIX", "5y")
    if hist.empty:
        return {"value": None, "score": None, "max": 6, "status": "STALE",
                "note": "No VIX history available"}
    pctile = percentile_rank(hist["Close"], vix_current)
    if pctile is None:
        return _error(6, "Percentile calc failed")
    if pctile < 30:    score = 6
    elif pctile < 60:  score = 4
    elif pctile < 80:  score = 2
    else:              score = 0
    return {"value": round(pctile, 1), "score": score, "max": 6, "status": "OK",
            "note": f"VIX {vix_current:.2f} = {pctile:.1f}th percentile of 5Y"}


def score_vix_vs_30d(vix_current) -> dict:
    """India VIX vs its 30-day moving average.  4 pts."""
    if vix_current is None:
        return _error(4, "No India VIX data")
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


# ---------- Component 7: Global Cross-Asset (all auto) ----------

def score_us10y_direction(us10y_current) -> dict:
    """US 10Y direction over 30 days.  2 pts."""
    if us10y_current is None:
        return _error(2, "No US10Y data")
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


def score_dxy(dxy_current) -> dict:
    """DXY level.  2 pts."""
    if dxy_current is None:
        return _error(2, "No DXY data")
    if dxy_current < 100:   score = 2
    elif dxy_current < 104: score = 1
    else:                   score = 0
    return {"value": round(dxy_current, 2), "score": score, "max": 2, "status": "OK",
            "note": f"DXY {dxy_current:.2f}"}


def score_us_vix(us_vix_current) -> dict:
    """US VIX level.  3 pts."""
    if us_vix_current is None:
        return _error(3, "No US VIX data")
    if us_vix_current < 15:    score = 3
    elif us_vix_current < 20:  score = 2
    elif us_vix_current < 25:  score = 1
    else:                      score = 0
    return {"value": round(us_vix_current, 2), "score": score, "max": 3, "status": "OK",
            "note": f"US VIX {us_vix_current:.2f}"}


def score_inr_direction(inr_current) -> dict:
    """INR/USD direction over 30 days.  2 pts."""
    if inr_current is None:
        return _error(2, "No INR data")
    hist = fetch_history("INR=X", "60d")
    if hist.empty or len(hist) < 30:
        return {"value": None, "score": None, "max": 2, "status": "STALE",
                "note": "Insufficient INR history"}
    val_30d_ago = float(hist["Close"].iloc[-30])
    pct_change = ((inr_current - val_30d_ago) / val_30d_ago) * 100
    if pct_change < -1:    score = 2
    elif pct_change < 1:   score = 1
    else:                  score = 0
    return {"value": round(pct_change, 2), "score": score, "max": 2, "status": "OK",
            "note": f"INR/USD {pct_change:+.2f}% over 30D (positive = INR weaker)"}


def score_gold_inr(gold_current) -> dict:
    """GOLDBEES vs its 6-month average. 3 pts."""
    if gold_current is None:
        return _error(3, "No GOLDBEES data")
    hist = fetch_history("GOLDBEES.NS", "1y")
    if hist.empty or len(hist) < 120:
        return {"value": None, "score": None, "max": 3, "status": "STALE",
                "note": "Insufficient GOLDBEES history"}
    avg_6m = float(hist["Close"].tail(120).mean())
    pct_diff = ((gold_current - avg_6m) / avg_6m) * 100
    if pct_diff < -10:    score = 3
    elif pct_diff < 0:    score = 2
    elif pct_diff < 10:   score = 1
    else:                 score = 0
    return {"value": round(pct_diff, 2), "score": score, "max": 3, "status": "OK",
            "note": f"GOLDBEES {gold_current:.2f} vs 6M avg {avg_6m:.2f} = {pct_diff:+.2f}%"}


# ---------- Component 8: Crude (all auto) ----------

def score_brent(brent_current) -> dict:
    """Brent Crude vs its 6-month average. 5 pts."""
    if brent_current is None:
        return _error(5, "No Brent data")
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


# ============================================================
# SCORING FUNCTIONS — MANUAL (NEW in v2)
# Institutional bands; see Engine A v2.1 design doc.
# ============================================================

# ---------- C1: Valuation manuals ----------

def score_nifty_pe_pctile(val) -> dict:
    """Nifty PE 10Y percentile.  6 pts. Low percentile = cheap = good."""
    if val is None:
        return _pending("Nifty PE 10Y percentile", 6)
    v, err = _validate_numeric(val, "nifty_pe_pctile")
    if err:
        return _error(6, f"nifty_pe_pctile {err}")
    if v <= 20:    score = 6
    elif v <= 40:  score = 4
    elif v <= 60:  score = 2
    elif v <= 80:  score = 1
    else:          score = 0
    return {"value": round(v, 1), "score": score, "max": 6, "status": "OK",
            "note": f"Nifty PE at {v:.1f}th percentile of 10Y "
                    f"({'cheap' if v <= 30 else 'fair' if v <= 60 else 'expensive'})"}


def score_mcap_gdp_ratio(val) -> dict:
    """
    MCap/GDP raw ratio %.  6 pts.  v2.1: takes RAW % (e.g. 242.75), not percentile.
    Bands calibrated to India's 20Y range (25-290%, median ~87%, +1σ ~127%).
    """
    if val is None:
        return _pending("MCap/GDP ratio (raw %)", 6)
    v, err = _validate_numeric(val, "mcap_gdp_ratio")
    if err:
        return _error(6, f"mcap_gdp_ratio {err}")
    if v <= 55:     score = 6  # deeply undervalued (below -1σ)
    elif v <= 80:   score = 4  # undervalued
    elif v <= 110:  score = 2  # fair (around median)
    elif v <= 160:  score = 1  # expensive (above +1σ)
    else:           score = 0  # very expensive (near peaks)
    return {"value": round(v, 2), "score": score, "max": 6, "status": "OK",
            "note": f"MCap/GDP {v:.1f}% "
                    f"({'deep value' if v <= 55 else 'undervalued' if v <= 80 else 'fair' if v <= 110 else 'expensive' if v <= 160 else 'very expensive'})"}


# ---------- C2: Credit & Rates manuals ----------

def score_aaa_spread_bps(val) -> dict:
    """
    AAA-GSec spread RAW bps.  8 pts.  v2.1: takes RAW basis points (e.g. 73), not percentile.
    Bands calibrated to India's 5Y range (30 bps tight - 200+ bps crisis).
    """
    if val is None:
        return _pending("AAA-GSec spread (raw bps)", 8)
    v, err = _validate_numeric(val, "aaa_spread_bps")
    if err:
        return _error(8, f"aaa_spread_bps {err}")
    if v <= 50:     score = 8  # very tight, excellent credit conditions
    elif v <= 75:   score = 6  # tight, healthy
    elif v <= 100:  score = 4  # normal
    elif v <= 150:  score = 2  # widening, stress emerging
    else:           score = 0  # crisis-level
    return {"value": round(v, 0), "score": score, "max": 8, "status": "OK",
            "note": f"AAA-GSec spread {v:.0f} bps "
                    f"({'very tight' if v <= 50 else 'tight, healthy' if v <= 75 else 'normal' if v <= 100 else 'wide, stress' if v <= 150 else 'crisis'})"}


def score_credit_growth_yoy(val) -> dict:
    """Bank Credit Growth YoY.  3 pts. Higher = expanding economy = good."""
    if val is None:
        return _pending("Bank credit growth YoY", 3)
    v, err = _validate_numeric(val, "credit_growth_yoy")
    if err:
        return _error(3, f"credit_growth_yoy {err}")
    if v > 15:    score = 3
    elif v > 10:  score = 2
    elif v > 5:   score = 1
    else:         score = 0
    return {"value": round(v, 2), "score": score, "max": 3, "status": "OK",
            "note": f"Bank credit YoY {v:+.1f}% "
                    f"({'strong' if v > 15 else 'normal' if v > 10 else 'slowing' if v > 5 else 'recession-signal'})"}


# ---------- C3: Trend & Breadth manual ----------

def score_pct_above_200dma(val) -> dict:
    """% Nifty 500 above 200 DMA.  6 pts. High = broad strength = good."""
    if val is None:
        return _pending("% Nifty 500 above 200 DMA", 6)
    v, err = _validate_numeric(val, "pct_above_200dma")
    if err:
        return _error(6, f"pct_above_200dma {err}")
    if v > 70:     score = 6
    elif v > 55:   score = 4
    elif v > 40:   score = 3
    elif v > 25:   score = 1
    else:          score = 0
    return {"value": round(v, 1), "score": score, "max": 6, "status": "OK",
            "note": f"{v:.1f}% of Nifty 500 above 200DMA "
                    f"({'broad strength' if v > 70 else 'mixed' if v > 40 else 'narrow/weak'})"}


# ---------- C5: Flows manuals ----------

def score_fii_latest_month(val) -> dict:
    """
    FII latest-month net flow.  5 pts.  v2.1: single month total (e.g. -60850 for April 2026).
    Bands calibrated to monthly FII data (May 2025 +27,856 best in 26mo, March 2026 -117,774 record outflow).
    """
    if val is None:
        return _pending("FII latest month net flow", 5)
    v, err = _validate_numeric(val, "fii_latest_month")
    if err:
        return _error(5, f"fii_latest_month {err}")
    if v > 25000:     score = 5  # strong inflow month
    elif v > 10000:   score = 4
    elif v > 0:       score = 3
    elif v > -20000:  score = 1
    else:             score = 0  # heavy outflow month
    return {"value": round(v, 0), "score": score, "max": 5, "status": "OK",
            "note": f"FII latest month {v:+,.0f} Cr "
                    f"({'strong inflow' if v > 25000 else 'inflow' if v > 0 else 'outflow' if v > -20000 else 'heavy outflow'})"}


def score_dii_latest_month(val) -> dict:
    """
    DII latest-month net flow.  4 pts.  v2.1: single month total (e.g. 45000).
    Bands calibrated to recent SIP-driven monthly DII (~30-50K Cr is normal).
    """
    if val is None:
        return _pending("DII latest month net flow", 4)
    v, err = _validate_numeric(val, "dii_latest_month")
    if err:
        return _error(4, f"dii_latest_month {err}")
    if v > 40000:     score = 4  # very strong domestic bid
    elif v > 20000:   score = 3  # normal SIP-driven
    elif v > 0:       score = 2
    else:             score = 0  # capitulation
    return {"value": round(v, 0), "score": score, "max": 4, "status": "OK",
            "note": f"DII latest month {v:+,.0f} Cr "
                    f"({'very strong' if v > 40000 else 'normal' if v > 20000 else 'weak' if v > 0 else 'capitulation'})"}


def score_sip_yoy(val) -> dict:
    """SIP YoY growth.  3 pts. Higher = retail confidence = good."""
    if val is None:
        return _pending("SIP YoY %", 3)
    v, err = _validate_numeric(val, "sip_yoy")
    if err:
        return _error(3, f"sip_yoy {err}")
    if v > 20:    score = 3
    elif v > 10:  score = 2
    elif v > 0:   score = 1
    else:         score = 0
    return {"value": round(v, 1), "score": score, "max": 3, "status": "OK",
            "note": f"SIP YoY {v:+.1f}% "
                    f"({'strong' if v > 20 else 'healthy' if v > 10 else 'slowing' if v > 0 else 'capitulation'})"}


# ---------- C6: Macro India manuals ----------

def score_rbi_stance(val) -> dict:
    """RBI Monetary Policy Stance. 3 pts. Categorical."""
    if val is None:
        return _pending("RBI stance", 3)
    s = str(val).strip()
    if s == "Accommodative":   score = 3
    elif s == "Neutral":       score = 2
    elif s == "Tightening":    score = 0
    else:
        return _error(3, f"rbi_stance unknown value: {s!r}")
    return {"value": s, "score": score, "max": 3, "status": "OK",
            "note": f"RBI stance: {s}"}


def score_cpi_yoy_with_direction(val, manual_df) -> dict:
    """
    CPI YoY scoring with AUTO-DERIVED direction. 3 pts.  v2.1: takes raw latest CPI %.
    Reads last 3 saves of cpi_yoy_latest from manual_inputs.csv to compute 3M trend.
    Threshold: ±0.3pp over the 3-reading span = direction change.
    Falls back to 'Stable' (2 pts) if <3 history readings.
    """
    if val is None:
        return _pending("CPI YoY latest (auto-direction)", 3)
    v, err = _validate_numeric(val, "cpi_yoy_latest")
    if err:
        return _error(3, f"cpi_yoy_latest {err}")

    history = get_field_history(manual_df, "cpi_yoy_latest", n=3)
    if len(history) < 3:
        # Not enough history yet — default to Stable, note the limitation
        return {"value": round(v, 2), "score": 2, "max": 3, "status": "OK",
                "note": f"CPI {v:.2f}% — insufficient history ({len(history)}/3 readings), "
                        f"defaulting to Stable. Direction auto-derives after 3 monthly saves."}

    oldest, _, latest = history[0], history[1], history[-1]
    delta = latest - oldest
    if delta > 0.3:
        direction = "Rising"
        score = 0
    elif delta < -0.3:
        direction = "Falling"
        score = 3
    else:
        direction = "Stable"
        score = 2
    return {"value": round(v, 2), "score": score, "max": 3, "status": "OK",
            "note": f"CPI 3M: {history[0]:.2f} \u2192 {history[1]:.2f} \u2192 {history[-1]:.2f} "
                    f"= {direction} (\u0394{delta:+.2f}pp)"}


def score_pmi_mfg(val) -> dict:
    """Manufacturing PMI. 3 pts. >50 = expansion."""
    if val is None:
        return _pending("Manufacturing PMI", 3)
    v, err = _validate_numeric(val, "pmi_mfg")
    if err:
        return _error(3, f"pmi_mfg {err}")
    if v > 55:     score = 3
    elif v > 52:   score = 2
    elif v > 50:   score = 1
    else:          score = 0
    return {"value": round(v, 1), "score": score, "max": 3, "status": "OK",
            "note": f"PMI {v:.1f} "
                    f"({'strong expansion' if v > 55 else 'expansion' if v > 50 else 'contraction'})"}


def score_gst_yoy(val) -> dict:
    """GST Collections YoY. 3 pts. Higher = robust economy."""
    if val is None:
        return _pending("GST YoY %", 3)
    v, err = _validate_numeric(val, "gst_yoy")
    if err:
        return _error(3, f"gst_yoy {err}")
    if v > 12:    score = 3
    elif v > 8:   score = 2
    elif v > 3:   score = 1
    else:         score = 0
    return {"value": round(v, 1), "score": score, "max": 3, "status": "OK",
            "note": f"GST YoY {v:+.1f}% "
                    f"({'robust' if v > 12 else 'normal' if v > 8 else 'slowing' if v > 3 else 'recession-signal'})"}


# ============================================================
# REGIME DETERMINATION
# ============================================================

def determine_regime(score_pct: float):
    """Map score % of max to regime + equity allocation %."""
    for min_pct, regime, equity_pct in ALLOCATION_BANDS:
        if score_pct >= min_pct:
            return regime, equity_pct
    return "EXIT_ALL", 10


def apply_safety_overrides(regime: str, equity_pct: int, nifty_pe) -> tuple:
    """
    Apply safety overrides per strategy doc:
      - PE Bubble: Nifty PE > 26 caps equity at 70%

    Returns (regime, equity_pct, override_applied_or_none).
    """
    if nifty_pe is not None:
        try:
            pe_f = float(nifty_pe)
            if pe_f > PE_BUBBLE_THRESHOLD and equity_pct > PE_BUBBLE_EQUITY_CAP:
                return regime, PE_BUBBLE_EQUITY_CAP, (
                    f"PE Bubble override: Nifty PE {pe_f:.2f} > {PE_BUBBLE_THRESHOLD}, "
                    f"equity capped at {PE_BUBBLE_EQUITY_CAP}%"
                )
        except (TypeError, ValueError):
            pass
    return regime, equity_pct, None


# ============================================================
# MAIN COMPUTATION
# ============================================================

def compute_engine_a():
    print(f"[{now_ist()}] Starting Engine A v2.1 compute layer (v2 with manual inputs)...")
    print("=" * 60)

    # ---- Load auto data from CSVs ----
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

    # ---- Load manual inputs (v2.1: latest dict + full DataFrame for history) ----
    manual = load_manual_inputs()
    manual_df = load_manual_inputs_df()
    nifty_pe          = manual.get("nifty_pe_ttm")
    nifty_pe_pctile   = manual.get("nifty_pe_pctile")
    mcap_gdp_ratio    = manual.get("mcap_gdp_ratio")          # v2.1: raw %, not pctile
    aaa_spread_bps    = manual.get("aaa_spread_bps")          # v2.1: raw bps, not pctile
    credit_growth     = manual.get("credit_growth_yoy")
    pct_above_200dma  = manual.get("pct_above_200dma")
    fii_latest_month  = manual.get("fii_latest_month")        # v2.1: single month
    dii_latest_month  = manual.get("dii_latest_month")        # v2.1: single month
    sip_yoy           = manual.get("sip_yoy")
    rbi_stance        = manual.get("rbi_stance")
    cpi_yoy_latest    = manual.get("cpi_yoy_latest")          # v2.1: raw %, auto-direction
    pmi_mfg           = manual.get("pmi_mfg")
    gst_yoy           = manual.get("gst_yoy")

    print(f"Auto data:")
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
    print(f"\nManual inputs loaded: {len(manual)}/13")
    if manual:
        for k, v in manual.items():
            print(f"  {k}: {v}")
    print("-" * 60)

    # ---- Score each sub-input ----
    components = {
        "C1_valuation": {
            "weight": 22, "name": "Valuation",
            "sub_inputs": {
                "yield_gap":        score_yield_gap(nifty_pe, gsec_10y),
                "nifty_pe_pctile":  score_nifty_pe_pctile(nifty_pe_pctile),
                "mcap_gdp_ratio":   score_mcap_gdp_ratio(mcap_gdp_ratio),
            }
        },
        "C2_credit_rates": {
            "weight": 14, "name": "Credit & Rates",
            "sub_inputs": {
                "aaa_spread_bps":     score_aaa_spread_bps(aaa_spread_bps),
                "yield_curve_10y_2y": score_yield_curve(gsec_10y, gsec_2y),
                "credit_growth_yoy":  score_credit_growth_yoy(credit_growth),
            }
        },
        "C3_trend_breadth": {
            "weight": 13, "name": "Trend & Breadth",
            "sub_inputs": {
                "nifty_vs_200dma":  score_nifty_vs_200dma(nifty_50),
                "pct_above_200dma": score_pct_above_200dma(pct_above_200dma),
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
                "fii_latest_month":  score_fii_latest_month(fii_latest_month),
                "dii_latest_month":  score_dii_latest_month(dii_latest_month),
                "sip_yoy":           score_sip_yoy(sip_yoy),
            }
        },
        "C6_macro_india": {
            "weight": 12, "name": "Macro India",
            "sub_inputs": {
                "rbi_stance":   score_rbi_stance(rbi_stance),
                "cpi_yoy":      score_cpi_yoy_with_direction(cpi_yoy_latest, manual_df),
                "pmi_mfg":      score_pmi_mfg(pmi_mfg),
                "gst_yoy":      score_gst_yoy(gst_yoy),
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

    # ---- Apply safety overrides (v2 NEW) ----
    regime, equity_pct, override_note = apply_safety_overrides(regime, equity_pct, nifty_pe)

    # ---- Print breakdown ----
    print(f"\n{'Component':<28} {'Score':<10} {'Max Avail':<12} {'% of Max':<10}")
    print("-" * 60)
    for comp_key, comp in components.items():
        print(f"{comp['name']:<28} {comp['score']:<10} {comp['max_available']:<12} "
              f"{comp['pct_of_max_available']:.1f}%")
    print("-" * 60)
    print(f"\nTOTAL SCORE:        {total_score} / {total_max_available} "
          f"(out of theoretical max {total_max_possible})")
    print(f"SCORE % OF MAX:     {score_pct:.1f}%")
    print(f"REGIME:             {regime}")
    print(f"EQUITY ALLOCATION:  {equity_pct}%")
    if override_note:
        print(f"SAFETY OVERRIDE:    {override_note}")
    print(f"\nPENDING MANUAL:     {len(pending_manual)} sub-inputs")
    if pending_manual:
        for item in pending_manual:
            print(f"     - {item}")
    if stale_inputs:
        print(f"\nSTALE/ERROR:        {len(stale_inputs)} sub-inputs")
        for item in stale_inputs:
            print(f"     - {item}")
    print("=" * 60)

    # Map regime to guidance text for dashboard display
    GUIDANCE_TEXT = {
        "FULL_DEPLOY": "Maximum deployment",
        "AGGRESSIVE":  "Lean in aggressively",
        "ACTIVE":      "Normal deployment",
        "CAUTIOUS":    "Selective adds only",
        "FREEZE":      "No new equity buys",
        "EXIT_ALL":    "Defensive only",
    }
    guidance = GUIDANCE_TEXT.get(regime, "—")

    # ---- Build output JSON ----
    output = {
        "schema_version": "v2.1",
        "computed_at_ist": now_ist(),
        "last_compute": now_ist(),                 # alias for dashboard
        "score": total_score,
        "max_available": total_max_available,      # alias for dashboard
        "max_available_today": total_max_available,
        "max_theoretical": total_max_possible,
        "score_pct_of_max_available": round(score_pct, 2),
        "regime": regime,
        "equity_allocation": equity_pct,           # alias for dashboard
        "regime_equity_pct": equity_pct,
        "guidance": guidance,                      # NEW: readable guidance
        "safety_override": override_note,
        "pending_count": len(pending_manual),      # alias for dashboard
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
        },
        "manual_inputs_loaded": list(manual.keys()),
    }

    # ---- Write JSON ----
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_JSON, "w") as f:
        json.dump(output, f, indent=2, default=str)
    print(f"\nWrote {OUTPUT_JSON}")

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
    print(f"Appended to {OUTPUT_HISTORY_CSV}")

    print(f"\n[{now_ist()}] Compute layer done.\n")
    return output


if __name__ == "__main__":
    compute_engine_a()
