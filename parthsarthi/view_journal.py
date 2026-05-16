"""
view_journal.py
Parthsarthi Capital - Phase 6, Item 6.4
THE DASHBOARD - JOURNAL VIEW.

This tab shows the system's memory: the daily screen-diff history.
Each day a screener is uploaded, the journal records what ENTERED
the screen, what LEFT it, and what STAYED. Over time this is the
record the AI pattern layer (6.5) studies and the audit trail an
RIA review would inspect.

It surfaces the journal module built in Phase 1 (item 1.1) and the
state-transition log from the state model (item 1.2).

It is a VIEW module: it reads the stored journal and renders it.
It exposes render(), called by app.py.
"""

import streamlit as st
import json
import os

NAVY    = '#0A1628'
GREEN   = '#16a34a'
RED     = '#dc2626'
GREY    = '#6B7280'


def _load_journal():
    """
    Load the screen-diff journal if it exists.
    The journal module (1.1) writes a JSON file per engine.
    Returns a list of journal entries, newest first, or [].
    """
    entries = []
    for fname in ['engine_b_journal.json', 'engine_c_journal.json',
                   'engine_d_journal.json', 'journal.json']:
        if os.path.exists(fname):
            try:
                with open(fname) as f:
                    data = json.load(f)
                if isinstance(data, list):
                    entries.extend(data)
                elif isinstance(data, dict) and 'entries' in data:
                    entries.extend(data['entries'])
            except (json.JSONDecodeError, ValueError):
                continue
    return entries


def _load_transitions():
    """
    Load the state-transition log from the state model (1.2).
    Returns a list of transition records, or [].
    """
    log = []
    for fname in ['state_b.json', 'state_c.json', 'state_d.json']:
        if os.path.exists(fname):
            try:
                with open(fname) as f:
                    data = json.load(f)
                log.extend(data.get('log', []))
            except (json.JSONDecodeError, ValueError):
                continue
    # newest first
    log.sort(key=lambda e: e.get('timestamp', ''), reverse=True)
    return log


def _screen_diff_section():
    """Section 1 - the daily screen-diff (entered / left / stayed)."""
    st.subheader('1. Daily Screen-Diff')
    entries = _load_journal()

    if not entries:
        st.info('No journal entries yet. The screen-diff is recorded each '
                'time a screener is uploaded and a cycle runs. Run a few '
                'daily cycles and the history builds here.')
        return

    st.caption(f'{len(entries)} journal entr(ies) recorded.')
    # show the most recent entries
    for e in entries[-10:][::-1]:
        date = e.get('date', e.get('timestamp', 'unknown date'))
        entered = e.get('entered', [])
        left = e.get('left', [])
        stayed = e.get('stayed', [])
        with st.expander(f"{date}  -  "
                         f"+{len(entered)} entered, "
                         f"-{len(left)} left, "
                         f"{len(stayed)} stayed"):
            c1, c2, c3 = st.columns(3)
            with c1:
                st.markdown(f"<b style='color:{GREEN}'>Entered</b>",
                            unsafe_allow_html=True)
                for tk in entered:
                    st.write(tk)
            with c2:
                st.markdown(f"<b style='color:{RED}'>Left</b>",
                            unsafe_allow_html=True)
                for tk in left:
                    st.write(tk)
            with c3:
                st.markdown(f"<b style='color:{GREY}'>Stayed</b>",
                            unsafe_allow_html=True)
                st.caption(f'{len(stayed)} stocks')


def _transitions_section():
    """Section 2 - the state-transition audit log."""
    st.subheader('2. State-Transition Log')
    log = _load_transitions()

    if not log:
        st.info('No state transitions recorded yet. Every move a stock '
                'makes between states (NEW / WATCH / HELD / DETERIORATING '
                '/ EXITED) is logged here with its reason - the audit '
                'trail.')
        return

    st.caption(f'{len(log)} state transitions recorded (newest first).')
    rows = []
    for e in log[:50]:
        rows.append({
            'When': e.get('timestamp', ''),
            'Engine': e.get('engine', ''),
            'Ticker': e.get('ticker', ''),
            'Transition': f"{e.get('from') or 'start'} -> {e.get('to', '')}",
            'Reason': e.get('reason', ''),
        })
    st.dataframe(rows, use_container_width=True, hide_index=True)


def _why_it_matters():
    """A short note on why the journal exists."""
    with st.expander('Why the journal matters'):
        st.markdown(
            'The journal is the system\'s memory. Without it, the engines '
            'are screeners with extra steps. With it:\n\n'
            '- Churn handling can see how often a stock has appeared\n'
            '- The CHURNER flag can count appearances over 90 days\n'
            '- The AI pattern layer (built next, 6.5) has a record to '
            'study - what booking levels worked, what exits were timed '
            'well\n'
            '- An RIA review has a complete, dated audit trail\n\n'
            'The journal is the prerequisite for the system learning '
            'from its own history.')


def render():
    """Render the Journal tab. Called by app.py."""
    st.header('Journal')
    st.caption('The system\'s memory - the daily screen-diff and the '
               'state-transition audit trail.')

    _screen_diff_section()
    st.divider()
    _transitions_section()
    st.divider()
    _why_it_matters()


# ---- self-test (structure check) ----
if __name__ == '__main__':
    import ast
    src = open(__file__).read()
    ast.parse(src)
    print('=' * 56)
    print('JOURNAL VIEW (6.4) - structure self-test')
    print('=' * 56)
    funcs = [n.name for n in ast.walk(ast.parse(src))
             if isinstance(n, ast.FunctionDef)]
    print('Functions defined:', funcs)
    print('render() present:', 'render' in funcs)
    print('\nSyntax valid. Full visual render requires the Streamlit')
    print('runtime - verified live when the dashboard is deployed (6.7).')
    print('=' * 56)
