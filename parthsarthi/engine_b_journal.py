"""
engine_b_journal.py
Parthsarthi Capital · Engine B Intelligence System · Step 1 of build

THE DAILY JOURNAL — screen-diff module.

This is the foundation of Engine B's intelligence. It does ONE job:
compare two daily screener CSV exports and record what changed.

  ENTERED  - on today's screen, not yesterday's   (new candidate)
  LEFT     - on yesterday's screen, not today's   (churn event)
  STAYED   - on both, with score deltas tracked   (trend)

Everything downstream — churn handler, conviction scoring, pattern
analysis — depends on this diff. The journal is the system's memory.

It does NOT yet make decisions. That is Step 2+. Step 1 only answers:
"what changed between yesterday and today?"

INPUT  : two Trendlyne 'Mom 1' CSV exports (34-column format)
OUTPUT : a structured journal entry (JSON) appended to the journal file

Usage:
    python engine_b_journal.py <yesterday.csv> <today.csv>
    python engine_b_journal.py <today.csv>          # first ever run
"""

import sys
import os
import json
import csv
from datetime import datetime


JOURNAL_FILE = 'engine_b_journal.json'

# The 34-column schema we expect from the Trendlyne 'Mom 1' export.
# Schema check (Risk Layer 4) rejects any upload that doesn't match.
EXPECTED_COLUMNS = [
    'Sl No', 'Stock', 'Delivery Vol  Avg Month', 'Delivery Vol  Avg Week',
    'Delivery% Vol  Avg Week', 'Delivery Vol  Prev EOD', 'Delivery% Vol  Avg Month',
    'Delivery Vol  EOD', 'Delivery% Vol  Prev EOD', 'Delivery% Vol  EOD',
    'Latest Financial Result', 'Net Profit 3Y Growth %', 'PEG TTM',
    'Net Profit QoQ Growth %', 'Rev  Growth Qtr YoY %', 'Revenue QoQ Growth %',
    'Durability Score', 'Momentum Score', '1Y Low', '1Y High', 'LTP',
    'MF holding current Qtr %', 'Total Debt to Total Equity Ann ',
    'Net Profit Ann  YoY Growth %', 'FII holding current Qtr %',
    'Institutional holding current Qtr %', 'Promoter holding latest %',
    'Sector', 'Piotroski Score', 'Market Cap', 'PE TTM', 'ROE Ann  %',
    'NSE Code', 'BSE Code', 'ISIN',
]

# Fields tracked for day-on-day deltas on STAYED stocks.
DELTA_FIELDS = ['Durability Score', 'Momentum Score', 'LTP', 'PE TTM']


def load_screener_csv(path):
    """
    Load a Trendlyne screener CSV.
    Returns (rows_by_ticker, error). error is None on success.
    Handles the BOM Trendlyne prepends and the quoted-field format.
    """
    if not os.path.exists(path):
        return None, f"File not found: {path}"

    try:
        # utf-8-sig strips the BOM Trendlyne adds to the first column name
        with open(path, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            cols = [c.strip() for c in (reader.fieldnames or [])]

            # --- Risk Layer 4: schema check ---
            # Compare on whitespace-normalised names (Trendlyne has stray spaces)
            cols_norm = {c.strip() for c in cols}
            missing = [c for c in EXPECTED_COLUMNS if c.strip() not in cols_norm]
            if missing:
                return None, (f"Schema mismatch — {len(missing)} expected "
                              f"column(s) missing, e.g. {missing[:3]}. "
                              f"Upload rejected (Risk Layer 4).")

            rows = {}
            for raw in reader:
                # normalise keys (strip stray spaces)
                row = {k.strip(): (v.strip() if isinstance(v, str) else v)
                       for k, v in raw.items()}
                ticker = row.get('NSE Code') or row.get('Stock')
                if ticker:
                    rows[ticker] = row

        if not rows:
            return None, "CSV parsed but contained no stock rows."
        return rows, None

    except Exception as e:
        return None, f"Failed to read CSV: {e}"


def _num(value):
    """Best-effort numeric parse. Returns None if not parseable."""
    try:
        return float(str(value).replace(',', ''))
    except (ValueError, AttributeError, TypeError):
        return None


def compute_diff(yesterday, today):
    """
    Compare two {ticker: row} dicts.
    Returns dict with entered / left / stayed lists.
    """
    y_tickers = set(yesterday.keys()) if yesterday else set()
    t_tickers = set(today.keys())

    entered_tickers = sorted(t_tickers - y_tickers)
    left_tickers    = sorted(y_tickers - t_tickers)
    stayed_tickers  = sorted(t_tickers & y_tickers)

    entered = []
    for tk in entered_tickers:
        r = today[tk]
        entered.append({
            'ticker':     tk,
            'name':       r.get('Stock'),
            'sector':     r.get('Sector'),
            'durability': _num(r.get('Durability Score')),
            'momentum':   _num(r.get('Momentum Score')),
            'ltp':        _num(r.get('LTP')),
            'pe':         _num(r.get('PE TTM')),
            'full_row':   r,   # keep all 34 fields for downstream modules
        })

    left = []
    for tk in left_tickers:
        r = yesterday[tk]
        left.append({
            'ticker':         tk,
            'name':           r.get('Stock'),
            'sector':         r.get('Sector'),
            'last_durability': _num(r.get('Durability Score')),
            'last_momentum':   _num(r.get('Momentum Score')),
            'last_ltp':        _num(r.get('LTP')),
        })

    stayed = []
    for tk in stayed_tickers:
        y, t = yesterday[tk], today[tk]
        deltas = {}
        for field in DELTA_FIELDS:
            yv, tv = _num(y.get(field)), _num(t.get(field))
            if yv is not None and tv is not None:
                deltas[field] = round(tv - yv, 2)
        stayed.append({
            'ticker': tk,
            'name':   t.get('Stock'),
            'deltas': deltas,
        })

    return {'entered': entered, 'left': left, 'stayed': stayed}


def build_journal_entry(today_path, diff, today_count):
    """Assemble the structured journal entry for this run."""
    return {
        'run_timestamp':  datetime.now().isoformat(timespec='seconds'),
        'source_file':    os.path.basename(today_path),
        'stocks_on_screen': today_count,
        'summary': {
            'entered': len(diff['entered']),
            'left':    len(diff['left']),
            'stayed':  len(diff['stayed']),
        },
        'entered': diff['entered'],
        'left':    diff['left'],
        'stayed':  diff['stayed'],
    }


def append_to_journal(entry, journal_path=JOURNAL_FILE):
    """Append entry to the rolling journal file (JSON list)."""
    journal = []
    if os.path.exists(journal_path):
        try:
            with open(journal_path, 'r') as f:
                journal = json.load(f)
        except (json.JSONDecodeError, ValueError):
            journal = []
    journal.append(entry)
    with open(journal_path, 'w') as f:
        json.dump(journal, f, indent=2)
    return len(journal)


def print_report(entry):
    """Human-readable summary of the diff."""
    s = entry['summary']
    print('=' * 56)
    print(f"ENGINE B JOURNAL  ·  {entry['run_timestamp']}")
    print(f"Source: {entry['source_file']}")
    print('=' * 56)
    print(f"On screen today : {entry['stocks_on_screen']}")
    print(f"  ENTERED : {s['entered']}")
    print(f"  LEFT    : {s['left']}")
    print(f"  STAYED  : {s['stayed']}")

    if entry['entered']:
        print("\n--- ENTERED (new candidates) ---")
        for e in entry['entered']:
            print(f"  + {e['ticker']:14} D{e['durability']} M{e['momentum']} "
                  f"  {e['sector']}")

    if entry['left']:
        print("\n--- LEFT (churn events — review held positions) ---")
        for e in entry['left']:
            print(f"  - {e['ticker']:14} last D{e['last_durability']} "
                  f"M{e['last_momentum']}")

    if entry['stayed']:
        # Show only stayed stocks with a notable momentum move
        movers = [s for s in entry['stayed']
                  if abs(s['deltas'].get('Momentum Score', 0)) >= 5]
        if movers:
            print("\n--- STAYED · notable momentum moves (>=5 pts) ---")
            for m in movers:
                d = m['deltas'].get('Momentum Score', 0)
                arrow = 'up' if d > 0 else 'down'
                print(f"  ~ {m['ticker']:14} Momentum {arrow} {abs(d)} pts")
    print('=' * 56)


def main():
    args = sys.argv[1:]
    if len(args) == 1:
        # First-ever run — no yesterday to compare
        today_path = args[0]
        yesterday_path = None
        print("First run — no prior CSV. Everything logs as ENTERED (baseline).")
    elif len(args) == 2:
        yesterday_path, today_path = args
    else:
        print("Usage:")
        print("  python engine_b_journal.py <today.csv>              (first run)")
        print("  python engine_b_journal.py <yesterday.csv> <today.csv>")
        sys.exit(1)

    today, err = load_screener_csv(today_path)
    if err:
        print(f"ERROR (today's file): {err}")
        sys.exit(1)

    yesterday = None
    if yesterday_path:
        yesterday, err = load_screener_csv(yesterday_path)
        if err:
            print(f"ERROR (yesterday's file): {err}")
            sys.exit(1)

    diff = compute_diff(yesterday, today)
    entry = build_journal_entry(today_path, diff, len(today))
    total = append_to_journal(entry)
    print_report(entry)
    print(f"\nJournal now holds {total} day(s) of history → {JOURNAL_FILE}")


if __name__ == '__main__':
    main()
