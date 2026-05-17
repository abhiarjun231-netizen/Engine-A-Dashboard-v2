"""
engine_a_link.py
Parthsarthi Capital - Engine A linkage (live read).

Engine A runs as a scheduled GitHub Actions cron in this same repo.
Every cycle it writes its result to:

    data/core/engine_a_current.json

This module READS that file so the Parthsarthi dashboard never asks
the user to type the score by hand. Engine A computes; Parthsarthi
reads. One repo, one source of truth.

It also maps Engine A's regime vocabulary onto the operating gate
that the Parthsarthi engines and Portfolio Master already understand.

If the file cannot be found or read, this module returns a clearly
flagged fallback so the dashboard degrades gracefully instead of
crashing - the user can still enter a score manually.
"""

import json
import os


# candidate paths - the app may run from parthsarthi/ or the repo root
_CANDIDATE_PATHS = [
    '../data/core/engine_a_current.json',   # app runs from parthsarthi/
    'data/core/engine_a_current.json',      # app runs from repo root
    './data/core/engine_a_current.json',
]


def _find_json():
    """Return the first engine_a_current.json path that exists, or None."""
    for p in _CANDIDATE_PATHS:
        if os.path.exists(p):
            return p
    return None


def operating_gate(score):
    """
    Map a 0-100 Engine A score onto the Parthsarthi operating gate.
      score <= 20  -> EXIT-ALL   close all equity
      score <= 30  -> FREEZE     hold, no new entries
      score  > 30  -> NORMAL     operate normally
    """
    if score is None:
        return 'NORMAL'
    if score <= 20:
        return 'EXIT-ALL'
    if score <= 30:
        return 'FREEZE'
    return 'NORMAL'


def load_engine_a():
    """
    Load Engine A's live result.

    Returns a dict with a consistent shape:
      {
        'available':  True/False,   - was the JSON found and read?
        'source':     'live' | 'fallback',
        'score':      int 0-100,
        'regime':     str,          - Engine A's own regime label
        'equity_pct': int,          - Engine A's equity allocation %
        'gate':       str,          - Parthsarthi gate (NORMAL/FREEZE/EXIT-ALL)
        'guidance':   str,
        'computed_at':str,
        'components': dict,         - the 8 component breakdown
        'pending':    int,          - manual inputs still pending
        'note':       str,          - human-readable status
      }
    """
    path = _find_json()
    if path is None:
        return {
            'available': False,
            'source': 'fallback',
            'score': 55,
            'regime': 'UNKNOWN',
            'equity_pct': 55,
            'gate': 'NORMAL',
            'guidance': 'Engine A data not found - using a manual default.',
            'computed_at': 'n/a',
            'components': {},
            'pending': 0,
            'note': ('Engine A score file not found. The dashboard is '
                     'using a manual default of 55. Check that the Engine '
                     'A cron has run and committed data/core/'
                     'engine_a_current.json.'),
        }

    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except (json.JSONDecodeError, ValueError, OSError) as e:
        return {
            'available': False,
            'source': 'fallback',
            'score': 55,
            'regime': 'UNKNOWN',
            'equity_pct': 55,
            'gate': 'NORMAL',
            'guidance': f'Engine A file could not be read ({e}).',
            'computed_at': 'n/a',
            'components': {},
            'pending': 0,
            'note': f'Engine A score file found but unreadable: {e}',
        }

    score = data.get('score')
    regime = data.get('regime', 'UNKNOWN')
    equity_pct = data.get('equity_allocation',
                          data.get('regime_equity_pct', 55))
    pending = data.get('pending_manual_count', 0)

    note = f'Live Engine A score, computed {data.get("computed_at_ist", "n/a")}.'
    if pending and pending > 0:
        note += (f' Note: {pending} manual input(s) still pending - the '
                 f'score is partial.')

    return {
        'available': True,
        'source': 'live',
        'score': score,
        'regime': regime,
        'equity_pct': equity_pct,
        'gate': operating_gate(score),
        'guidance': data.get('guidance', ''),
        'computed_at': data.get('computed_at_ist', 'n/a'),
        'components': data.get('components', {}),
        'pending': pending,
        'note': note,
    }


# ---- self-test ----
if __name__ == '__main__':
    print('=' * 60)
    print('ENGINE A LINK - self-test')
    print('=' * 60)

    # gate mapping
    print('\nGate mapping:')
    for s in [85, 55, 44, 30, 25, 15]:
        print(f'  score {s:3} -> {operating_gate(s)}')

    # live load
    print('\nLive load:')
    a = load_engine_a()
    print(f'  available : {a["available"]}  (source: {a["source"]})')
    print(f'  score     : {a["score"]}')
    print(f'  regime    : {a["regime"]}')
    print(f'  equity %  : {a["equity_pct"]}')
    print(f'  gate      : {a["gate"]}')
    print(f'  note      : {a["note"]}')

    print('\n' + '=' * 60)
    print('Engine A link reads the cron-written JSON; the dashboard')
    print('never needs a hand-typed score.')
    print('=' * 60)
