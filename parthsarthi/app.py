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
import os
import tempfile
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


# ---------------------------------------------------------------
#  SCREENER PERSISTENCE - survive a browser refresh
# ---------------------------------------------------------------
# st.session_state is wiped on every browser refresh, so an uploaded
# screener would be lost and need re-uploading. We mirror each uploaded
# CSV to a cache folder on disk; on load we restore from it. The cache
# stays until the user uploads a replacement or taps "Clear screeners".
#
# Scope of this fix: it survives a browser refresh and short idle -
# exactly the reported problem. It does NOT survive the Streamlit app
# fully sleeping (Streamlit Cloud wipes local disk after long
# inactivity); permanent storage would need a repo-backed cache.

_CACHE_DIR = os.path.join(tempfile.gettempdir(), 'parthsarthi_screener_cache')
_ENGINES = ['B', 'C', 'D']


class _CachedScreener:
    """
    A screener restored from the disk cache. It behaves like a Streamlit
    UploadedFile for the only two things the rest of the app needs:
    .name and .getvalue(). match_engine() and the engine orchestrators
    therefore work with it unchanged - no other file needs editing.
    """

    def __init__(self, name, data):
        self.name = name
        self._data = data

    def getvalue(self):
        return self._data


def _cache_paths(engine):
    """(csv_path, name_path) for one engine's cached screener."""
    return (os.path.join(_CACHE_DIR, f'screener_{engine}.csv'),
            os.path.join(_CACHE_DIR, f'screener_{engine}.name'))


def cache_screener(engine, uploaded_file):
    """Mirror an uploaded screener to disk so it survives a refresh."""
    try:
        os.makedirs(_CACHE_DIR, exist_ok=True)
        csv_path, name_path = _cache_paths(engine)
        with open(csv_path, 'wb') as f:
            f.write(uploaded_file.getvalue())
        with open(name_path, 'w', encoding='utf-8') as f:
            f.write(getattr(uploaded_file, 'name', f'screener_{engine}.csv'))
    except OSError:
        pass   # caching is best-effort - never break an upload over it


def load_cached_screener(engine):
    """Return a _CachedScreener restored from disk, or None if none cached."""
    csv_path, name_path = _cache_paths(engine)
    if not os.path.exists(csv_path):
        return None
    try:
        with open(csv_path, 'rb') as f:
            data = f.read()
        name = f'screener_{engine}.csv'
        if os.path.exists(name_path):
            with open(name_path, 'r', encoding='utf-8') as nf:
                name = nf.read().strip() or name
        return _CachedScreener(name, data)
    except OSError:
        return None


def clear_cached_screeners():
    """Delete every cached screener - the 'upload fresh ones' action."""
    for engine in _ENGINES:
        for path in _cache_paths(engine):
            try:
                if os.path.exists(path):
                    os.remove(path)
            except OSError:
                pass


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
        /* The global dark-text rule above ALSO matches the <p>/<div>/<span>
           that Streamlit wraps the button LABEL in, making the label
           dark-on-dark (invisible). These rules use higher specificity
           (.stApp .stButton button *) to force the label - and every
           child element - to the right colour. */
        .stApp .stButton button {{
            background-color: {NAVY} !important;
            border: none !important;
            border-radius: 8px !important;
            font-weight: 600 !important;
            padding: 0.55rem 1.4rem !important;
            width: 100% !important;
        }}
        .stApp .stButton button,
        .stApp .stButton button * {{
            color: {CREAM} !important;
        }}
        .stApp .stButton button:hover {{
            background-color: {SAFFRON} !important;
        }}
        .stApp .stButton button:hover,
        .stApp .stButton button:hover * {{
            color: {NAVY} !important;
        }}
        .stApp .stButton button:active,
        .stApp .stButton button:focus {{
            background-color: {SAFFRON} !important;
            box-shadow: none !important;
        }}
        .stApp .stButton button:active,
        .stApp .stButton button:active *,
        .stApp .stButton button:focus,
        .stApp .stButton button:focus * {{
            color: {NAVY} !important;
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
        /* the uploader's own "Browse files" button is not a .stButton,
           so the rules above miss it - give it a clear light style */
        .stApp [data-testid="stFileUploader"] button {{
            background-color: #FFFFFF !important;
            border: 1px solid #C9C2B0 !important;
        }}
        .stApp [data-testid="stFileUploader"] button,
        .stApp [data-testid="stFileUploader"] button * {{
            color: {NAVY} !important;
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
        'uploader_gen': 0,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

    # Restore screeners cached on disk. A browser refresh wipes
    # st.session_state, so without this the three CSVs would be lost
    # and need re-uploading every time. The cache is rebuilt on upload
    # and cleared by the "Clear all screeners" button.
    for engine in _ENGINES:
        key = f'screener_{engine.lower()}'
        if st.session_state.get(key) is None:
            cached = load_cached_screener(engine)
            if cached is not None:
                st.session_state[key] = cached


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
                 'by name - keep the Mom / C2 / D1 prefixes. Uploads are '
                 'kept across a browser refresh until you clear them.')

    # The uploader key carries a generation counter so the "Clear all
    # screeners" button can force a fresh, empty uploader widget.
    up_key = f'upload_all_{st.session_state.get("uploader_gen", 0)}'
    files = st.file_uploader('Screener CSVs', type='csv',
                             accept_multiple_files=True,
                             key=up_key, label_visibility='collapsed')

    if files:
        labels = {'B': 'Engine B - Momentum', 'C': 'Engine C - Value',
                  'D': 'Engine D - Compounders'}
        for f in files:
            eng = match_engine(f.name)
            if eng in _ENGINES:
                st.session_state[f'screener_{eng.lower()}'] = f
                cache_screener(eng, f)        # mirror to disk - survives refresh
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
    loaded = []
    for eng in _ENGINES:
        sc = st.session_state.get(f'screener_{eng.lower()}')
        if sc is not None:
            loaded.append((eng, getattr(sc, 'name', f'screener_{eng}.csv')))

    st.write(f'**{len(loaded)} of 3** screeners loaded.')
    for eng, name in loaded:
        st.caption(f'Engine {eng}:  {name}')

    if len(loaded) == 3:
        st.info('All screeners loaded. Open the **Decisions** tab and '
                'tap "Run Engines" to generate decisions.')
    elif loaded:
        st.info(f'{3 - len(loaded)} screener(s) still needed.')
    else:
        st.info('Upload the three screener CSVs above to begin.')

    if loaded:
        st.write('')
        if st.button('Clear all screeners'):
            clear_cached_screeners()
            for eng in _ENGINES:
                st.session_state[f'screener_{eng.lower()}'] = None
            # bump the uploader generation so its widget resets to empty
            st.session_state['uploader_gen'] = \
                st.session_state.get('uploader_gen', 0) + 1
            st.rerun()


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
