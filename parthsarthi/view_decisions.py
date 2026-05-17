"""
view_decisions.py
Parthsarthi Capital - Phase 6, Item 6.2
THE DASHBOARD - DECISION VIEW.

This tab is where the dashboard becomes useful. It runs the three
engine orchestrators on the uploaded screener CSVs and displays
every decision - verdict, conviction, and the full reason string.

It is a VIEW module: it reads from session state (set by the admin
panel, 6.1), calls the engine orchestrators, and renders the result.
The decision logic itself lives entirely in the engine modules.

This module is imported by app.py and exposes one function,
render(), which app.py calls when the Decisions tab is selected.
"""

import streamlit as st
import tempfile
import os

NAVY    = '#0A1628'
SAFFRON = '#D97706'

# verdict -> display colour, for the decision cards
VERDICT_COLOUR = {
    # buy-grade
    'STRIKE': '#16a34a', 'DEPLOY': '#16a34a', 'INCUBATE': '#16a34a',
    'INCUBATE-START': '#16a34a', 'ENTER-FREE-SLOT': '#16a34a',
    'Buy': '#16a34a', 'Watch': '#6B7280', 'Skip': '#9CA3AF',
    # hold / wait
    'HOLD': '#6B7280', 'STALK': '#6B7280', 'HOLD-FIRE': '#6B7280',
    'INCUBATE-HOLD': '#6B7280', 'WAIT-NO-ROOM': '#6B7280',
    'RIDE': '#16a34a', 'HELD': '#6B7280',
    # caution
    'GUARD': '#D97706', 'RE-RATING': '#D97706', 'SKIP': '#9CA3AF',
    'PASS': '#9CA3AF', 'ROTATE': '#D97706',
    # exits
    'EXIT': '#dc2626', 'EXIT-TRAIL': '#dc2626', 'EXIT-DEAD': '#dc2626',
    'INCUBATE-FAIL': '#dc2626', 'BOOK-THIRD': '#0891b2',
}


def _save_upload_to_temp(uploaded_file):
    """Write an uploaded file to a temp path so the engines can read it."""
    if uploaded_file is None:
        return None
    suffix = '.csv'
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    tmp.write(uploaded_file.getvalue())
    tmp.close()
    return tmp.name


def _run_engines():
    """
    Run the three engine orchestrators on the uploaded CSVs.
    Returns {engine: (report_text, decisions_list)} or an error dict.
    """
    from datetime import datetime
    results = {}
    score = st.session_state.get('engine_a_score', 55)

    # paths for the three uploaded screeners
    paths = {
        'B': _save_upload_to_temp(st.session_state.get('screener_b')),
        'C': _save_upload_to_temp(st.session_state.get('screener_c')),
        'D': _save_upload_to_temp(st.session_state.get('screener_d')),
    }

    try:
        if paths['B']:
            from engine_b import EngineB
            eng = EngineB(engine_a_score=score)
            report = eng.run_cycle(paths['B'],
                                   file_date=datetime.now().isoformat())
            results['B'] = (report, eng.decisions)
        if paths['C']:
            from engine_c import EngineC
            eng = EngineC(engine_a_score=score)
            report = eng.run_cycle(paths['C'],
                                   file_date=datetime.now().isoformat())
            results['C'] = (report, eng.decisions)
        if paths['D']:
            from engine_d import EngineD
            eng = EngineD(engine_a_score=score)
            report = eng.run_cycle(paths['D'],
                                   file_date=datetime.now().isoformat())
            results['D'] = (report, eng.decisions)
    finally:
        for p in paths.values():
            if p and os.path.exists(p):
                os.unlink(p)

    return results


def _decision_card(d):
    """Render one decision as a coloured card."""
    colour = VERDICT_COLOUR.get(d.verdict, NAVY)
    score_txt = ''
    if d.signals:
        score_txt = f" &middot; {d.total_score()}/{d.max_score()}"
    st.markdown(f"""
        <div style="border-left:4px solid {colour}; background:#fff;
                    padding:10px 14px; margin-bottom:8px; border-radius:4px;">
          <span style="font-weight:700; color:{NAVY};">{d.ticker}</span>
          <span style="color:{colour}; font-weight:700;">
            &nbsp;{d.verdict}{score_txt}</span>
          <div style="font-size:12px; color:#6B7280; margin-top:4px;">
            {d.rule}</div>
        </div>
    """, unsafe_allow_html=True)


def _audit_box(text):
    """
    Render an audit / reason string as a light, self-contained CARD
    with wrapping text - not a dark, horizontally-scrolling code block.

    The text keeps a monospace face (it is an auditable trace) but
    wraps to the card width, so it never runs off the side of a phone
    screen the way st.code() does.
    """
    safe = (str(text) if text is not None else '') \
        .replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
    st.markdown(
        f"<div style='background:#F1ECE0; border:1px solid #E5E0D5; "
        f"border-radius:6px; padding:10px 13px; margin:2px 0 12px 0; "
        f"font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace; "
        f"font-size:12px; line-height:1.55; color:#2A3340; "
        f"white-space:pre-wrap; word-break:break-word;'>{safe}</div>",
        unsafe_allow_html=True)


def render():
    """Render the Decisions tab. Called by app.py."""
    st.header('Decisions')

    uploaded = sum(1 for k in ['screener_b', 'screener_c', 'screener_d']
                   if st.session_state.get(k) is not None)
    if uploaded == 0:
        st.warning('No screeners uploaded. Go to the Admin tab and upload '
                   'the daily screener CSVs first.')
        return

    st.caption(f'{uploaded}/3 screeners loaded. '
               f'Engine A score: {st.session_state.get("engine_a_score", 55)}')

    if st.button('Run Engines & Show Decisions', type='primary'):
        with st.spinner('Running the engines...'):
            try:
                results = _run_engines()
                st.session_state['engine_results'] = results
            except Exception as e:
                st.error(f'Engine run failed: {e}')
                return

    results = st.session_state.get('engine_results')
    if not results:
        st.info('Click "Run Engines & Show Decisions" to generate decisions.')
        return

    # one expandable section per engine
    engine_titles = {'B': 'Engine B - Momentum',
                     'C': 'Engine C - Value',
                     'D': 'Engine D - Compounders'}
    for eng_code in ['B', 'C', 'D']:
        if eng_code not in results:
            continue
        report, decisions = results[eng_code]

        # verdict tally
        tally = {}
        for d in decisions:
            tally[d.verdict] = tally.get(d.verdict, 0) + 1
        tally_txt = ' &middot; '.join(f'{v}: {n}'
                                      for v, n in sorted(tally.items()))

        st.subheader(engine_titles[eng_code])
        st.caption(f'{len(decisions)} decisions | {tally_txt}')

        # buy-grade decisions first, then the rest
        buy_grade = {'Buy', 'STRIKE', 'DEPLOY', 'INCUBATE'}
        priority = [d for d in decisions if d.verdict in buy_grade]
        others = [d for d in decisions if d.verdict not in buy_grade]

        if priority:
            st.markdown('**Action decisions:**')
            for d in priority:
                _decision_card(d)
                # show the plain-English summary if present, else the
                # auditable reason string
                if getattr(d, 'summary', None):
                    st.markdown(
                        f"<div style='font-size:13px; color:#2A3340; "
                        f"padding:4px 12px 10px 12px;'>{d.summary}</div>",
                        unsafe_allow_html=True)
                    with st.expander('audit detail'):
                        _audit_box(d.reason_string())
                else:
                    with st.expander('reason string'):
                        _audit_box(d.reason_string())

        with st.expander(f'All {len(decisions)} decisions for '
                         f'{engine_titles[eng_code]}'):
            for d in others:
                _decision_card(d)

        with st.expander('Full engine cycle report'):
            st.code(report, language=None)

        st.divider()


# ---- self-test (structure check; full render needs the Streamlit runtime) ----
if __name__ == '__main__':
    import ast
    src = open(__file__).read()
    ast.parse(src)
    print('=' * 56)
    print('DECISION VIEW (6.2) - structure self-test')
    print('=' * 56)
    funcs = [n.name for n in ast.walk(ast.parse(src))
             if isinstance(n, ast.FunctionDef)]
    print('Functions defined:', funcs)
    print('render() present:', 'render' in funcs)
    print('Verdict colours mapped:', len(VERDICT_COLOUR))
    print('\nSyntax valid. Full visual render requires the Streamlit')
    print('runtime - verified live when the dashboard is deployed (6.7).')
    print('=' * 56)
