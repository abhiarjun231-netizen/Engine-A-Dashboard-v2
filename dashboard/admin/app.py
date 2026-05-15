"""
Engine A v2.1 Admin Dashboard — Step 9A + 9B
=============================================
Two tabs:
  1) Dashboard (read-only) — reads engine_a_current.json, renders score + components
  2) Admin / Manual Inputs — password-gated form for 13 Tier 4 sub-inputs,
     commits manual_inputs.csv to GitHub via Contents API.

The cron workflow picks up the new CSV on the next run and recomputes the
Engine A score. No editing of fetcher code, no script triggers.

Streamlit Cloud secrets required:
  - ADMIN_PASSWORD  : password for the Admin tab
  - GH_PAT          : fine-grained PAT with Contents:write on this repo

Run locally:    streamlit run dashboard/admin/app.py
Deploy:         share.streamlit.io
"""

import hmac
import json
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st
from streamlit_autorefresh import st_autorefresh

# Make sibling module github_io.py importable when run via `streamlit run`
sys.path.insert(0, str(Path(__file__).resolve().parent))
from github_io import commit_file_to_repo  # noqa: E402


# =============================================================================
# CONFIG
# =============================================================================
REFRESH_INTERVAL_SEC = 300
JSON_RELATIVE_PATH = "data/core/engine_a_current.json"
MANUAL_CSV_RELATIVE = "data/core/manual_inputs.csv"

GITHUB_OWNER = "abhiarjun231-netizen"
GITHUB_REPO = "Engine-A-Dashboard-v2"
GITHUB_BRANCH = "main"

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
MANUAL_CSV_PATH = REPO_ROOT / MANUAL_CSV_RELATIVE


# =============================================================================
# MANUAL INPUT FIELD DEFINITIONS
# =============================================================================
# 13 fields. Each definition drives form rendering AND is the contract with
# the compute layer (matching field names in calculate_engine_a_v21.py 9C).
MANUAL_FIELDS = [
    {
        "key": "nifty_pe_ttm",
        "label": "Nifty 50 PE (TTM)",
        "type": "number",
        "min": 5.0, "max": 50.0, "step": 0.1, "default": 22.0,
        "help": "From Trendlyne. Feeds Yield Gap calc.",
        "cadence": "Monthly",
    },
    {
        "key": "nifty_pe_pctile",
        "label": "Nifty PE Percentile (10Y, %)",
        "type": "slider",
        "min": 0, "max": 100, "step": 1, "default": 50,
        "help": "10-year historical percentile of current PE. Low = cheap.",
        "cadence": "Monthly",
    },
    {
        "key": "mcap_gdp_pctile",
        "label": "MCap/GDP Percentile (20Y, %)",
        "type": "slider",
        "min": 0, "max": 100, "step": 1, "default": 50,
        "help": "20Y percentile of total India MCap / nominal GDP.",
        "cadence": "Monthly",
    },
    {
        "key": "aaa_spread_pctile",
        "label": "AAA-GSec Spread Percentile (5Y, %)",
        "type": "slider",
        "min": 0, "max": 100, "step": 1, "default": 50,
        "help": "5Y percentile of AAA bond yield minus G-Sec. Tight = healthy.",
        "cadence": "Monthly",
    },
    {
        "key": "credit_growth_yoy",
        "label": "Bank Credit Growth YoY (%)",
        "type": "number",
        "min": -10.0, "max": 30.0, "step": 0.1, "default": 12.0,
        "help": "RBI weekly press release.",
        "cadence": "Bi-weekly",
    },
    {
        "key": "pct_above_200dma",
        "label": "% Nifty 500 above 200 DMA",
        "type": "slider",
        "min": 0, "max": 100, "step": 1, "default": 50,
        "help": "Breadth. >70% = broad strength.",
        "cadence": "Weekly",
    },
    {
        "key": "fii_30d",
        "label": "FII 30D Net Flow (Cr)",
        "type": "number",
        "min": -100000.0, "max": 100000.0, "step": 100.0, "default": 0.0,
        "help": "Sum of 30 trading days. Negative = outflow.",
        "cadence": "Daily/Weekly",
    },
    {
        "key": "dii_30d",
        "label": "DII 30D Net Flow (Cr)",
        "type": "number",
        "min": -50000.0, "max": 100000.0, "step": 100.0, "default": 5000.0,
        "help": "Sum of 30 trading days.",
        "cadence": "Daily/Weekly",
    },
    {
        "key": "sip_yoy",
        "label": "SIP YoY (%)",
        "type": "number",
        "min": -30.0, "max": 50.0, "step": 0.5, "default": 15.0,
        "help": "AMFI monthly release.",
        "cadence": "Monthly",
    },
    {
        "key": "rbi_stance",
        "label": "RBI Monetary Policy Stance",
        "type": "select",
        "options": ["Accommodative", "Neutral", "Tightening"],
        "default": "Neutral",
        "help": "Per latest MPC statement.",
        "cadence": "Per MPC (~6/year)",
    },
    {
        "key": "cpi_yoy_direction",
        "label": "CPI YoY Direction (3M trend)",
        "type": "select",
        "options": ["Falling", "Stable", "Rising"],
        "default": "Stable",
        "help": "Trend over last 3 monthly readings.",
        "cadence": "Monthly (12th)",
    },
    {
        "key": "pmi_mfg",
        "label": "Manufacturing PMI",
        "type": "number",
        "min": 40.0, "max": 65.0, "step": 0.1, "default": 53.0,
        "help": ">50 = expansion. S&P Global India release.",
        "cadence": "Monthly (1st)",
    },
    {
        "key": "gst_yoy",
        "label": "GST Collections YoY (%)",
        "type": "number",
        "min": -30.0, "max": 50.0, "step": 0.5, "default": 12.0,
        "help": "PIB monthly release.",
        "cadence": "Monthly (1st)",
    },
]

# Group manual fields by Engine A component for form layout
COMPONENT_GROUPS = [
    ("Valuation (C1)",       ["nifty_pe_ttm", "nifty_pe_pctile", "mcap_gdp_pctile"]),
    ("Credit & Rates (C2)",  ["aaa_spread_pctile", "credit_growth_yoy"]),
    ("Trend & Breadth (C3)", ["pct_above_200dma"]),
    ("Flows (C5)",           ["fii_30d", "dii_30d", "sip_yoy"]),
    ("Macro India (C6)",     ["rbi_stance", "cpi_yoy_direction", "pmi_mfg", "gst_yoy"]),
]


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


def load_current_manual_values():
    """
    Read manual_inputs.csv (long format) and return latest value per field.
    Returns dict: {field_key: (value_str, timestamp_str)}.
    Empty dict if CSV is missing or empty.
    """
    if not MANUAL_CSV_PATH.exists():
        return {}
    try:
        df = pd.read_csv(MANUAL_CSV_PATH)
        if df.empty:
            return {}
        df = df.sort_values("timestamp_ist")
        latest = df.groupby("field").tail(1)
        return {
            str(row["field"]): (str(row["value"]), str(row["timestamp_ist"]))
            for _, row in latest.iterrows()
        }
    except Exception as e:
        st.warning(f"Could not read manual_inputs.csv: {e}")
        return {}


# =============================================================================
# DASHBOARD RENDER (Step 9A, unchanged from theme-agnostic v2)
# =============================================================================
def render_hero(data):
    score        = data.get("score", 0)
    max_avail    = data.get("max_available_today", 0)
    max_theory   = data.get("max_theoretical", 100)
    score_pct    = data.get("score_pct_of_max_available", 0) or 0
    regime       = data.get("regime", "UNKNOWN")
    equity_pct   = data.get("regime_equity_pct", 0)

    regime_name, color, tone = REGIME_INFO.get(regime, (regime, "#525252", ""))

    st.markdown(
        f"""
        <div style="background:#ffffff; border:1px solid #e5e5e5;
                    border-left:6px solid {color}; padding:22px 24px;
                    border-radius:12px; margin-bottom:16px;
                    box-shadow:0 1px 3px rgba(0,0,0,0.06);">
            <div style="color:#525252; font-size:12px; letter-spacing:1.5px;
                        text-transform:uppercase; margin-bottom:6px; font-weight:600;">
                Engine A v2.1 &middot; Current State
            </div>
            <div style="color:#171717; font-size:52px; font-weight:700;
                        line-height:1.1; margin:6px 0;">
                {score}
                <span style="color:#737373; font-size:24px; font-weight:500;">
                    / {max_avail}
                </span>
            </div>
            <div style="color:#525252; font-size:13px; margin-bottom:14px;">
                {score_pct:.1f}% of max available today &middot;
                {max_avail}/{max_theory} pts unlocked
                ({max_theory - max_avail} pts blocked by pending inputs)
            </div>
            <div style="display:inline-block; background:{color}; color:#ffffff;
                        padding:8px 16px; border-radius:6px; font-weight:700;
                        font-size:14px; letter-spacing:0.5px;">
                {regime_name} &middot; {equity_pct}% EQUITY
            </div>
            <div style="color:#525252; font-size:13px; margin-top:12px;
                        font-style:italic;">
                {tone}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_pending_banner(data):
    pending = data.get("pending_manual", []) or []
    count = data.get("pending_manual_count", len(pending))
    if count == 0:
        st.success("All sub-inputs filled.")
        return
    st.warning(
        f"**{count} sub-inputs pending manual entry.** "
        f"Score computed on partial data. Enter values via the Admin tab."
    )
    with st.expander(f"Show pending list ({count})"):
        for p in pending:
            st.markdown(f"- `{p}`")


def render_component(comp_key, comp):
    name      = comp.get("name", comp_key)
    weight    = comp.get("weight", 0)
    score     = comp.get("score", 0) or 0
    max_avail = comp.get("max_available", 0) or 0
    pct       = comp.get("pct_of_max_available", 0) or 0

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

    progress = min(pct / 100.0, 1.0) if max_avail > 0 else 0.0
    st.progress(progress)

    sub_inputs = comp.get("sub_inputs", {}) or {}
    with st.expander(f"Sub-inputs ({len(sub_inputs)})"):
        for sub_key, sub in sub_inputs.items():
            render_sub_input(sub_key, sub)


def render_sub_input(sub_key, sub):
    status  = sub.get("status", "UNKNOWN")
    value   = sub.get("value")
    score   = sub.get("score")
    sub_max = sub.get("max", 0)
    note    = sub.get("note", "") or ""

    color = STATUS_COLOR.get(status, "#525252")
    label = STATUS_LABEL.get(status, status)
    value_str = "\u2014" if value is None else str(value)
    score_str = "\u2014" if score is None else f"{score}/{sub_max}"

    st.markdown(
        f"""
        <div style="background:#f5f5f5; border-left:3px solid {color};
                    padding:10px 12px; margin:8px 0; border-radius:4px;">
            <div style="display:flex; justify-content:space-between; align-items:center;">
                <span style="color:#171717; font-weight:600; font-size:14px;
                             font-family:ui-monospace,SFMono-Regular,Menlo,monospace;">
                    {sub_key}
                </span>
                <span style="color:{color}; font-size:10px; font-weight:700;
                             letter-spacing:1px;">{label}</span>
            </div>
            <div style="color:#525252; font-size:13px; margin-top:4px;">
                value:
                <code style="color:#171717; background:#ffffff; padding:1px 5px;
                             border-radius:3px; border:1px solid #e5e5e5;">{value_str}</code>
                &middot; score:
                <code style="color:#171717; background:#ffffff; padding:1px 5px;
                             border-radius:3px; border:1px solid #e5e5e5;">{score_str}</code>
            </div>
            <div style="color:#737373; font-size:12px; margin-top:4px; font-style:italic;">
                {note}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_raw_inputs(data):
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


def render_dashboard():
    """Step 9A read-only dashboard."""
    top_l, top_r = st.columns([3, 1])
    with top_l:
        st.caption(
            f"Auto-refresh every {REFRESH_INTERVAL_SEC // 60} min. "
            f"Tap refresh for instant update."
        )
    with top_r:
        if st.button("Refresh", use_container_width=True, key="refresh_dash"):
            st.rerun()

    data, err = load_engine_a_data(JSON_PATH)
    if err or data is None:
        st.error("Could not load engine_a_current.json.")
        st.code(err or "unknown error")
        st.code(f"Expected at: {JSON_PATH}")
        return

    schema_v = data.get("schema_version", "")
    computed_at = data.get("computed_at_ist", "unknown")
    if schema_v != "v2.1":
        st.warning(f"Unexpected schema version: '{schema_v}'.")
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


# =============================================================================
# ADMIN / MANUAL INPUT FORM (Step 9B)
# =============================================================================
def password_gate():
    """Return True if user is authenticated, False otherwise."""
    if st.session_state.get("admin_authed"):
        return True

    try:
        admin_pw = st.secrets["ADMIN_PASSWORD"]
    except (KeyError, FileNotFoundError):
        st.error("Missing Streamlit secret: ADMIN_PASSWORD.")
        st.info(
            "Add it at: share.streamlit.io \u2192 Manage app \u2192 Settings "
            "\u2192 Secrets. Format: `ADMIN_PASSWORD = \"your-password\"`"
        )
        return False

    st.markdown("#### Admin login required")
    st.caption("Manual input form is password-protected. Enter to unlock.")

    with st.form("password_form", clear_on_submit=False):
        pw = st.text_input("Password", type="password")
        ok = st.form_submit_button("Unlock", use_container_width=True)

    if ok:
        if hmac.compare_digest(pw, admin_pw):
            st.session_state.admin_authed = True
            st.rerun()
        else:
            st.error("Wrong password.")
    return False


def is_value_changed(new_val, old_val):
    """Compare new form value vs stored CSV value. True if meaningfully different."""
    if old_val is None or old_val == "" or str(old_val).lower() == "nan":
        return True
    try:
        return abs(float(new_val) - float(old_val)) > 1e-6
    except (ValueError, TypeError):
        return str(new_val) != str(old_val)


def render_field(field_cfg, current_value, current_ts):
    """Render one form widget; return user's value."""
    key = field_cfg["key"]
    label = field_cfg["label"]
    ftype = field_cfg["type"]

    # "Last updated" caption
    if current_value is not None and str(current_value).lower() != "nan":
        st.caption(
            f"**{key}**  \u00b7  last value: `{current_value}`  "
            f"\u00b7  updated: {current_ts}  \u00b7  cadence: {field_cfg['cadence']}"
        )
    else:
        st.caption(
            f"**{key}**  \u00b7  *never set*  \u00b7  cadence: {field_cfg['cadence']}"
        )

    if ftype == "number":
        default = float(current_value) if current_value not in (None, "", "nan") else field_cfg["default"]
        try:
            default = float(default)
        except (ValueError, TypeError):
            default = field_cfg["default"]
        # Clamp default within bounds
        default = max(field_cfg["min"], min(field_cfg["max"], default))
        return st.number_input(
            label,
            min_value=field_cfg["min"],
            max_value=field_cfg["max"],
            value=default,
            step=field_cfg["step"],
            help=field_cfg["help"],
            key=f"input_{key}",
        )
    if ftype == "slider":
        try:
            default = int(float(current_value)) if current_value not in (None, "", "nan") else field_cfg["default"]
        except (ValueError, TypeError):
            default = field_cfg["default"]
        default = max(field_cfg["min"], min(field_cfg["max"], default))
        return st.slider(
            label,
            min_value=field_cfg["min"],
            max_value=field_cfg["max"],
            value=default,
            step=field_cfg["step"],
            help=field_cfg["help"],
            key=f"input_{key}",
        )
    if ftype == "select":
        default_val = current_value if current_value in field_cfg["options"] else field_cfg["default"]
        default_idx = field_cfg["options"].index(default_val)
        return st.selectbox(
            label,
            options=field_cfg["options"],
            index=default_idx,
            help=field_cfg["help"],
            key=f"input_{key}",
        )
    return None


def commit_manual_inputs(changed_pairs, gh_pat):
    """
    Append rows to manual_inputs.csv and commit via GitHub API.
    Returns (success, error_msg, n_changed).
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    new_rows = pd.DataFrame([
        {"timestamp_ist": timestamp, "field": k, "value": v, "note": ""}
        for k, v in changed_pairs
    ])

    if MANUAL_CSV_PATH.exists():
        try:
            df_existing = pd.read_csv(MANUAL_CSV_PATH)
        except Exception:
            df_existing = pd.DataFrame(columns=["timestamp_ist", "field", "value", "note"])
    else:
        df_existing = pd.DataFrame(columns=["timestamp_ist", "field", "value", "note"])

    df_full = pd.concat([df_existing, new_rows], ignore_index=True)
    csv_content = df_full.to_csv(index=False)

    success, err = commit_file_to_repo(
        content=csv_content,
        repo_path=MANUAL_CSV_RELATIVE,
        commit_msg=f"Manual inputs: {len(changed_pairs)} field update(s)",
        token=gh_pat,
        owner=GITHUB_OWNER,
        repo=GITHUB_REPO,
        branch=GITHUB_BRANCH,
    )
    return success, err, len(changed_pairs)


def render_admin_form():
    """Step 9B password-gated manual input form."""
    if not password_gate():
        return

    # Check GH_PAT exists before showing form
    try:
        gh_pat = st.secrets["GH_PAT"]
    except (KeyError, FileNotFoundError):
        st.error("Missing Streamlit secret: GH_PAT.")
        st.info(
            "Add it at: share.streamlit.io \u2192 Manage app \u2192 Settings "
            "\u2192 Secrets. Format: `GH_PAT = \"github_pat_xxx...\"`"
        )
        return

    # Logout button
    top_l, top_r = st.columns([3, 1])
    with top_l:
        st.markdown("### Manual Inputs (Tier 4)")
    with top_r:
        if st.button("Log out", use_container_width=True):
            st.session_state.admin_authed = False
            st.rerun()

    current = load_current_manual_values()

    n_set = sum(1 for f in MANUAL_FIELDS if f["key"] in current)
    st.caption(
        f"{n_set} of {len(MANUAL_FIELDS)} manual inputs have a stored value. "
        f"Update only the fields that have changed and tap Save."
    )

    # The form
    with st.form("manual_inputs_form", clear_on_submit=False):
        form_values = {}
        for group_name, field_keys in COMPONENT_GROUPS:
            st.markdown(f"#### {group_name}")
            for key in field_keys:
                cfg = next(f for f in MANUAL_FIELDS if f["key"] == key)
                cur_val, cur_ts = current.get(key, (None, None))
                form_values[key] = render_field(cfg, cur_val, cur_ts)
            st.markdown("")  # spacing

        st.markdown("---")
        submitted = st.form_submit_button(
            "Save & commit to GitHub",
            use_container_width=True,
            type="primary",
        )

    if submitted:
        # Diff: which fields changed?
        changed = []
        for key, new_val in form_values.items():
            old_val = current.get(key, (None, None))[0]
            if is_value_changed(new_val, old_val):
                changed.append((key, new_val))

        if not changed:
            st.info("No changes detected. Nothing committed.")
            return

        with st.spinner(f"Committing {len(changed)} change(s) to GitHub..."):
            success, err, n = commit_manual_inputs(changed, gh_pat)

        if success:
            st.success(f"Committed {n} update(s) to `manual_inputs.csv`.")
            with st.expander("Show what was committed"):
                for k, v in changed:
                    st.markdown(f"- `{k}` \u2192 **{v}**")
            st.info(
                "Next cron run (within 15 min during NSE hours) will pick up "
                "new values and recompute the score. Refresh the Dashboard tab "
                "to see updates."
            )
        else:
            st.error(f"Commit failed.")
            st.code(err or "unknown")
            st.warning(
                "Your changes were NOT saved. Verify GH_PAT permissions "
                "(Contents:write on this repo) and try again."
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

    st.markdown("# Engine A v2.1")

    # Pause autorefresh when admin is logged in (avoid disrupting form entry)
    if not st.session_state.get("admin_authed"):
        st_autorefresh(
            interval=REFRESH_INTERVAL_SEC * 1000,
            key="engine_a_autorefresh",
        )

    tab_dashboard, tab_admin = st.tabs(["Dashboard", "Admin"])

    with tab_dashboard:
        render_dashboard()

    with tab_admin:
        render_admin_form()

    st.markdown("---")
    st.caption(
        "Engine A v2.1 \u00b7 Steps 9A + 9B. "
        "Compute layer (9C) wires manual inputs into the score \u2014 next ship."
    )


if __name__ == "__main__":
    main()
