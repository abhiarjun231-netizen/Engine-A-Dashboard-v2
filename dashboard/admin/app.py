"""
Engine A v2.1 Admin Dashboard - Step 9A (Read-Only) - v2 theme-agnostic
========================================================================
Theme-agnostic update:
- Hero card and sub-input cards are SELF-CONTAINED with explicit
  background + text colors (white bg + dark text). Readable regardless
  of whether Streamlit Cloud renders light or dark theme.
- Component headers and captions use Streamlit native markdown so they
  adapt to whichever theme is active.
- No reliance on .streamlit/config.toml theme override.

Run locally:    streamlit run dashboard/admin/app.py
Deploy:         share.streamlit.io -> entry point: dashboard/admin/app.py
"""

import json
from pathlib import Path

import streamlit as st
from streamlit_autorefresh import st_autorefresh


# =============================================================================
# CONFIG
# =============================================================================
REFRESH_INTERVAL_SEC = 300                     # 5 minutes
JSON_RELATIVE_PATH = "data/core/engine_a_current.json"

REGIME_INFO = {
    "FULL_DEPLOY": ("FULL DEPLOY", "#15803d", "Maximum allocation"),
    "AGGRESSIVE":  ("AGGRESSIVE",  "#65a30d", "Full deployment"),
    "ACTIVE":      ("ACTIVE",      "#ca8a04", "Normal deployment"),
    "CAUTIOUS":    ("CAUTIOUS",    "#c2410c", "Reduced size buys only"),
    "FREEZE":      ("FREEZE",      "#b91c1c", "No new equity buys"),
    "EXIT_ALL":    ("EXIT ALL",    "#7f1d1d", "Sell everything"),
}

STATUS_COLOR = {
    "OK":             "#15803d",
    "PENDING_MANUAL": "#737373",
    "STALE":          "#ca8a04",
    "ERROR":          "#b91c1c",
}

STATUS_LABEL = {
    "OK":             "OK",
    "PENDING_MANUAL": "MANUAL",
    "STALE":          "STALE",
    "ERROR":          "ERROR",
}


# =============================================================================
# PATHS
# =============================================================================
REPO_ROOT = Path(__file__).resolve().parents[2]
JSON_PATH = REPO_ROOT / JSON_RELATIVE_PATH


# =============================================================================
# DATA LOADING
# =============================================================================
def load_engine_a_data(path):
    """Return (data_dict, error_string).  Either data or error will be None."""
    try:
        if not path.exists():
            return None, f"File not found: {path}"
        with path.open("r", encoding="utf-8") as f:
            return json.load(f), None
    except json.JSONDecodeError as e:
        return None, f"JSON parse error: {e}"
    except OSError as e:
        return None, f"File read error: {e}"


# =============================================================================
# RENDER HELPERS
# =============================================================================
def render_hero(data):
    """Self-contained white card -- score, regime, equity %, one-liner.
    Explicit bg + text colors so it renders correctly in any theme."""
    score        = data.get("score", 0)
    max_avail    = data.get("max_available_today", 0)
    max_theory   = data.get("max_theoretical", 100)
    score_pct    = data.get("score_pct_of_max_available", 0) or 0
    regime       = data.get("regime", "UNKNOWN")
    equity_pct   = data.get("regime_equity_pct", 0)

    regime_name, color, tone = REGIME_INFO.get(
        regime, (regime, "#525252", "")
    )

    st.markdown(
        f"""
        <div style="
            background: #ffffff;
            border: 1px solid #e5e5e5;
            border-left: 6px solid {color};
            padding: 22px 24px;
            border-radius: 12px;
            margin-bottom: 16px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.06);
        ">
            <div style="color: #525252; font-size: 12px; letter-spacing: 1.5px;
                        text-transform: uppercase; margin-bottom: 6px; font-weight: 600;">
                Engine A v2.1 &middot; Current State
            </div>
            <div style="color: #171717; font-size: 52px; font-weight: 700;
                        line-height: 1.1; margin: 6px 0;">
                {score}
                <span style="color: #737373; font-size: 24px; font-weight: 500;">
                    / {max_avail}
                </span>
            </div>
            <div style="color: #525252; font-size: 13px; margin-bottom: 14px;">
                {score_pct:.1f}% of max available today &middot;
                {max_avail}/{max_theory} pts unlocked
                ({max_theory - max_avail} pts blocked by pending inputs)
            </div>
            <div style="display: inline-block; background: {color}; color: #ffffff;
                        padding: 8px 16px; border-radius: 6px; font-weight: 700;
                        font-size: 14px; letter-spacing: 0.5px;">
                {regime_name} &middot; {equity_pct}% EQUITY
            </div>
            <div style="color: #525252; font-size: 13px; margin-top: 12px;
                        font-style: italic;">
                {tone}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_pending_banner(data):
    """Native warning -- adapts to theme automatically."""
    pending = data.get("pending_manual", []) or []
    count = data.get("pending_manual_count", len(pending))

    if count == 0:
        st.success("All sub-inputs filled. No pending manuals.")
        return

    st.warning(
        f"**{count} sub-inputs pending manual entry.** "
        f"Score is being computed on partial data. "
        f"Manual input form ships in Step 9B."
    )

    with st.expander(f"Show pending list ({count})"):
        for p in pending:
            st.markdown(f"- `{p}`")


def render_component(comp_key, comp):
    """Native theme-aware header + native progress + custom expander cards.
    No custom-HTML text outside the explicitly-styled sub-input cards."""
    name       = comp.get("name", comp_key)
    weight     = comp.get("weight", 0)
    score      = comp.get("score", 0) or 0
    max_avail  = comp.get("max_available", 0) or 0
    pct        = comp.get("pct_of_max_available", 0) or 0

    # Header: native markdown (theme-aware)
    c1, c2 = st.columns([2, 1])
    with c1:
        st.markdown(f"**{name}**  \u00b7  max {weight}")
    with c2:
        if max_avail == 0:
            st.markdown(
                "<div style='text-align:right; opacity:0.6;'>no live data yet</div>",
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                f"<div style='text-align:right;'><b>{score}</b> / {max_avail} "
                f"<span style='opacity:0.6;'>({pct:.0f}%)</span></div>",
                unsafe_allow_html=True,
            )

    progress_value = min(pct / 100.0, 1.0) if max_avail > 0 else 0.0
    st.progress(progress_value)

    sub_inputs = comp.get("sub_inputs", {}) or {}
    with st.expander(f"Sub-inputs ({len(sub_inputs)})"):
        for sub_key, sub in sub_inputs.items():
            render_sub_input(sub_key, sub)


def render_sub_input(sub_key, sub):
    """Self-contained sub-input card -- light gray bg + explicit dark text.
    Readable on any parent theme."""
    status   = sub.get("status", "UNKNOWN")
    value    = sub.get("value")
    score    = sub.get("score")
    sub_max  = sub.get("max", 0)
    note     = sub.get("note", "") or ""

    color = STATUS_COLOR.get(status, "#525252")
    label = STATUS_LABEL.get(status, status)

    value_str = "\u2014" if value is None else str(value)
    score_str = "\u2014" if score is None else f"{score}/{sub_max}"

    st.markdown(
        f"""
        <div style="background: #f5f5f5;
                    border-left: 3px solid {color};
                    padding: 10px 12px; margin: 8px 0;
                    border-radius: 4px;">
            <div style="display:flex; justify-content:space-between; align-items:center;">
                <span style="color:#171717; font-weight:600; font-size:14px;
                             font-family: ui-monospace, SFMono-Regular, Menlo, monospace;">
                    {sub_key}
                </span>
                <span style="color: {color}; font-size:10px; font-weight:700;
                             letter-spacing:1px;">
                    {label}
                </span>
            </div>
            <div style="color:#525252; font-size:13px; margin-top:4px;">
                value:
                <code style="color:#171717; background:#ffffff;
                             padding:1px 5px; border-radius:3px;
                             border:1px solid #e5e5e5;">{value_str}</code>
                &middot; score:
                <code style="color:#171717; background:#ffffff;
                             padding:1px 5px; border-radius:3px;
                             border:1px solid #e5e5e5;">{score_str}</code>
            </div>
            <div style="color:#737373; font-size:12px; margin-top:4px;
                        font-style:italic;">
                {note}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_raw_inputs(data):
    """Native theme-aware key/value list."""
    raw = data.get("raw_inputs", {}) or {}
    if not raw:
        return

    with st.expander(f"Raw market data ({len(raw)} auto-fetched)"):
        for key, val in raw.items():
            c1, c2 = st.columns([2, 1])
            with c1:
                st.markdown(f"`{key}`")
            with c2:
                st.markdown(
                    f"<div style='text-align:right;'><b>{val}</b></div>",
                    unsafe_allow_html=True,
                )


# =============================================================================
# MAIN
# =============================================================================
def main():
    st.set_page_config(
        page_title="Engine A v2.1",
        layout="centered",
        initial_sidebar_state="collapsed",
    )

    st_autorefresh(
        interval=REFRESH_INTERVAL_SEC * 1000,
        key="engine_a_autorefresh",
    )

    st.markdown("# Engine A v2.1")

    top_l, top_r = st.columns([3, 1])
    with top_l:
        st.caption(
            f"Auto-refresh every {REFRESH_INTERVAL_SEC // 60} min. "
            f"Tap refresh for instant update."
        )
    with top_r:
        if st.button("Refresh", use_container_width=True):
            st.rerun()

    data, err = load_engine_a_data(JSON_PATH)
    if err or data is None:
        st.error("Could not load engine_a_current.json.")
        st.code(err or "unknown error")
        st.code(f"Expected at: {JSON_PATH}")
        st.stop()

    schema_v = data.get("schema_version", "")
    computed_at = data.get("computed_at_ist", "unknown")
    if schema_v != "v2.1":
        st.warning(
            f"Unexpected schema version: '{schema_v}' "
            f"(dashboard built for v2.1)."
        )
    st.caption(f"Last compute: **{computed_at} IST** \u00b7 schema **{schema_v}**")

    render_hero(data)
    render_pending_banner(data)

    stale_count = data.get("stale_inputs_count", 0)
    if stale_count > 0:
        st.warning(f"{stale_count} sub-input(s) marked STALE. Check fetchers.")

    st.markdown("### Components")
    components = data.get("components", {}) or {}
    for comp_key, comp in components.items():
        render_component(comp_key, comp)

    st.markdown("---")
    render_raw_inputs(data)

    st.markdown("---")
    st.caption(
        "Engine A v2.1 \u00b7 Step 9A (read-only). "
        "Manual input form ships in Step 9B."
    )


if __name__ == "__main__":
    main()
