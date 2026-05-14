"""
============================================================
Engine A Dashboard v2.1
Core Fetcher: yfinance (Global Data)
============================================================
Fetches 5 global tickers required for Engine A scoring:
  - US 10Y Treasury yield (^TNX)
  - DXY US Dollar Index (DX-Y.NYB)
  - US VIX (^VIX)
  - USD/INR exchange rate (INR=X)
  - Brent Crude futures (BZ=F)

Output: data/core/yfinance_global.csv (appends one row per ticker per run)
Run:    python fetchers/core/yfinance/fetch_yfinance_core.py
Cron:   Every 15 min during NSE hours + once at 4 AM IST after US close

Design principles:
  - Sanity checks: every value bounded by reasonable range
  - Graceful degradation: one ticker failure doesn't kill others
  - IST timestamps: matches user timezone
  - Append-only: builds historical dataset over time
  - Status flagging: OK / STALE / ERROR per row

Last updated: May 14, 2026
============================================================
"""

import os
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd
import pytz
import yfinance as yf


# ============================================================
# CONFIGURATION
# ============================================================

IST = pytz.timezone("Asia/Kolkata")

# Output path (relative to repo root)
OUTPUT_DIR = Path("data/core")
OUTPUT_FILE = OUTPUT_DIR / "yfinance_global.csv"

# Tickers to fetch, with sanity ranges
# Format: ticker -> (display_name, min_sane_value, max_sane_value, scale_divisor)
# scale_divisor handles ^TNX which yfinance returns as 44.6 for 4.46%
TICKERS = {
    "^TNX":     ("US 10Y Yield",     2.0,   8.0,   10),
    "DX-Y.NYB": ("DXY",              85.0,  120.0, 1),
    "^VIX":     ("US VIX",           8.0,   80.0,  1),
    "INR=X":    ("USD/INR",          75.0,  100.0, 1),
    "BZ=F":     ("Brent Crude",      30.0,  180.0, 1),
}


# ============================================================
# HELPERS
# ============================================================

def now_ist() -> str:
    """Current timestamp in IST as 'YYYY-MM-DD HH:MM:SS' string."""
    return datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S")


def fetch_one_ticker(ticker: str, name: str, min_val: float, max_val: float, scale: int) -> dict:
    """
    Fetch a single ticker from yfinance.
    Returns a dict ready to be a CSV row.

    Status logic:
      OK    - fetched successfully, value in sane range
      STALE - fetched but value looks wrong (out of sane range)
      ERROR - fetch failed (network, ticker delisted, etc.)
    """
    fetched_at = now_ist()

    try:
        # Use 5d to be safe — handles weekends, holidays, half-days
        data = yf.Ticker(ticker).history(period="5d", auto_adjust=False)

        if data.empty:
            return {
                "timestamp": fetched_at,
                "ticker": ticker,
                "name": name,
                "value": None,
                "change_pct": None,
                "fetched_at": fetched_at,
                "status": "ERROR",
                "note": "Empty dataframe from yfinance",
            }

        # Latest close
        latest_close = float(data["Close"].iloc[-1]) / scale

        # Previous close for change %
        if len(data) >= 2:
            prev_close = float(data["Close"].iloc[-2]) / scale
            change_pct = ((latest_close - prev_close) / prev_close) * 100
        else:
            change_pct = None

        # Market timestamp of the latest close (when it was valid for)
        market_ts = data.index[-1]
        if market_ts.tzinfo is None:
            market_ts = pytz.UTC.localize(market_ts)
        market_ts_ist = market_ts.astimezone(IST).strftime("%Y-%m-%d %H:%M:%S")

        # Sanity check
        if not (min_val <= latest_close <= max_val):
            status = "STALE"
            note = f"Value {latest_close:.4f} outside sane range [{min_val}, {max_val}]"
        else:
            status = "OK"
            note = ""

        return {
            "timestamp": market_ts_ist,
            "ticker": ticker,
            "name": name,
            "value": round(latest_close, 4),
            "change_pct": round(change_pct, 4) if change_pct is not None else None,
            "fetched_at": fetched_at,
            "status": status,
            "note": note,
        }

    except Exception as e:
        return {
            "timestamp": fetched_at,
            "ticker": ticker,
            "name": name,
            "value": None,
            "change_pct": None,
            "fetched_at": fetched_at,
            "status": "ERROR",
            "note": f"{type(e).__name__}: {str(e)[:100]}",
        }


def append_to_csv(rows: list, output_file: Path):
    """Append new rows to CSV, creating the file with headers if it doesn't exist."""
    new_df = pd.DataFrame(rows)

    # Ensure output directory exists
    output_file.parent.mkdir(parents=True, exist_ok=True)

    # Append vs create
    if output_file.exists():
        new_df.to_csv(output_file, mode="a", header=False, index=False)
    else:
        new_df.to_csv(output_file, mode="w", header=True, index=False)


# ============================================================
# MAIN
# ============================================================

def main():
    print(f"[{now_ist()}] Starting yfinance core fetch...")
    print(f"Output: {OUTPUT_FILE}")
    print("-" * 60)

    rows = []
    ok_count, stale_count, error_count = 0, 0, 0

    for ticker, (name, min_val, max_val, scale) in TICKERS.items():
        row = fetch_one_ticker(ticker, name, min_val, max_val, scale)
        rows.append(row)

        status = row["status"]
        value = row["value"] if row["value"] is not None else "N/A"
        symbol = "OK " if status == "OK" else ("WARN" if status == "STALE" else "FAIL")

        print(f"  [{symbol}] {name:<18} {ticker:<10} = {value}  ({status})")

        if status == "OK":
            ok_count += 1
        elif status == "STALE":
            stale_count += 1
        else:
            error_count += 1

    append_to_csv(rows, OUTPUT_FILE)

    print("-" * 60)
    print(f"Summary: OK={ok_count}  STALE={stale_count}  ERROR={error_count}")
    print(f"[{now_ist()}] Done. Wrote {len(rows)} rows to {OUTPUT_FILE}")

    # Exit code: 0 if at least one fetch succeeded, 1 if all failed
    # This lets GitHub Actions know whether to flag the run as failed
    if ok_count == 0:
        print("ERROR: All fetches failed. Exiting with code 1.")
        sys.exit(1)


if __name__ == "__main__":
    main()
