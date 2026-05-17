"""
app.py
Parthsarthi Capital - Dashboard (UI rebuild).

The entry point and router for the dashboard. This rebuild fixes the
earlier UI problems: faint "ghost" text, the unstyled red button, and
loose layout. Styling is done with strong, high-specificity CSS that
overrides Streamlit's defaults rather than fighting them.

Run locally:   streamlit run app.py
Deploy:        Streamlit Community Cloud, main file parthsarthi/app.py
"""

import streamlit as st
from datetime import datetime

# ---- Parthsarthi brand palette ----
NAVY    = '#0A1628'
CREAM   = '#FDFBF5'
SAFFRON = '#D97706'
INK     = '#2A3340'
GREEN   = '#16a34a'


def match_engine(filename):
    """
    Match an uploaded screener CSV to its engine by filename.
    Trendlyne exports keep distinctive prefixes:
      Mom...  -> Engine B (Momentum)
      C2...   -> Engine C (Value)
      D1...   -> Engine D (Compounders)
    Returns 'B', 'C', 'D', or None.
    """
    name = filename.lower()
    if name.startswith('mom') or 'momentum' in name:
        return 'B'
    if name.startswith('c2') or 'c2_value' in name or 'c2 value' in name:
        return 'C'
    if name.startswith('d1') or 'd1_compound' in name or 'd1 compound' in name:
        return 'D'
    return None


def setup_page():
    """Page config and the full brand stylesheet."""
    st.set_page_config(
        page_title='Parthsarthi Capital',
        page_icon='*',
        layout='centered',
        initial_sidebar_state='expanded',
    )

    # Strong, high-specificity CSS. Every rule uses !important so it
    # overrides Streamlit's default theme cleanly - this is what fixes
    # the faint text and the red button.
    st.markdown(f"""
        <style>
        /* ---- base canvas ---- */
        .stApp {{
            background-color: {CREAM} !important;
        }}
        .block-container {{
            padding-top: 2rem !important;
            padding-bottom: 3rem !important;
            max-width: 760px !important;
        }}

        /* ---- force ALL text to dark ink (kills the ghost text) ---- */
        .stApp, .stApp p, .stApp span, .stApp label, .stApp div,
        .stMarkdown, [data-testid="stMarkdownContainer"] {{
            color: {INK} !important;
        }}

        /* ---- headings - crisp navy ---- */
        .stApp h1, .stApp h2, .stApp h3, .stApp h4,
        [data-testid="stHeading"] {{
            color: {NAVY} !important;
            font-weight: 700 !important;
        }}
        .stApp h1 {{ font-size: 1.7rem !important; }}
        .stApp h2 {{ font-size: 1.3rem !important; margin-top: 0.5rem !important; }}
        .stApp h3 {{ font-size: 1.05rem !important; }}

        /* ---- all buttons - navy, no red ---- */
        .stButton > button {{
            background-color: {NAVY} !important;
            color: {CREAM} !important;
            border: none !important;
            border-radius: 8px !important;
            font-weight: 600 !important;
            padding: 0.55rem 1.4rem !important;
            width: 100% !important;
        }}
        .stButton > button:hover {{
            background-color: {SAFFRON} !important;
            color: {NAVY} !important;
        }}
        .stButton > button:active, .stButton > button:focus {{
            background-color: {SAFFRON} !important;
            color: {NAVY} !important;
            box-shadow: none !important;
        }}

        /* ---- inputs ---- */
        [data-testid="stNumberInput"] input,
        [data-testid="stTextInput"] input {{
            background-color: #FFFFFF !important;
            color: {NAVY} !important;
            border: 1px solid #E5E0D5 !important;
        }}

        /* ---- file uploader ---- */
        [data-testid="stFileUploader"] {{
            background-color: #FFFFFF !important;
            border: 1.5px dashed #C9C2B0 !important;
            border-radius: 10px !important;
            padding: 6px !important;
        }}
        [data-testid="stFileUploader"] section {{
            background-color: #FFFFFF !important;
        }}

        /* ---- expanders ---- */
        [data-testid="stExpander"] {{
            border: 1px solid #E5E0D5 !important;
            border-radius: 8px !important;
            background-color: #FFFFFF !important;
        }}

        /* ---- alert boxes (info / success / warning) ---- */
        [data-testid="stAlert"] {{
            border-radius: 8px !important;
        }}

        /* ---- sidebar ---- */
        [data-testid="stSidebar"] {{
            background-color: {NAVY} !important;
        }}
        [data-testid="stSidebar"] *, [data-testid="stSidebar"] label,
        [data-testid="stSidebar"] p, [data-testid="stSidebar"] span {{
            color: {CREAM} !important;
        }}

        /* ---- divider spacing ---- */
        hr {{ margin: 1.2rem 0 !important; border-color: #E5E0D5 !important; }}

        /* ---- brand header text - ID selectors beat the global rule ---- */
        #pc-brand-name {{ color: {CREAM} !important; }}
        #pc-brand-tag  {{ color: {SAFFRON} !important; }}

        /* ---- dataframe ---- */
        [data-testid="stDataFrame"] {{
            border: 1px solid #E5E0D5 !important;
            border-radius: 8px !important;
        }}
        </style>
    """, unsafe_allow_html=True)


def brand_header():
    """The navy brand block at the top of every page."""
    st.markdown(f"""
        <div style="background:{NAVY}; padding:22px 24px;
                    border-radius:12px; margin-bottom:22px;">
          <div id="pc-brand-name" style="font-size:23px;
                      font-weight:800; letter-spacing:0.5px;">
            PARTHSARTHI CAPITAL</div>
          <div id="pc-brand-tag" style="font-size:13px;
                      margin-top:3px; font-style:italic;">
            Your charioteer in Indian markets</div>
        </div>
    """, unsafe_allow_html=True)


def section_card(title, subtitle=None):
    """Render a consistent section heading."""
    sub = (f'<div style="font-size:12px; color:#6B7280; margin-top:2px;">'
           f'{subtitle}</div>') if subtitle else ''
    st.markdown(f"""
        <div style="margin:6px 0 10px 0;">
          <div style="font-size:15px; font-weight:700; color:{NAVY};">
            {title}</div>
          {sub}
        </div>
    """, unsafe_allow_html=True)


def init_state():
    """Initialise the session-state containers used across tabs."""
    defaults = {
        'screener_b': None, 'screener_c': None, 'screener_d': None,
        'engine_a_score': 55, 'total_portfolio': 1000000,
        'last_run': None, 'decisions': [], 'engine_results': None,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


def admin_panel():
    """The Admin tab - Engine A status (live), portfolio size, CSV upload."""
    st.header('Admin')
    st.caption('Engine A is read automatically from its scheduled run. '
               'Set the portfolio size, upload the screeners, then open '
               'the Decisions tab.')
    st.divider()

    # ---- 1. Engine A - read live, not typed ----
    section_card('1.  Engine A Regime',
                 'Read automatically from the latest scheduled run.')
    import engine_a_link
    a = engine_a_link.load_engine_a()
    st.session_state['engine_a_score'] = a['score']
    st.session_state['engine_a_data'] = a

    c1, c2, c3 = st.columns(3)
    c1.metric('Engine A score', f"{a['score']}/100")
    c2.metric('Regime', a['regime'])
    c3.metric('Operating gate', a['gate'])

    if a['available']:
        st.caption(f"Live - computed {a['computed_at']}. "
                   f"Equity allocation {a['equity_pct']}%.")
        if a['pending'] and a['pending'] > 0:
            st.warning(f"{a['pending']} manual input(s) pending in Engine A "
                       f"- the score is partial.")
    else:
        st.warning(a['note'])

    gate = a['gate']
    if gate == 'NORMAL':
        st.success(f'Operating gate: {gate} - entries and exits permitted.')
    elif gate == 'FREEZE':
        st.warning(f'Operating gate: {gate} - no new entries.')
    else:
        st.error(f'Operating gate: {gate} - close all equity positions.')

    st.divider()

    # ---- 2. Portfolio size ----
    section_card('2.  Portfolio Size',
                 'The total capital the engines allocate across B, C, D and E.')
    portfolio = st.number_input('Total portfolio (Rs)',
                                min_value=0,
                                value=st.session_state['total_portfolio'],
                                step=10000)
    st.session_state['total_portfolio'] = portfolio

    st.divider()

    # ---- 3. Screener upload ----
    section_card('3.  Upload Screener CSVs',
                 'Upload all three at once. Files are matched to engines '
                 'by name - keep the Mom / C2 / D1 prefixes.')

    files = st.file_uploader('Screener CSVs', type='csv',
                             accept_multiple_files=True,
                             key='upload_all', label_visibility='collapsed')

    if files:
        labels = {'B': 'Engine B - Momentum', 'C': 'Engine C - Value',
                  'D': 'Engine D - Compounders'}
        for f in files:
            eng = match_engine(f.name)
            if eng == 'B':
                st.session_state['screener_b'] = f
            elif eng == 'C':
                st.session_state['screener_c'] = f
            elif eng == 'D':
                st.session_state['screener_d'] = f
        st.write('')
        for f in files:
            eng = match_engine(f.name)
            if eng:
                st.success(f'{f.name}  ->  {labels[eng]}')
            else:
                st.error(f'{f.name}  ->  not matched. Rename to start '
                         f'with Mom, C2 or D1.')

    st.divider()

    # ---- 4. Status ----
    section_card('4.  Status')
    uploaded = sum(1 for k in ['screener_b', 'screener_c', 'screener_d']
                   if st.session_state[k] is not None)
    st.write(f'**{uploaded} of 3** screeners loaded.')
    if uploaded == 3:
        st.info('All screeners loaded. Open the **Decisions** tab and '
                'tap "Run Engines" to generate decisions.')
    elif uploaded > 0:
        st.info(f'{3 - uploaded} screener(s) still needed.')
    else:
        st.info('Upload the three screener CSVs above to begin.')


def engine_a_panel():
    """The Engine A tab - the macro regime score and its 8 components."""
    st.header('Engine A - Macro Regime')
    st.caption('The Director. Reads the macro picture and sets how much '
               'capital goes to equity. Updated on a schedule.')
    st.divider()

    import engine_a_link
    a = engine_a_link.load_engine_a()

    if not a['available']:
        st.warning(a['note'])
        return

    # headline
    c1, c2, c3 = st.columns(3)
    c1.metric('Score', f"{a['score']}/100")
    c2.metric('Regime', a['regime'])
    c3.metric('Equity allocation', f"{a['equity_pct']}%")
    st.caption(f"Computed {a['computed_at']}.  {a['guidance']}")

    st.divider()

    # the 8 components
    section_card('Component Breakdown',
                 'The eight macro components behind the score.')
    comps = a['components']
    if comps:
        rows = []
        for key, c in comps.items():
            rows.append({
                'Component': c.get('name', key),
                'Score': f"{c.get('score', 0)} / {c.get('weight', 0)}",
                'Strength': f"{c.get('pct_of_max_available', 0):.0f}%",
            })
        st.dataframe(rows, use_container_width=True, hide_index=True)
        st.caption('Each component contributes to the 0-100 score. '
                   'Strength shows how much of that component was earned.')
    else:
        st.info('Component detail not available in the current data.')


def main():
    setup_page()
    init_state()
    brand_header()

    tab = st.sidebar.radio('Navigate',
                           ['Admin', 'Engine A', 'Engine A Inputs',
                            'Decisions', 'Portfolio', 'Journal', 'Public'])
    st.sidebar.divider()
    st.sidebar.caption('Parthsarthi Capital')
    st.sidebar.caption('Educational research framework.')
    st.sidebar.caption('Not investment advice.')

    if tab == 'Admin':
        admin_panel()
    elif tab == 'Engine A':
        engine_a_panel()
    elif tab == 'Engine A Inputs':
        import view_engine_a_inputs
        view_engine_a_inputs.render()
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
        import view_public
        view_public.render()


if __name__ == '__main__':
    main()
