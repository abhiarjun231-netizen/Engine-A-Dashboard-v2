"""
============================================================
Engine A Dashboard v2.1
Core Scraper: Indian Government Bond Yields
============================================================
Scrapes bond yields from investing.com:
  - India 10Y G-Sec yield (Engine A C1 Valuation + C2 Credit)
  - India 2Y G-Sec yield  (Engine A C2 Credit)

Output: data/core/bond_yields.csv (appends one row per yield per run)
Run:    python fetchers/core/scrapers/fetch_bonds.py
Cron:   Real-time when bond market is open; falls back gracefully otherwise

Design principles:
  - Sanity checks: every value bounded by reasonable range
  - Graceful degradation: one yield failure doesn't kill the other
  - User-Agent spoofing: avoids basic rate-limit blocks
  - IST timestamps: matches user timezone
  - Append-only: builds historical dataset over time
  - Status flagging: OK / STALE / ERROR per row

NOTE on robustness:
  investing.com's HTML structure may change. This scraper looks for the
  yield value via multiple fallback selectors. If they ALL fail, it
  returns ERROR with a clear message — never silently corrupts data.

Last updated: May 14, 2026
============================================================
"""

import re
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd
import pytz
import requests
from bs4 import BeautifulSoup


# ============================================================
# CONFIGURATION
# ============================================================

IST = pytz.timezone("Asia/Kolkata")

OUTPUT_DIR = Path("data/core")
OUTPUT_FILE = OUTPUT_DIR / "bond_yields.csv"

# Realistic browser headers — investing.com rejects bare scraper requests
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Linux; Android 13; SM-A536B) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Mobile Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}

# Bonds to fetch
# Format: (display_name, url, min_sane_yield_pct, max_sane_yield_pct)
BONDS = [
    (
        "India 10Y G-Sec",
        "https://www.investing.com/rates-bonds/india-10-year-bond-yield",
        4.0,
        10.0,
    ),
    (
        "India 2Y G-Sec",
        "https://www.investing.com/rates-bonds/india-2-year-bond-yield",
        3.0,
        10.0,
    ),
]


# ============================================================
# HELPERS
# ============================================================

def now_ist() -> str:
    """Current timestamp in IST as 'YYYY-MM-DD HH:MM:SS' string."""
    return datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S")


def extract_yield(html: str) -> float | None:
    """
    Extract the bond yield % from investing.com HTML.
    Tries multiple selector strategies — robust against minor HTML changes.

    Returns yield as float (e.g. 7.045) or None if all strategies fail.
    """
    soup = BeautifulSoup(html, "lxml")

    # Strategy 1: data-test="instrument-price-last" (current investing.com selector)
    el = soup.find(attrs={"data-test": "instrument-price-last"})
    if el and el.text.strip():
        try:
            return float(el.text.strip().replace(",", ""))
        except ValueError:
            pass

    # Strategy 2: id="last_last" (legacy selector, may still work)
    el = soup.find(id="last_last")
    if el and el.text.strip():
        try:
            return float(el.text.strip().replace(",", ""))
        except ValueError:
            pass

    # Strategy 3: parse from <title> tag (often contains current price)
    if soup.title and soup.title.string:
        m = re.search(r"(\d+\.\d{2,4})", soup.title.string)
        if m:
            try:
                return float(m.group(1))
            except ValueError:
                pass

    # Strategy 4: regex sweep through the entire page for "X.XXX%"-style numbers
    # appearing near "Yield" keyword (last-ditch effort)
    text = soup.get_text(" ", strip=True)
    m = re.search(r"Yield[^\d]{0,20}(\d+\.\d{2,4})", text)
    if m:
        try:
            return float(m.group(1))
        except ValueError:
            pass

    return None


def fetch_one_bond(name: str, url: str, min_val: float, max_val: float) -> dict:
    """
    Scrape a single bond yield from investing.com.
    Returns a dict ready to be a CSV row.

    Status logic:
      OK    - scraped successfully, value in sane range
      STALE - scraped but value looks wrong
      ERROR - scrape failed (network, parse error, etc.)
    """
    fetched_at = now_ist()

    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()

        yield_value = extract_yield(resp.text)

        if yield_value is None:
            return {
                "timestamp": fetched_at,
                "ticker": url.split("/")[-1],
                "name": name,
                "value": None,
                "change_pct": None,
                "fetched_at": fetched_at,
                "status": "ERROR",
                "note": "All extraction strategies failed (page structure may have changed)",
            }

        # Sanity check
        if not (min_val <= yield_value <= max_val):
            status = "STALE"
            note = f"Value {yield_value:.4f} outside sane range [{min_val}, {max_val}]"
        else:
            status = "OK"
            note = ""

        return {
            "timestamp": fetched_at,
            "ticker": url.split("/")[-1],
            "name": name,
            "value": round(yield_value, 4),
            "change_pct": None,  # investing.com page change% is fragile; skip for now
            "fetched_at": fetched_at,
            "status": status,
            "note": note,
        }

    except requests.exceptions.HTTPError as e:
        return {
            "timestamp": fetched_at,
            "ticker": url.split("/")[-1],
            "name": name,
            "value": None,
            "change_pct": None,
            "fetched_at": fetched_at,
            "status": "ERROR",
            "note": f"HTTP {e.response.status_code}",
        }

    except Exception as e:
        return {
            "timestamp": fetched_at,
            "ticker": url.split("/")[-1],
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


# ============================================================
# MAIN
# ============================================================

def main():
    print(f"[{now_ist()}] Starting bond yields scraper...")
    print(f"Output: {OUTPUT_FILE}")
    print("-" * 60)

    rows = []
    ok_count, stale_count, error_count = 0, 0, 0

    for name, url, min_val, max_val in BONDS:
        row = fetch_one_bond(name, url, min_val, max_val)
        rows.append(row)

        status = row["status"]
        value = row["value"] if row["value"] is not None else "N/A"
        symbol = "OK " if status == "OK" else ("WARN" if status == "STALE" else "FAIL")

        print(f"  [{symbol}] {name:<20} = {value}  ({status})")
        if row.get("note"):
            print(f"        note: {row['note']}")

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

    if ok_count == 0:
        print("ERROR: All scrapes failed. Exiting with code 1.")
        sys.exit(1)


if __name__ == "__main__":
    main()
