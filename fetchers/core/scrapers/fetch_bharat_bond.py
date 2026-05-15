"""
============================================================
Engine A Dashboard v2.1
Core Scraper: Bharat Bond ETF YTM (AAA PSU Credit Proxy)
============================================================
Scrapes Bharat Bond ETF YTMs from Edelweiss MF:
  - April 2030 series (~4Y duration)
  - April 2031 series (~5Y duration)
  - April 2032 series (~6Y duration)
  - April 2033 series (~7Y duration)

These YTMs proxy AAA PSU corporate bond yields, used to compute
AAA-GSec credit spread for Engine A C2 Credit & Rates.

Source: https://www.edelweissmf.com/
Output: data/core/bharat_bond_ytm.csv (appends one row per series per run)
Run:    python fetchers/core/scrapers/fetch_bharat_bond.py
Cron:   Daily EOD via existing cron workflow

Design principles:
  - Sanity checks: YTM must be 5-12%
  - Multiple extraction strategies: robust against HTML changes
  - Graceful degradation: failure of one series doesn't kill others
  - User-Agent spoofing: avoids basic bot blocks
  - Append-only: builds historical YTM dataset

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
OUTPUT_FILE = OUTPUT_DIR / "bharat_bond_ytm.csv"

# Edelweiss Bharat Bond ETF series pages
# Note: Some series pages may have unique URLs; we'll search via a sweep approach
BHARAT_BOND_SERIES_PAGE = "https://www.edelweissmf.com/passive-debt-funds"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Linux; Android 13; SM-A536B) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Mobile Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}

# Series we want to extract
# Each entry: (display_name, key_to_find_on_page)
SERIES = [
    ("Bharat Bond April 2030", "2030"),
    ("Bharat Bond April 2031", "2031"),
    ("Bharat Bond April 2032", "2032"),
    ("Bharat Bond April 2033", "2033"),
]

# Sanity range for YTM percentages
YTM_MIN = 5.0
YTM_MAX = 12.0


# ============================================================
# HELPERS
# ============================================================

def now_ist() -> str:
    return datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S")


def extract_all_ytms(html: str) -> dict:
    """
    Scan the Edelweiss page for YTMs associated with each Bharat Bond series.
    Returns a dict {series_year: ytm_value} for any successful extractions.

    Strategy: search for patterns like '2030 ... 7.46% YTM' or 'April 2030 7.46 YTM'.
    """
    soup = BeautifulSoup(html, "lxml")
    page_text = soup.get_text(" ", strip=True)

    results = {}

    # Strategy 1: Look for "April YYYY" followed by "X.XX% YTM" within ~80 chars
    for year in ["2030", "2031", "2032", "2033"]:
        # Try pattern: "April 2030" then "X.XX" then "YTM" within 100 chars
        pattern = rf"(?:April\s+|BHARAT[^\d]*?){year}.{{1,150}}?(\d{{1,2}}\.\d{{1,3}})\s*%?\s*YTM"
        m = re.search(pattern, page_text, re.IGNORECASE | re.DOTALL)
        if m:
            try:
                val = float(m.group(1))
                if YTM_MIN <= val <= YTM_MAX:
                    results[year] = val
                    continue
            except ValueError:
                pass

        # Strategy 2: Look for "YTM" near the year (reversed order)
        pattern_alt = rf"(\d{{1,2}}\.\d{{1,3}})\s*%?\s*YTM.{{1,150}}?{year}"
        m = re.search(pattern_alt, page_text, re.IGNORECASE | re.DOTALL)
        if m:
            try:
                val = float(m.group(1))
                if YTM_MIN <= val <= YTM_MAX:
                    results[year] = val
            except ValueError:
                pass

    return results


def fetch_bharat_bond_ytms() -> list:
    """
    Scrape Bharat Bond ETF YTMs from Edelweiss.
    Returns a list of CSV row dicts (one per series).
    """
    fetched_at = now_ist()
    rows = []

    try:
        resp = requests.get(BHARAT_BOND_SERIES_PAGE, headers=HEADERS, timeout=20)
        resp.raise_for_status()

        ytms = extract_all_ytms(resp.text)

        if not ytms:
            # Total failure — all series get ERROR
            for name, year in SERIES:
                rows.append({
                    "timestamp": fetched_at,
                    "ticker": f"BHARAT_BOND_{year}",
                    "name": name,
                    "value": None,
                    "fetched_at": fetched_at,
                    "status": "ERROR",
                    "note": "No YTM extracted from Edelweiss page",
                })
            return rows

        # Per-series rows
        for name, year in SERIES:
            if year in ytms:
                rows.append({
                    "timestamp": fetched_at,
                    "ticker": f"BHARAT_BOND_{year}",
                    "name": name,
                    "value": round(ytms[year], 4),
                    "fetched_at": fetched_at,
                    "status": "OK",
                    "note": "",
                })
            else:
                rows.append({
                    "timestamp": fetched_at,
                    "ticker": f"BHARAT_BOND_{year}",
                    "name": name,
                    "value": None,
                    "fetched_at": fetched_at,
                    "status": "ERROR",
                    "note": f"YTM for {year} not found on page",
                })

        return rows

    except requests.exceptions.HTTPError as e:
        for name, year in SERIES:
            rows.append({
                "timestamp": fetched_at,
                "ticker": f"BHARAT_BOND_{year}",
                "name": name,
                "value": None,
                "fetched_at": fetched_at,
                "status": "ERROR",
                "note": f"HTTP {e.response.status_code}",
            })
        return rows

    except Exception as e:
        for name, year in SERIES:
            rows.append({
                "timestamp": fetched_at,
                "ticker": f"BHARAT_BOND_{year}",
                "name": name,
                "value": None,
                "fetched_at": fetched_at,
                "status": "ERROR",
                "note": f"{type(e).__name__}: {str(e)[:100]}",
            })
        return rows


def append_to_csv(rows: list, output_file: Path):
    """Append rows to CSV, creating with headers if it doesn't exist."""
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
    print(f"[{now_ist()}] Starting Bharat Bond YTM scraper...")
    print(f"Output: {OUTPUT_FILE}")
    print("-" * 60)

    rows = fetch_bharat_bond_ytms()

    ok_count, stale_count, error_count = 0, 0, 0
    for row in rows:
        status = row["status"]
        value = row["value"] if row["value"] is not None else "N/A"
        symbol = "OK " if status == "OK" else ("WARN" if status == "STALE" else "FAIL")

        value_str = f"{value:.4f}%" if isinstance(value, (int, float)) else value
        print(f"  [{symbol}] {row['name']:<28} = {value_str}  ({status})")
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
        print("ERROR: All extractions failed. Exiting with code 1.")
        sys.exit(1)


if __name__ == "__main__":
    main()
