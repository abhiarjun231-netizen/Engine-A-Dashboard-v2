"""
data_guard.py
Parthsarthi Capital - Phase 1, Item 1.4
RISK LAYER 4 - STALE detection & CSV schema check.

The principle, from the Master Framework:
  "The system must know when it is blind, and refuse to act
   rather than act on bad data."

This module is the gatekeeper. Before any engine is allowed to make
decisions from a screener upload, the upload must pass through here.
It checks two things:

  1. SCHEMA  - does the CSV have the columns the engine expects?
               A malformed / changed Trendlyne export is rejected,
               not parsed half-way.

  2. STALENESS - how old is the data? If the most recent upload is
               more than 48 hours old, the system is STALE and must
               not make decisions on it.

If either check fails, the engine does not run. The dashboard shows a
STALE / REJECTED banner instead of acting on unreliable data.
"""

import os
import csv
from datetime import datetime, timedelta


# Maximum age before data is considered STALE
STALE_HOURS = 48

# The 34-column schema expected from every Trendlyne screener export
# (B, C and D screeners all use this same export format).
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


class GuardResult:
    """Outcome of a data-guard check."""

    def __init__(self):
        self.schema_ok = False
        self.fresh_ok = False
        self.errors = []
        self.warnings = []
        self.age_hours = None
        self.row_count = 0

    @property
    def passed(self):
        """The engine may run only if BOTH checks pass."""
        return self.schema_ok and self.fresh_ok

    @property
    def status(self):
        if self.passed:
            return 'OK'
        if not self.schema_ok:
            return 'REJECTED'   # bad file - never act on it
        return 'STALE'          # file fine, but too old

    def banner(self):
        """One-line message for the dashboard."""
        if self.passed:
            return f'OK - data fresh ({self.age_hours:.1f}h old), {self.row_count} stocks'
        if not self.schema_ok:
            return f'REJECTED - {self.errors[0] if self.errors else "schema check failed"}'
        return (f'STALE - data is {self.age_hours:.1f}h old '
                f'(limit {STALE_HOURS}h). Decisions are frozen.')


def check_schema(csv_path):
    """
    Verify the CSV has the expected columns. Returns (ok, errors, row_count).
    Uses whitespace-normalised comparison (Trendlyne has stray spaces).
    """
    errors = []
    if not os.path.exists(csv_path):
        return False, [f'File not found: {csv_path}'], 0

    try:
        with open(csv_path, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            cols = [c.strip() for c in (reader.fieldnames or [])]
            cols_norm = {c.strip() for c in cols}

            missing = [c for c in EXPECTED_COLUMNS if c.strip() not in cols_norm]
            if missing:
                errors.append(
                    f'{len(missing)} expected column(s) missing, '
                    f'e.g. {missing[:3]}')

            rows = list(reader)
            row_count = len(rows)
            if row_count == 0:
                errors.append('CSV has columns but zero stock rows')

        return (len(errors) == 0, errors, row_count)

    except Exception as e:
        return False, [f'Failed to read CSV: {e}'], 0


def check_freshness(csv_path, now=None):
    """
    Check how old the file is, by its modification time.
    Returns (ok, age_hours). ok is False if older than STALE_HOURS.
    `now` can be injected for testing.
    """
    now = now or datetime.now()
    if not os.path.exists(csv_path):
        return False, None

    mtime = datetime.fromtimestamp(os.path.getmtime(csv_path))
    age = (now - mtime).total_seconds() / 3600.0
    return (age <= STALE_HOURS, age)


def guard(csv_path, now=None, file_date=None):
    """
    The full Risk Layer 4 gate. Run this before any engine acts on an upload.

    `file_date` - optional explicit data date (ISO string). If given, freshness
    is judged on this rather than the file's modification time. This matters
    because a freshly-downloaded file can still contain stale market data.

    Returns a GuardResult. Engine runs only if result.passed is True.
    """
    now = now or datetime.now()
    result = GuardResult()

    # 1. schema
    schema_ok, errors, row_count = check_schema(csv_path)
    result.schema_ok = schema_ok
    result.errors.extend(errors)
    result.row_count = row_count

    # 2. freshness
    if file_date:
        try:
            d = datetime.fromisoformat(file_date)
            age = (now - d).total_seconds() / 3600.0
            result.fresh_ok = age <= STALE_HOURS
            result.age_hours = age
        except ValueError:
            result.warnings.append(f'Bad file_date: {file_date}; using mtime')
            fresh_ok, age = check_freshness(csv_path, now)
            result.fresh_ok, result.age_hours = fresh_ok, age
    else:
        fresh_ok, age = check_freshness(csv_path, now)
        result.fresh_ok = fresh_ok
        result.age_hours = age

    if result.age_hours is not None and not result.fresh_ok:
        result.errors.append(
            f'Data is {result.age_hours:.1f}h old, exceeds {STALE_HOURS}h limit')

    return result


# ---- self-test ----
if __name__ == '__main__':
    print('=' * 58)
    print('DATA GUARD (Risk Layer 4) - self-test')
    print('=' * 58)

    # build a valid mini CSV
    valid_path = '/tmp/guard_valid.csv'
    with open(valid_path, 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.writer(f)
        w.writerow(EXPECTED_COLUMNS)
        w.writerow(['1', 'Test Stock'] + ['0'] * (len(EXPECTED_COLUMNS) - 2))

    # build a malformed CSV (missing columns)
    bad_path = '/tmp/guard_bad.csv'
    with open(bad_path, 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.writer(f)
        w.writerow(['Stock', 'LTP', 'Sector'])   # only 3 columns
        w.writerow(['Test', '100', 'Metals'])

    now = datetime.now()

    # Test 1: valid + fresh
    print('\nTest 1 - valid schema, fresh data:')
    r = guard(valid_path, now=now, file_date=now.isoformat())
    print(f'  status={r.status}  passed={r.passed}')
    print(f'  {r.banner()}')

    # Test 2: valid schema, STALE data (3 days old)
    print('\nTest 2 - valid schema, stale data (72h old):')
    old_date = (now - timedelta(hours=72)).isoformat()
    r = guard(valid_path, now=now, file_date=old_date)
    print(f'  status={r.status}  passed={r.passed}')
    print(f'  {r.banner()}')

    # Test 3: malformed schema
    print('\nTest 3 - malformed CSV (missing columns):')
    r = guard(bad_path, now=now, file_date=now.isoformat())
    print(f'  status={r.status}  passed={r.passed}')
    print(f'  {r.banner()}')

    # Test 4: missing file
    print('\nTest 4 - file does not exist:')
    r = guard('/tmp/nonexistent.csv', now=now)
    print(f'  status={r.status}  passed={r.passed}')
    print(f'  {r.banner()}')

    # Test 5: borderline - exactly at the 48h limit
    print('\nTest 5 - borderline freshness (47h old, just inside limit):')
    edge = (now - timedelta(hours=47)).isoformat()
    r = guard(valid_path, now=now, file_date=edge)
    print(f'  status={r.status}  passed={r.passed}')

    os.remove(valid_path)
    os.remove(bad_path)

    print('\n' + '=' * 58)
    print('Self-test complete. The guard blocks malformed uploads')
    print('(REJECTED) and stale data (STALE); engines run only on OK.')
    print('=' * 58)
