"""
============================================================
Engine A Dashboard v2.1
Core Scraper: BSE All India Market Capitalisation
============================================================
Scrapes total India listed market cap from BSE:
  - All India Market Cap (₹ Crore)
  - Used for Engine A C1 Valuation (MCap/GDP ratio)

Source URL: https://www.bseindia.com/markets/equity/EQReports/allindiamktcap.aspx
Output:     data/core/bse_mcap.csv (appends one row per run)
Run:        python fetchers/core/scrapers/fetch_bse_mcap.py
Cron:       Daily EOD via existing cron workflow

Design principles:
  - Sanity checks: MCap must be in ₹ 100 lakh Cr to ₹ 1000 lakh Cr range
  - Graceful degradation: scraper failure doesn't break workflow
  - User-Agent spoofing: avoids basic bot blocks
  - IST timestamps: matches user timezone
  - Append-only: builds historical dataset
  - Status flagging: OK / STALE / ERROR

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
OUTPUT_FILE = OUTPUT_DIR / "bse_mcap.csv"

URL = "https://www.bseindia.com/markets/equity/EQReports/allindiamktcap.aspx"

# Realistic browser headers — BSE rejects bare scraper requests
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Linux; Android 13; SM-A536B) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Mobile Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Referer": "https://www.bseindia.com/",
}

# Sanity range for total India MCap (in Lakh Crore = 1 Lakh Cr = 100 K Cr)
# India MCap was ~250 Lakh Cr in 2020, ~450+ Lakh Cr in 2026
# Realistic range: 100 to 1000 Lakh Cr = 1,00,00,000 to 10,00,00,000 ₹ Cr
MCAP_MIN = 100_00_000     # 100 Lakh Cr
MCAP_MAX = 10_00_00_000   # 1000 Lakh Cr


# ============================================================
# HELPERS
# ============================================================

def now_ist() -> str:
    """Current timestamp in IST as 'YYYY-MM-DD HH:MM:SS' string."""
    return datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S")


def parse_indian_number(text: str) -> float | None:
    """
    Parse Indian-format numbers like '4,63,01,247.23' to float.
    Handles commas (Indian or Western), decimals, and whitespace.
    """
    if not text:
        return None
    try:
        cleaned = re.sub(r"[^\d.]", "", text.strip())
        return float(cleaned) if cleaned else None
    except (ValueError, AttributeError):
        return None


def extract_mcap(html: str) -> tuple[float | None, str | None]:
    """
    Extract All India Market Cap from BSE HTML.
    Tries multiple strategies — robust against minor HTML changes.

    Returns (mcap_value, as_on_date) or (None, None) if all strategies fail.
    """
    soup = BeautifulSoup(html, "lxml")

    as_on_date = None

    # Try to find "As on DD MMM YYYY" date
    date_match = re.search(r"As on\s+(\d{1,2}\s+\w+\s+\d{4})", soup.get_text())
    if date_match:
        as_on_date = date_match.group(1).strip()

    # Strategy 1: Look for the specific table with 3 columns
    # (Total Companies | All India Market Cap | Top 10 MCap)
    for table in soup.find_all("table"):
        text = table.get_text(" ", strip=True)
        if "All India" in text and "Market" in text and "Capital" in text.replace("isation", "ization"):
            # Find all cells with numeric content
            cells = table.find_all(["td", "th"])
            for i, cell in enumerate(cells):
                cell_text = cell.get_text(strip=True)
                # The MCap value is a large number with commas
                if re.match(r"^[\d,]+(\.\d+)?$", cell_text) and len(cell_text) >= 8:
                    value = parse_indian_number(cell_text)
                    if value and MCAP_MIN <= value <= MCAP_MAX:
                        return value, as_on_date

    # Strategy 2: Regex scan for the largest Indian-format number on the page
    # India MCap is the biggest number — by far
    numbers = re.findall(r"\b\d{1,2}(?:,\d{2,3})+(?:\.\d+)?\b", soup.get_text())
    candidates = []
    for num_str in numbers:
        value = parse_indian_number(num_str)
        if value and MCAP_MIN <= value <= MCAP_MAX:
            candidates.append(value)
    if candidates:
        # Return the largest candidate (MCap is biggest number on page)
        return max(candidates), as_on_date

    return None, as_on_date


def fetch_bse_mcap() -> dict:
    """
    Scrape BSE All India Market Cap.
    Returns a dict ready to be a CSV row.

    Status logic:
      OK    - scraped successfully, value in sane range
      STALE - scraped but value looks wrong
      ERROR - scrape failed
    """
    fetched_at = now_ist()

    try:
        resp = requests.get(URL, headers=HEADERS, timeout=20)
        resp.raise_for_status()

        mcap_value, as_on_date = extract_mcap(resp.text)

        if mcap_value is None:
            return {
                "timestamp": fetched_at,
                "ticker": "BSE_INDIA_MCAP",
                "name": "All India Market Cap",
                "value": None,
                "as_on_date": as_on_date,
                "fetched_at": fetched_at,
                "status": "ERROR",
                "note": "All extraction strategies failed (page structure may have changed)",
            }

        # Sanity check (already done in extractor, but double-check)
        if not (MCAP_MIN <= mcap_value <= MCAP_MAX):
            status = "STALE"
            note = f"Value {mcap_value:.2f} outside sane range [{MCAP_MIN}, {MCAP_MAX}]"
        else:
            status = "OK"
            note = ""

        return {
            "timestamp": fetched_at,
            "ticker": "BSE_INDIA_MCAP",
            "name": "All India Market Cap",
            "value": round(mcap_value, 2),
            "as_on_date": as_on_date,
            "fetched_at": fetched_at,
            "status": status,
            "note": note,
        }

    except requests.exceptions.HTTPError as e:
        return {
            "timestamp": fetched_at,
            "ticker": "BSE_INDIA_MCAP",
            "name": "All India Market Cap",
            "value": None,
            "as_on_date": None,
            "fetched_at": fetched_at,
            "status": "ERROR",
            "note": f"HTTP {e.response.status_code}",
        }

    except Exception as e:
        return {
            "timestamp": fetched_at,
            "ticker": "BSE_INDIA_MCAP",
            "name": "All India Market Cap",
            "value": None,
            "as_on_date": None,
            "fetched_at": fetched_at,
            "status": "ERROR",
            "note": f"{type(e).__name__}: {str(e)[:100]}",
        }


def append_to_csv(row: dict, output_file: Path):
    """Append a row to CSV, creating with headers if it doesn't exist."""
    new_df = pd.DataFrame([row])
    output_file.parent.mkdir(parents=True, exist_ok=True)

    if output_file.exists():
        new_df.to_csv(output_file, mode="a", header=False, index=False)
    else:
        new_df.to_csv(output_file, mode="w", header=True, index=False)


# ============================================================
# MAIN
# ============================================================

def main():
    print(f"[{now_ist()}] Starting BSE MCap scraper...")
    print(f"Output: {OUTPUT_FILE}")
    print("-" * 60)

    row = fetch_bse_mcap()

    status = row["status"]
    value = row["value"] if row["value"] is not None else "N/A"
    as_on = row.get("as_on_date") or "unknown"
    symbol = "OK " if status == "OK" else ("WARN" if status == "STALE" else "FAIL")

    # Format value with Indian-style commas for readable display
    if isinstance(value, (int, float)):
        value_str = f"{value:,.2f}"
    else:
        value_str = str(value)

    print(f"  [{symbol}] All India MCap = ₹ {value_str} Cr  (as on {as_on})  ({status})")
    if row.get("note"):
        print(f"        note: {row['note']}")

    append_to_csv(row, OUTPUT_FILE)

    print("-" * 60)
    print(f"[{now_ist()}] Done. Wrote 1 row to {OUTPUT_FILE}")

    if status == "ERROR":
        print("ERROR: Scrape failed. Exiting with code 1.")
        sys.exit(1)


if __name__ == "__main__":
    main()
