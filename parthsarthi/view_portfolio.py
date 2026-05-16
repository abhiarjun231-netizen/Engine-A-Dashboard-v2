"""
view_portfolio.py
Parthsarthi Capital - Phase 6, Item 6.3
THE DASHBOARD - PORTFOLIO VIEW.

This tab shows the actual book - what is held, how capital is split,
and whether the portfolio is within its limits. It is where the
Portfolio Master modules (Phase 5) surface visually.

Sections:
  1. Capital - Engine A regime, equity budget, B/C/D split,
               deployed vs free (from portfolio_capital, 5.1, 5.8)
  2. Holdings - every position across B/C/D, with its owning engine
  3. Concentration - per-stock exposure vs the 10% master cap
               (portfolio_stockcap, 5.2) and sector exposure vs the
               30% portfolio cap (portfolio_holdings, 5.5)

It is a VIEW module: it reads the held positions from the data
store and renders them through the Portfolio Master logic. It
exposes render(), called by app.py.
"""

import streamlit as st

NAVY    = '#0A1628'
SAFFRON = '#D97706'
GREEN   = '#16a34a'
RED     = '#dc2626'

ENGINE_NAME = {'B': 'Momentum', 'C': 'Value', 'D': 'Compounders'}


def _load_positions():
    """
    Load held positions. Reads the shared data store if present;
    otherwise returns an empty book (fresh paper-trading start).
    """
    try:
        from data_store import DataStore
        ds = DataStore()
        positions = []
        for p in ds.positions.values():
            positions.append({
                'ticker': p.ticker, 'engine': p.engine,
                'entry_price': p.entry_price, 'quantity': p.quantity,
                'current_value': p.invested(),   # marked at entry until live price wired
                'sector': 'Unknown',
            })
        return positions, ds.total_equity
    except Exception:
        return [], 0


def _capital_section():
    """Section 1 - capital allocation and the B/C/D split."""
    st.subheader('1. Capital')
    score = st.session_state.get('engine_a_score', 55)
    portfolio = st.session_state.get('total_portfolio', 1000000)

    try:
        from portfolio_engine_a import engine_a_directive, operating_gate
        from portfolio_capital import allocate
        alloc = allocate(portfolio, score)
        gate = operating_gate(score)
    except Exception as e:
        st.error(f'Could not load Portfolio Master capital logic: {e}')
        return

    c1, c2, c3 = st.columns(3)
    c1.metric('Engine A score', score)
    c2.metric('Regime', alloc['regime'])
    c3.metric('Operating gate', gate)

    c1, c2 = st.columns(2)
    c1.metric('Equity budget', f"Rs {alloc['equity_budget']:,.0f}")
    c2.metric('Non-equity (Engine E)', f"Rs {alloc['non_equity']:,.0f}")

    st.markdown('**Engine budgets (30 / 30 / 40 split):**')
    eb = alloc['engine_budgets']
    cols = st.columns(3)
    for col, code in zip(cols, ['B', 'C', 'D']):
        col.metric(f'Engine {code} - {ENGINE_NAME[code]}',
                   f"Rs {eb[code]:,.0f}")

    if gate != 'NORMAL':
        st.warning(f'Operating gate is **{gate}** - '
                   + ('all positions to be closed.' if gate == 'EXIT-ALL'
                      else 'no new entries permitted.'))


def _holdings_section(positions):
    """Section 2 - the held positions across all engines."""
    st.subheader('2. Holdings')
    if not positions:
        st.info('No positions held. The book is empty - a fresh '
                'paper-trading start.')
        return

    st.caption(f'{len(positions)} positions held across B, C and D.')
    rows = []
    for p in positions:
        rows.append({
            'Ticker': p['ticker'],
            'Engine': f"{p['engine']} - {ENGINE_NAME.get(p['engine'], '')}",
            'Entry': f"{p['entry_price']:,.1f}",
            'Qty': p['quantity'],
            'Value': f"Rs {p['current_value']:,.0f}",
        })
    st.dataframe(rows, use_container_width=True, hide_index=True)


def _concentration_section(positions):
    """Section 3 - per-stock and per-sector concentration checks."""
    st.subheader('3. Concentration Checks')
    if not positions:
        st.info('No positions - no concentration to check.')
        return

    total_equity = sum(p['current_value'] for p in positions)
    if total_equity <= 0:
        st.info('No deployed capital yet.')
        return

    # per-stock exposure vs the 10% master cap
    st.markdown('**Per-stock exposure (10% master cap):**')
    try:
        from portfolio_stockcap import MASTER_STOCK_CAP_PCT
        cap = MASTER_STOCK_CAP_PCT
    except Exception:
        cap = 10.0

    by_stock = {}
    for p in positions:
        by_stock[p['ticker']] = by_stock.get(p['ticker'], 0) + p['current_value']
    rows = []
    for tk, val in sorted(by_stock.items(), key=lambda x: -x[1]):
        pct = val / total_equity * 100
        flag = 'OVER CAP' if pct > cap else 'ok'
        rows.append({'Stock': tk, 'Exposure': f'{pct:.1f}%',
                     'Status': flag})
    st.dataframe(rows, use_container_width=True, hide_index=True)

    # per-sector exposure vs the 30% portfolio cap
    st.markdown('**Sector exposure (30% portfolio cap):**')
    try:
        from portfolio_holdings import portfolio_sector_exposure, SECTOR_CAP_PCT
        sectors = portfolio_sector_exposure(positions)
        scap = SECTOR_CAP_PCT
    except Exception:
        sectors, scap = {}, 30.0

    if sectors:
        rows = []
        for s, pct in sorted(sectors.items(), key=lambda x: -x[1]):
            flag = 'OVER CAP' if pct > scap else 'ok'
            rows.append({'Sector': s, 'Exposure': f'{pct:.1f}%',
                         'Status': flag})
        st.dataframe(rows, use_container_width=True, hide_index=True)
    else:
        st.caption('Sector data not available for held positions.')


def render():
    """Render the Portfolio tab. Called by app.py."""
    st.header('Portfolio')
    positions, _ = _load_positions()

    _capital_section()
    st.divider()
    _holdings_section(positions)
    st.divider()
    _concentration_section(positions)


# ---- self-test (structure check) ----
if __name__ == '__main__':
    import ast
    src = open(__file__).read()
    ast.parse(src)
    print('=' * 56)
    print('PORTFOLIO VIEW (6.3) - structure self-test')
    print('=' * 56)
    funcs = [n.name for n in ast.walk(ast.parse(src))
             if isinstance(n, ast.FunctionDef)]
    print('Functions defined:', funcs)
    print('render() present:', 'render' in funcs)
    print('\nSyntax valid. Full visual render requires the Streamlit')
    print('runtime - verified live when the dashboard is deployed (6.7).')
    print('=' * 56)
