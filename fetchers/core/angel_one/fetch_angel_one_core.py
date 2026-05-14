"""
============================================================
Engine A Dashboard v2.1
Core Fetcher: Angel One SmartAPI (Indian Real-Time Data)
============================================================
Fetches 3 Indian tickers required for Engine A scoring:
  - Nifty 50 (index, token 99926000)
  - India VIX (index, token 99926009)
  - GOLDBEES (equity ETF, NSE)

Output: data/core/angel_one_indian.csv (appends one row per ticker per run)
Run:    python fetchers/core/angel_one/fetch_angel_one_core.py

Authentication:
  Reads 4 credentials from environment variables:
    ANGEL_API_KEY
    ANGEL_CLIENT_CODE
    ANGEL_PIN
    ANGEL_TOTP_SECRET
  Each run authenticates fresh via TOTP, then logs out.

Design principles:
  - Sanity checks: every value bounded by reasonable range
  - Graceful degradation: one ticker failure doesn't kill others
  - Auth failure handling: clear error if secrets missing or wrong
  - IST timestamps: matches user timezone
  - Append-only: builds historical dataset over time
  - Status flagging: OK / STALE / ERROR per row

Last updated: May 14, 2026
============================================================
"""

import os
import sys
import time
from datetime import datetime
from pathlib import Path

import pandas as pd
import pyotp
import pytz
from SmartApi import SmartConnect


# ============================================================
# CONFIGURATION
# ============================================================

IST = pytz.timezone("Asia/Kolkata")

# Output path (relative to repo root)
OUTPUT_DIR = Path("data/core")
OUTPUT_FILE = OUTPUT_DIR / "angel_one_indian.csv"

# Required environment variables (GitHub Actions injects from Secrets)
REQUIRED_ENV_VARS = [
    "ANGEL_API_KEY",
    "ANGEL_CLIENT_CODE",
    "ANGEL_PIN",
    "ANGEL_TOTP_SECRET",
]

# Tickers to fetch via Angel One LTP API
# Format: (display_name, exchange, tradingsymbol, symboltoken, min_sane, max_sane)
TICKERS = [
    ("Nifty 50",   "NSE", "NIFTY 50",      "99926000", 15000.0, 35000.0),
    ("India VIX",  "NSE", "INDIA VIX",     "99926009",     5.0,    80.0),
    ("GOLDBEES",   "NSE", "GOLDBEES-EQ",   "16086",       40.0,   200.0),
]


# ============================================================
# HELPERS
# ============================================================

def now_ist() -> str:
    """Current timestamp in IST as 'YYYY-MM-DD HH:MM:SS' string."""
    return datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S")


def get_credentials():
    """Read 4 Angel One credentials from environment. Exit hard if missing."""
    missing = [v for v in REQUIRED_ENV_VARS if not os.environ.get(v)]
    if missing:
        print(f"ERROR: Missing environment variables: {missing}")
        print("Ensure all 4 are set in GitHub Secrets:")
        for v in REQUIRED_ENV_VARS:
            print(f"  - {v}")
        sys.exit(1)

    return {
        "api_key":      os.environ["ANGEL_API_KEY"],
        "client_code":  os.environ["ANGEL_CLIENT_CODE"],
        "pin":          os.environ["ANGEL_PIN"],
        "totp_secret":  os.environ["ANGEL_TOTP_SECRET"],
    }


def authenticate(creds: dict) -> SmartConnect:
    """Login to Angel One via TOTP. Returns authenticated SmartConnect object."""
    print(f"[{now_ist()}] Authenticating with Angel One...")

    obj = SmartConnect(api_key=creds["api_key"])

    # Generate current TOTP code from secret
    totp = pyotp.TOTP(creds["totp_secret"]).now()

    # Authenticate
    session = obj.generateSession(
        clientCode=creds["client_code"],
        password=creds["pin"],
        totp=totp,
    )

    if not session.get("status"):
        print(f"ERROR: Angel One auth failed: {session.get('message', 'unknown')}")
        sys.exit(1)

    print(f"[{now_ist()}] Auth OK. Session established.")
    return obj


def fetch_one_ticker(obj: SmartConnect, name: str, exchange: str,
                     tradingsymbol: str, symboltoken: str,
                     min_val: float, max_val: float) -> dict:
    """
    Fetch a single ticker's LTP (Last Traded Price) via Angel One.
    Returns a dict ready to be a CSV row.

    Status logic:
      OK    - fetched successfully, value in sane range
      STALE - fetched but value looks wrong (out of sane range)
      ERROR - fetch failed
    """
    fetched_at = now_ist()

    try:
        # Angel One LTP endpoint
        result = obj.ltpData(exchange, tradingsymbol, symboltoken)

        if not result.get("status"):
            return {
                "timestamp": fetched_at,
                "ticker": tradingsymbol,
                "name": name,
                "value": None,
                "change_pct": None,
                "fetched_at": fetched_at,
                "status": "ERROR",
                "note": f"API: {result.get('message', 'unknown')}",
            }

        data = result.get("data", {})
        ltp = float(data.get("ltp", 0))
        close = float(data.get("close", 0))  # previous day close

        if ltp == 0:
            return {
                "timestamp": fetched_at,
                "ticker": tradingsymbol,
                "name": name,
                "value": None,
                "change_pct": None,
                "fetched_at": fetched_at,
                "status": "ERROR",
                "note": "LTP returned zero",
            }

        # Compute change % vs previous close
        change_pct = ((ltp - close) / close * 100) if close > 0 else None

        # Sanity check
        if not (min_val <= ltp <= max_val):
            status = "STALE"
            note = f"Value {ltp:.2f} outside sane range [{min_val}, {max_val}]"
        else:
            status = "OK"
            note = ""

        return {
            "timestamp": fetched_at,  # Angel One LTP is real-time; mark with fetch time
            "ticker": tradingsymbol,
            "name": name,
            "value": round(ltp, 4),
            "change_pct": round(change_pct, 4) if change_pct is not None else None,
            "fetched_at": fetched_at,
            "status": status,
            "note": note,
        }

    except Exception as e:
        return {
            "timestamp": fetched_at,
            "ticker": tradingsymbol,
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
    output_file.parent.mkdir(parents=True, exist_ok=True)

    if output_file.exists():
        new_df.to_csv(output_file, mode="a", header=False, index=False)
    else:
        new_df.to_csv(output_file, mode="w", header=True, index=False)


def safe_logout(obj: SmartConnect, client_code: str):
    """Clean logout. Suppress errors — logout failure shouldn't fail the run."""
    try:
        obj.terminateSession(client_code)
    except Exception as e:
        print(f"WARN: Logout exception (non-fatal): {type(e).__name__}: {e}")


# ============================================================
# MAIN
# ============================================================

def main():
    print(f"[{now_ist()}] Starting Angel One core fetch...")
    print(f"Output: {OUTPUT_FILE}")
    print("-" * 60)

    creds = get_credentials()
    obj = authenticate(creds)

    rows = []
    ok_count, stale_count, error_count = 0, 0, 0

    try:
        for name, exchange, tradingsymbol, symboltoken, min_val, max_val in TICKERS:
            row = fetch_one_ticker(obj, name, exchange, tradingsymbol,
                                   symboltoken, min_val, max_val)
            rows.append(row)

            status = row["status"]
            value = row["value"] if row["value"] is not None else "N/A"
            symbol = "OK " if status == "OK" else ("WARN" if status == "STALE" else "FAIL")

            print(f"  [{symbol}] {name:<18} {tradingsymbol:<14} = {value}  ({status})")

            if status == "OK":
                ok_count += 1
            elif status == "STALE":
                stale_count += 1
            else:
                error_count += 1

            # Be polite to API: 1 request/sec is Angel One rate limit
            time.sleep(1.1)
    finally:
        safe_logout(obj, creds["client_code"])

    append_to_csv(rows, OUTPUT_FILE)

    print("-" * 60)
    print(f"Summary: OK={ok_count}  STALE={stale_count}  ERROR={error_count}")
    print(f"[{now_ist()}] Done. Wrote {len(rows)} rows to {OUTPUT_FILE}")

    if ok_count == 0:
        print("ERROR: All fetches failed. Exiting with code 1.")
        sys.exit(1)


if __name__ == "__main__":
    main()
