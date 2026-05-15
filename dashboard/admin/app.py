"""
Engine A v2.1 Admin Dashboard - Step 9A (Read-Only)
====================================================
Streamlit app that reads data/core/engine_a_current.json and displays:
- Score + regime + equity % (hero card)
- 8 component breakdown with progress bars
- Sub-inputs table per component (expandable)
- Pending manual inputs (highlighted)
- Raw market data (auto-fetched)
- Auto-refresh

No write capability. That comes in Step 9B (manual input form).

Run locally:    streamlit run dashboard/admin/app.py
Deploy:         share.streamlit.io -> entry point: dashboard/admin/app.py

Author:         Engine A v2.1 build
Schema:         v2.1
"""

import json
from pathlib import Path

import streamlit as st
from streamlit_autorefresh import st_autorefresh


# =============================================================================
# CONFIG  (change constants here, nothing else)
# =============================================================================
REFRESH_INTERVAL_SEC = 300                     # 5 minutes. Change to 60 for 1-min.
JSON_RELATIVE_PATH = "data/core/engine_a_current.json"

# Map regime -> (display name, color, one-liner)
REGIME_INFO = {
    "FULL_DEPLOY": ("FULL DEPLOY", "#15803d", "Maximum allocation"),
    "AGGRESSIVE":  ("AGGRESSIVE",  "#65a30d", "Full deployment"),
    "ACTIVE":      ("ACTIVE",      "#ca8a04", "Normal deployment"),
    "CAUTIOUS":    ("CAUTIOUS",    "#c2410c", "Reduced size buys only"),
    "FREEZE":      ("FREEZE",      "#b91c1c", "No new equity buys"),
    "EXIT_ALL":    ("EXIT ALL",    "#7f1d1d", "Sell everything"),
}

# Map status -> color (used for sub-input border accent)
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
# This file is at dashboard/admin/app.py -- repo root is two parents up.
REPO_ROOT = Path(__file__).resolve().parents[2]
JSON_PATH = REPO_ROOT / JSON_RELATIVE_PATH


# =============================================================================
# DATA LOADING (no caching -- file read is cheap, always want fresh)
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
    """Top card -- score, regime, equity %, one-liner."""
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
            background: linear-gradient(135deg, {color}15 0%, {color}05 100%);
            border-left: 6px solid {color};
            padding: 22px 24px;
            border-radius: 12px;
            margin-bottom: 16px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.04);
        ">
            <div style="font-size: 12px; color: #525252; letter-spacing: 1.5px;
                        text-transform: uppercase; margin-bottom: 6px; font-weight: 600;">
                Engine A v2.1 &middot; Current State
            </div>
            <div style="font-size: 52px; font-weight: 700; color: #171717;
                        line-height: 1.1; margin: 6px 0;">
                {score}
                <span style="font-size: 24px; color: #737373; font-weight: 500;">
                    / {max_avail}
                </span>
            </div>
            <div style="font-size: 13px; color: #525252; margin-bottom: 14px;">
                {score_pct:.1f}% of max available today &middot;
                {max_avail}/{max_theory} pts unlocked
                ({max_theory - max_avail} pts blocked by pending inputs)
            </div>
            <div style="display: inline-block; background: {color}; color: white;
                        padding: 8px 16px; border-radius: 6px; font-weight: 700;
                        font-size: 14px; letter-spacing: 0.5px;">
                {regime_name} &middot; {equity_pct}% EQUITY
            </div>
            <div style="font-size: 13px; color: #525252; margin-top: 12px;
                        font-style: italic;">
                {tone}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_pending_banner(data):
    """Show pending-manual count prominently."""
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
    """One component card with progress bar + expandable sub-inputs."""
    name       = comp.get("name", comp_key)
    weight     = comp.get("weight", 0)
    score      = comp.get("score", 0) or 0
    max_avail  = comp.get("max_available", 0) or 0
    pct        = comp.get("pct_of_max_available", 0) or 0

    # Header
    if max_avail == 0:
        header_right = (
            f"<span style='color:#737373; font-size:13px'>"
            f"no live data yet</span>"
        )
        progress_value = 0.0
    else:
        header_right = (
            f"<strong>{score}</strong> "
            f"<span style='color:#737373'>/ {max_avail}</span> "
            f"<span style='color:#a3a3a3; font-size:12px'>({pct:.0f}%)</span>"
        )
        progress_value = min(pct / 100.0, 1.0)

    st.markdown(
        f"""
        <div style="display:flex; justify-content:space-between; align-items:baseline;
                    margin-top: 14px; margin-bottom: 6px;">
            <span style="font-weight:600; color:#171717;">
                {name}
                <span style="color:#a3a3a3; font-size:12px; font-weight:400;">
                    &middot; max {weight}
                </span>
            </span>
            <span style="font-size:14px;">{header_right}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.progress(progress_value)

    sub_inputs = comp.get("sub_inputs", {}) or {}
    with st.expander(f"Sub-inputs ({len(sub_inputs)})"):
        for sub_key, sub in sub_inputs.items():
            render_sub_input(sub_key, sub)


def render_sub_input(sub_key, sub):
    """One sub-input row with status badge + value + score + note."""
    status   = sub.get("status", "UNKNOWN")
    value    = sub.get("value")
    score    = sub.get("score")
    sub_max  = sub.get("max", 0)
    note     = sub.get("note", "") or ""

    color = STATUS_COLOR.get(status, "#525252")
    label = STATUS_LABEL.get(status, status)

    value_str = "—" if value is None else str(value)
    score_str = "—" if score is None else f"{score}/{sub_max}"

    st.markdown(
        f"""
        <div style="border-left: 3px solid {color};
                    padding: 10px 12px; margin: 8px 0;
                    background: #fafafa; border-radius: 4px;">
            <div style="display:flex; justify-content:space-between; align-items:center;">
                <span style="font-weight:600; color:#171717; font-size:14px;
                             font-family: ui-monospace, SFMono-Regular, Menlo, monospace;">
                    {sub_key}
                </span>
                <span style="font-size:10px; font-weight:700;
                             color: {color}; letter-spacing:1px;">
                    {label}
                </span>
            </div>
            <div style="font-size:13px; color:#525252; margin-top:4px;">
                value: <code>{value_str}</code> &middot;
                score: <code>{score_str}</code>
            </div>
            <div style="font-size:12px; color:#737373;
                        margin-top:2px; font-style:italic;">
                {note}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_raw_inputs(data):
    """Bottom expandable section -- auto-fetched market data."""
    raw = data.get("raw_inputs", {}) or {}
    if not raw:
        return

    with st.expander(f"Raw market data ({len(raw)} auto-fetched)"):
        rows = ""
        for key, val in raw.items():
            rows += (
                f"<div style='display:flex; justify-content:space-between;"
                f" padding: 6px 0; border-bottom: 1px solid #f5f5f5;'>"
                f"<span style='font-family: ui-monospace, monospace;"
                f" color:#525252; font-size:13px;'>{key}</span>"
                f"<span style='font-weight:600; color:#171717;'>{val}</span>"
                f"</div>"
            )
        st.markdown(rows, unsafe_allow_html=True)


# =============================================================================
# MAIN
# =============================================================================
def main():
    st.set_page_config(
        page_title="Engine A v2.1",
        layout="centered",          # mobile-first
        initial_sidebar_state="collapsed",
    )

    # Auto-refresh (re-runs whole script every N seconds)
    st_autorefresh(
        interval=REFRESH_INTERVAL_SEC * 1000,
        key="engine_a_autorefresh",
    )

    st.markdown("# Engine A v2.1")

    # Top bar: caption + refresh button
    top_l, top_r = st.columns([3, 1])
    with top_l:
        st.caption(
            f"Auto-refresh every {REFRESH_INTERVAL_SEC // 60} min. "
            f"Tap refresh for instant update."
        )
    with top_r:
        if st.button("Refresh", use_container_width=True):
            st.rerun()

    # Load data
    data, err = load_engine_a_data(JSON_PATH)
    if err or data is None:
        st.error("Could not load engine_a_current.json.")
        st.code(err or "unknown error")
        st.code(f"Expected at: {JSON_PATH}")
        st.stop()

    # Schema sanity
    schema_v = data.get("schema_version", "")
    computed_at = data.get("computed_at_ist", "unknown")
    if schema_v != "v2.1":
        st.warning(
            f"Unexpected schema version: '{schema_v}' "
            f"(dashboard built for v2.1)."
        )
    st.caption(f"Last compute: **{computed_at} IST** &middot; schema **{schema_v}**")

    # Hero
    render_hero(data)

    # Pending banner
    render_pending_banner(data)

    # Stale warning
    stale_count = data.get("stale_inputs_count", 0)
    if stale_count > 0:
        st.warning(f"{stale_count} sub-input(s) marked STALE. Check fetchers.")

    # 8 components
    st.markdown("### Components")
    components = data.get("components", {}) or {}
    for comp_key, comp in components.items():
        render_component(comp_key, comp)

    # Raw inputs
    st.markdown("---")
    render_raw_inputs(data)

    # Footer
    st.markdown("---")
    st.caption(
        "Engine A v2.1 &middot; Step 9A (read-only). "
        "Manual input form ships in Step 9B."
    )


if __name__ == "__main__":
    main()
