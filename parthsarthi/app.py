"""
app.py
Parthsarthi Capital - Phase 6, Item 6.1
THE DASHBOARD - Streamlit admin interface with CSV upload.

This is the entry point of the usable product. It is a thin router:
a sidebar of tabs, and an admin panel where the three engine
screener CSVs are uploaded. The heavy logic lives in the engine
and Portfolio Master modules already built; this file only wires
the interface to them.

Phase 6 builds the dashboard tab by tab:
  6.1 - this file: admin + CSV upload (the shell)
  6.2 - decision view
  6.3 - portfolio view
  6.4 - journal view
  6.5 - AI narration layer
  6.6 - public dashboard tab

Run locally:   streamlit run app.py
Deploy (6.7):  Streamlit Community Cloud, pointed at the GitHub repo.
"""

import streamlit as st
from datetime import datetime

# Parthsarthi brand palette
NAVY    = '#0A1628'
CREAM   = '#FDFBF5'
SAFFRON = '#D97706'


def setup_page():
    """Page config and brand styling."""
    st.set_page_config(
        page_title='Parthsarthi Capital',
        page_icon='*',
        layout='wide',
        initial_sidebar_state='expanded',
    )
    st.markdown(f"""
        <style>
        .stApp {{ background-color: {CREAM}; }}
        h1, h2, h3 {{ color: {NAVY}; }}
        .brand-bar {{
            background-color: {NAVY}; color: {CREAM};
            padding: 14px 20px; border-radius: 8px; margin-bottom: 18px;
        }}
        .brand-bar .name {{ font-size: 22px; font-weight: 700; }}
        .brand-bar .tag  {{ font-size: 13px; color: {SAFFRON}; }}
        </style>
    """, unsafe_allow_html=True)


def brand_header():
    st.markdown(f"""
        <div class="brand-bar">
          <div class="name">PARTHSARTHI CAPITAL</div>
          <div class="tag">Your charioteer in Indian markets</div>
        </div>
    """, unsafe_allow_html=True)


def init_state():
    """Initialise the session state containers used across tabs."""
    defaults = {
        'screener_b': None,      # uploaded momentum CSV (raw bytes)
        'screener_c': None,      # uploaded C2 value CSV
        'screener_d': None,      # uploaded D1 compounder CSV
        'engine_a_score': 55,    # current Engine A regime score
        'total_portfolio': 1000000,
        'last_run': None,        # timestamp of the last cycle run
        'decisions': [],         # decisions from the last cycle
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


def admin_panel():
    """The admin tab - CSV upload and run controls."""
    st.header('Admin - Data & Controls')

    # ---- Engine A regime input ----
    st.subheader('1. Engine A - Regime')
    col1, col2 = st.columns(2)
    with col1:
        score = st.number_input(
            'Engine A score (0-100)', min_value=0, max_value=100,
            value=st.session_state['engine_a_score'], step=1,
            help='The macro regime score from Engine A. Sets the equity '
                 'budget and the operating gate.')
        st.session_state['engine_a_score'] = score
    with col2:
        portfolio = st.number_input(
            'Total portfolio value (Rs)', min_value=0,
            value=st.session_state['total_portfolio'], step=10000)
        st.session_state['total_portfolio'] = portfolio

    # show the regime that score implies
    gate = ('EXIT-ALL' if score <= 20 else
            'FREEZE' if score <= 30 else 'NORMAL')
    st.info(f'Operating gate at score {score}: **{gate}**')

    st.divider()

    # ---- screener uploads ----
    st.subheader('2. Upload Screener CSVs')
    st.caption('Upload the daily Trendlyne exports for each engine. '
               'Each is validated by the data guard before any decision '
               'is made.')

    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown('**Engine B - Momentum**')
        f = st.file_uploader('Momentum screener', type='csv',
                             key='upload_b', label_visibility='collapsed')
        if f is not None:
            st.session_state['screener_b'] = f
            st.success(f'Loaded: {f.name}')
    with c2:
        st.markdown('**Engine C - Value**')
        f = st.file_uploader('C2 value screener', type='csv',
                             key='upload_c', label_visibility='collapsed')
        if f is not None:
            st.session_state['screener_c'] = f
            st.success(f'Loaded: {f.name}')
    with c3:
        st.markdown('**Engine D - Compounders**')
        f = st.file_uploader('D1 compounder screener', type='csv',
                             key='upload_d', label_visibility='collapsed')
        if f is not None:
            st.session_state['screener_d'] = f
            st.success(f'Loaded: {f.name}')

    st.divider()

    # ---- run controls ----
    st.subheader('3. Run the Daily Cycle')
    uploaded = sum(1 for k in ['screener_b', 'screener_c', 'screener_d']
                   if st.session_state[k] is not None)
    st.caption(f'{uploaded}/3 screeners uploaded.')

    if st.button('Run Daily Cycle', type='primary',
                 disabled=(uploaded == 0)):
        st.session_state['last_run'] = datetime.now()
        st.success('Cycle run recorded. (Engine wiring is completed in '
                   'items 6.2-6.5 - this 6.1 shell handles upload and '
                   'controls.)')

    if st.session_state['last_run']:
        st.caption(f"Last cycle run: "
                   f"{st.session_state['last_run']:%Y-%m-%d %H:%M}")


def placeholder_tab(name, item):
    """A placeholder for tabs built later in Phase 6."""
    st.header(name)
    st.info(f'This tab is built in Phase 6 item {item}.')


def main():
    setup_page()
    init_state()
    brand_header()

    tab = st.sidebar.radio(
        'Navigate',
        ['Admin', 'Decisions', 'Portfolio', 'Journal', 'Public'],
    )
    st.sidebar.divider()
    st.sidebar.caption('Parthsarthi Capital')
    st.sidebar.caption('Educational research framework.')
    st.sidebar.caption('Not investment advice.')

    if tab == 'Admin':
        admin_panel()
    elif tab == 'Decisions':
        import view_decisions
        view_decisions.render()
    elif tab == 'Portfolio':
        import view_portfolio
        view_portfolio.render()
    elif tab == 'Journal':
        import view_journal
        view_journal.render()
    elif tab == 'Public':
        placeholder_tab('Public Dashboard', '6.6')


if __name__ == '__main__':
    main()
