"""
view_public.py
Parthsarthi Capital - Phase 6, Item 6.6
THE DASHBOARD - PUBLIC VIEW.

This tab is the face of the system - what someone OTHER than the
operator sees. It is read-only: no uploads, no admin controls, no
run buttons. It presents the portfolio's current state and recent
activity, cleanly and professionally.

Sections:
  1. Hero - the brand, the regime, the headline numbers
  2. Allocation - the equity split and exposure, visually
  3. Recent activity - the latest buy / exit decisions, narrated
                        in plain English (via ai_narration, 6.5)
  4. Disclosure - the honest standing of the system

It is a VIEW module: it reads state and stored data and renders.
It exposes render(), called by app.py. It never writes anything.
"""

import streamlit as st

NAVY    = '#0A1628'
CREAM   = '#FDFBF5'
SAFFRON = '#D97706'
GREEN   = '#16a34a'
GREY    = '#6B7280'


def _hero():
    """Section 1 - the branded hero block with headline numbers."""
    score = st.session_state.get('engine_a_score', 55)
    portfolio = st.session_state.get('total_portfolio', 1000000)

    try:
        from portfolio_capital import regime_for_score
        from portfolio_engine_a import operating_gate
        regime, fraction = regime_for_score(score)
        gate = operating_gate(score)
    except Exception:
        regime, fraction, gate = 'Unknown', 0.0, 'NORMAL'

    st.markdown(f"""
        <div style="background:{NAVY}; color:{CREAM}; padding:28px 26px;
                    border-radius:10px; margin-bottom:18px;">
          <div style="font-size:13px; color:{SAFFRON};
                      letter-spacing:1px;">PARTHSARTHI CAPITAL</div>
          <div style="font-size:30px; font-weight:700; margin-top:4px;">
            The {regime} Regime</div>
          <div style="font-size:14px; color:#9CA3AF; margin-top:8px;">
            A systematic investment framework for Indian equity,
            debt and gold markets.</div>
        </div>
    """, unsafe_allow_html=True)

    c1, c2, c3 = st.columns(3)
    c1.metric('Engine A score', f'{score}/100')
    c2.metric('Target equity', f'{fraction*100:.0f}%')
    c3.metric('Operating gate', gate)


def _allocation():
    """Section 2 - the equity allocation, presented cleanly."""
    st.subheader('Allocation')
    score = st.session_state.get('engine_a_score', 55)
    portfolio = st.session_state.get('total_portfolio', 1000000)

    try:
        from portfolio_capital import allocate
        a = allocate(portfolio, score)
    except Exception as e:
        st.caption(f'Allocation unavailable: {e}')
        return

    eb = a['engine_budgets']
    st.markdown(
        f"Of the total book, **{a['equity_fraction']*100:.0f}%** is "
        f"allocated to equity and the rest to debt and gold (Engine E). "
        f"The equity slice is split across three engines:")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric('Momentum (B)', f"{eb['B']/a['equity_budget']*100:.0f}%"
              if a['equity_budget'] else '30%')
    c2.metric('Value (C)', f"{eb['C']/a['equity_budget']*100:.0f}%"
              if a['equity_budget'] else '30%')
    c3.metric('Compounders (D)', f"{eb['D']/a['equity_budget']*100:.0f}%"
              if a['equity_budget'] else '40%')
    c4.metric('Debt + Gold (E)',
              f"{a['non_equity']/(a['equity_budget']+a['non_equity'])*100:.0f}%"
              if (a['equity_budget']+a['non_equity']) else '-')


def _recent_activity():
    """Section 3 - the latest decisions, narrated in plain English."""
    st.subheader('Recent Activity')

    results = st.session_state.get('engine_results')
    if not results:
        st.info('No recent cycle has been run. Recent buy and exit '
                'decisions appear here once the engines have run.')
        return

    try:
        from ai_narration import narrate_cycle, cycle_summary
    except Exception as e:
        st.caption(f'Narration unavailable: {e}')
        return

    # gather all decisions across the engines
    all_decisions = []
    for eng_code, (_, decisions) in results.items():
        all_decisions.extend(decisions)

    # the one-paragraph summary
    st.markdown(f"*{cycle_summary(all_decisions)}*")

    # the action decisions, narrated
    buy_grade = {'STRIKE', 'DEPLOY', 'INCUBATE', 'INCUBATE-START'}
    exit_grade = {'EXIT', 'EXIT-TRAIL', 'EXIT-DEAD', 'INCUBATE-FAIL'}
    action = [d for d in all_decisions
              if d.verdict in buy_grade or d.verdict in exit_grade]

    if not action:
        st.caption('No buy or exit actions in the latest cycle - '
                   'a hold-steady day.')
        return

    for tk, verdict, text in narrate_cycle(action, max_items=12):
        colour = GREEN if verdict in buy_grade else '#dc2626'
        st.markdown(f"""
            <div style="border-left:3px solid {colour}; background:#fff;
                        padding:8px 12px; margin-bottom:6px;
                        border-radius:4px; font-size:13px;">
              {text}
            </div>
        """, unsafe_allow_html=True)


def _disclosure():
    """Section 4 - the honest standing of the system."""
    st.divider()
    st.caption(
        'Parthsarthi Capital is an educational research framework. '
        'It is not investment advice, not a SEBI-registered service, '
        'and is in a paper-trading validation phase. Markets carry '
        'risk of capital loss. Every decision shown is generated by '
        'deterministic rules and is fully auditable.')


def render():
    """Render the Public dashboard tab. Called by app.py."""
    _hero()
    _allocation()
    st.divider()
    _recent_activity()
    _disclosure()


# ---- self-test (structure check) ----
if __name__ == '__main__':
    import ast
    src = open(__file__).read()
    ast.parse(src)
    print('=' * 56)
    print('PUBLIC VIEW (6.6) - structure self-test')
    print('=' * 56)
    funcs = [n.name for n in ast.walk(ast.parse(src))
             if isinstance(n, ast.FunctionDef)]
    print('Functions defined:', funcs)
    print('render() present:', 'render' in funcs)
    # read-only check: count actual UI-write calls, excluding this
    # self-test block (which mentions the call names as search strings)
    render_src = src.split("# ---- self-test")[0]
    has_upload = 'file_uploader(' in render_src
    has_button = '.button(' in render_src
    print('Read-only (no upload/button calls in render code):',
          not has_upload and not has_button)
    print('\nSyntax valid. Full visual render requires the Streamlit')
    print('runtime - verified live when the dashboard is deployed (6.7).')
    print('=' * 56)
