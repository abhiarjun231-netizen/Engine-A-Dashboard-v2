"""
data_store.py
Parthsarthi Capital - Phase 1, Item 1.5
THE SHARED DATA STORE - persistent memory for the whole system.

Everything the system needs to remember between runs lives here:
  - POSITIONS  : what is currently held, per engine
  - CAPITAL    : capital allocated and deployed, per engine
  - HISTORY    : every closed position (the track record)

The journal (1.1) remembers what the SCREENER did day to day.
The state model (1.2) remembers what STATE each stock is in.
This store remembers the PORTFOLIO - the actual holdings, money,
and the closed-trade record that the AI pattern layer will study.

One JSON file is the single source of truth. Every write saves
immediately - the system must survive being closed at any moment.
"""

import os
import json
from datetime import datetime


STORE_FILE = 'parthsarthi_store.json'

# Locked capital split from the Portfolio Master framework
ENGINE_SPLIT = {'B': 0.30, 'C': 0.30, 'D': 0.40}


class Position:
    """One open holding."""

    def __init__(self, ticker, engine, entry_price, quantity,
                 entry_date=None, conviction=None, target_value=None):
        self.ticker = ticker
        self.engine = engine                # owning engine - B / C / D
        self.entry_price = entry_price
        self.quantity = quantity
        self.entry_date = entry_date or datetime.now().isoformat(timespec='seconds')
        self.conviction = conviction        # conviction score at entry
        self.target_value = target_value    # intended full-size value
        self.peak_price = entry_price       # for trailing stops
        self.notes = []                     # list of (date, note)

    def invested(self):
        return self.entry_price * self.quantity

    def current_value(self, price):
        return price * self.quantity

    def pnl_pct(self, price):
        if self.entry_price == 0:
            return 0.0
        return (price - self.entry_price) / self.entry_price * 100.0

    def update_peak(self, price):
        if price > self.peak_price:
            self.peak_price = price

    def to_dict(self):
        return {
            'ticker': self.ticker, 'engine': self.engine,
            'entry_price': self.entry_price, 'quantity': self.quantity,
            'entry_date': self.entry_date, 'conviction': self.conviction,
            'target_value': self.target_value, 'peak_price': self.peak_price,
            'notes': self.notes,
        }

    @staticmethod
    def from_dict(d):
        p = Position(d['ticker'], d['engine'], d['entry_price'],
                     d['quantity'], d['entry_date'], d.get('conviction'),
                     d.get('target_value'))
        p.peak_price = d.get('peak_price', d['entry_price'])
        p.notes = d.get('notes', [])
        return p


class DataStore:
    """The single persistent store for positions, capital and history."""

    def __init__(self, store_path=None):
        self.store_path = store_path or STORE_FILE
        self.total_equity = 0.0          # set by Engine A regime
        self.positions = {}              # ticker -> Position
        self.history = []                # closed-trade records
        self.meta = {}                   # misc: last update, etc.
        self._load()

    # ---- persistence ----
    def _load(self):
        if os.path.exists(self.store_path):
            try:
                with open(self.store_path) as f:
                    d = json.load(f)
                self.total_equity = d.get('total_equity', 0.0)
                self.positions = {t: Position.from_dict(p)
                                  for t, p in d.get('positions', {}).items()}
                self.history = d.get('history', [])
                self.meta = d.get('meta', {})
            except (json.JSONDecodeError, ValueError):
                pass

    def _save(self):
        self.meta['last_update'] = datetime.now().isoformat(timespec='seconds')
        with open(self.store_path, 'w') as f:
            json.dump({
                'total_equity': self.total_equity,
                'positions': {t: p.to_dict() for t, p in self.positions.items()},
                'history': self.history,
                'meta': self.meta,
            }, f, indent=2)

    # ---- capital ----
    def set_total_equity(self, amount):
        """Engine A sets the total equity budget."""
        self.total_equity = amount
        self._save()

    def engine_capital(self, engine):
        """Capital allocated to one engine, per the locked split."""
        return self.total_equity * ENGINE_SPLIT.get(engine, 0.0)

    def engine_deployed(self, engine):
        """Capital currently invested by one engine."""
        return sum(p.invested() for p in self.positions.values()
                   if p.engine == engine)

    def engine_free(self, engine):
        """Capital still available to one engine."""
        return self.engine_capital(engine) - self.engine_deployed(engine)

    # ---- positions ----
    def open_position(self, position):
        """Record a new holding."""
        if position.ticker in self.positions:
            raise ValueError(f'{position.ticker} already held - '
                             f'no averaging up (framework rule).')
        self.positions[position.ticker] = position
        self._save()
        return True

    def close_position(self, ticker, exit_price, reason):
        """
        Close a holding, move it to history with full record.
        `reason` is mandatory - the audit trail requires it.
        """
        if not reason or not str(reason).strip():
            raise ValueError('Closing a position requires a reason.')
        if ticker not in self.positions:
            raise ValueError(f'{ticker} is not held.')

        p = self.positions.pop(ticker)
        pnl_pct = p.pnl_pct(exit_price)
        record = {
            'ticker': p.ticker, 'engine': p.engine,
            'entry_date': p.entry_date,
            'exit_date': datetime.now().isoformat(timespec='seconds'),
            'entry_price': p.entry_price, 'exit_price': exit_price,
            'quantity': p.quantity, 'conviction': p.conviction,
            'pnl_pct': round(pnl_pct, 2),
            'pnl_value': round((exit_price - p.entry_price) * p.quantity, 2),
            'exit_reason': reason,
        }
        self.history.append(record)
        self._save()
        return record

    def get_position(self, ticker):
        return self.positions.get(ticker)

    def positions_for_engine(self, engine):
        return [p for p in self.positions.values() if p.engine == engine]

    # ---- track record ----
    def stats(self, engine=None):
        """Win/loss statistics from closed history."""
        trades = [h for h in self.history
                  if engine is None or h['engine'] == engine]
        if not trades:
            return {'trades': 0, 'wins': 0, 'losses': 0,
                    'win_rate': 0.0, 'avg_pnl': 0.0}
        wins = [t for t in trades if t['pnl_pct'] > 0]
        avg = sum(t['pnl_pct'] for t in trades) / len(trades)
        return {
            'trades': len(trades),
            'wins': len(wins),
            'losses': len(trades) - len(wins),
            'win_rate': round(len(wins) / len(trades) * 100, 1),
            'avg_pnl': round(avg, 2),
        }


# ---- self-test ----
if __name__ == '__main__':
    print('=' * 58)
    print('SHARED DATA STORE - self-test')
    print('=' * 58)

    test_file = '/tmp/store_test.json'
    if os.path.exists(test_file):
        os.remove(test_file)

    ds = DataStore(store_path=test_file)

    # 1. Engine A sets equity budget
    ds.set_total_equity(1000000)   # Rs 10 lakh
    print('\nTotal equity set: Rs 10,00,000')
    print(f"  Engine B capital: Rs {ds.engine_capital('B'):,.0f}")
    print(f"  Engine C capital: Rs {ds.engine_capital('C'):,.0f}")
    print(f"  Engine D capital: Rs {ds.engine_capital('D'):,.0f}")

    # 2. open two positions in Engine B
    ds.open_position(Position('TATASTEEL', 'B', 140.0, 1000, conviction=8))
    ds.open_position(Position('JSWSTEEL',  'B', 900.0, 100,  conviction=7))
    print('\nOpened 2 Engine B positions:')
    print(f"  B deployed: Rs {ds.engine_deployed('B'):,.0f}")
    print(f"  B free:     Rs {ds.engine_free('B'):,.0f}")

    # 3. no-averaging rule
    print('\nAttempting to re-open TATASTEEL (averaging up)...')
    try:
        ds.open_position(Position('TATASTEEL', 'B', 130.0, 500))
        print('  ERROR: averaging up was allowed!')
    except ValueError as e:
        print(f'  Correctly rejected: {e}')

    # 4. close a position at a profit
    rec = ds.close_position('TATASTEEL', 168.0, 'Trailing stop hit at +20%')
    print(f"\nClosed TATASTEEL: {rec['pnl_pct']}% "
          f"(Rs {rec['pnl_value']:,.0f})  reason: {rec['exit_reason']}")

    # 5. close one at a loss
    ds.close_position('JSWSTEEL', 820.0, 'Hard stop -15% from peak')

    # 6. track record
    print('\nEngine B track record:')
    s = ds.stats('B')
    print(f"  trades={s['trades']}  wins={s['wins']}  losses={s['losses']}  "
          f"win_rate={s['win_rate']}%  avg_pnl={s['avg_pnl']}%")

    # 7. persistence - reload from disk
    ds2 = DataStore(store_path=test_file)
    print('\nReloaded store from disk:')
    print(f"  total equity: Rs {ds2.total_equity:,.0f}")
    print(f"  open positions: {len(ds2.positions)}")
    print(f"  closed history: {len(ds2.history)} trades")

    os.remove(test_file)
    print('\n' + '=' * 58)
    print('Self-test complete. The store persists capital, positions and')
    print('the closed-trade record, and enforces the no-averaging rule.')
    print('=' * 58)
