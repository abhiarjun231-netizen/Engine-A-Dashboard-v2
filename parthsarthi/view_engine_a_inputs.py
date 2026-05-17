"""
view_engine_a_inputs.py
Parthsarthi Capital - Engine A manual-input tab.

Engine A's score is built from auto-fetched market data PLUS 13 manual
inputs that are published on different schedules (Nifty PE monthly,
bank credit bi-weekly, RBI stance per MPC, and so on). Those 13 are
entered by hand.

This tab is that input form, brought into the Parthsarthi dashboard
so everything lives in one place. For each field it shows:
  - the last saved value and when it was saved
  - a tappable link to the official source
  - an input box

On save, only the CHANGED fields are appended to
data/core/manual_inputs.csv and committed to the repo via the GitHub
Contents API. Engine A's cron picks up the new CSV on its next run
and recomputes the score.

Requirements:
  - github_io.py in the same folder
  - a 'GH_PAT' Streamlit secret (fine-grained PAT, Contents:write)
  - an admin password set as the 'ADMIN_PASSWORD' Streamlit secret
    (falls back to a default if not set - change it in production)
"""

import streamlit as st
import csv
import io
import os
from datetime import datetime

from github_io import commit_file_to_repo, read_file_from_repo


# ---- repo / file configuration ----
GITHUB_OWNER  = 'abhiarjun231-netizen'
GITHUB_REPO   = 'Engine-A-Dashboard-v2'
GITHUB_BRANCH = 'main'
MANUAL_CSV_RELATIVE = 'data/core/manual_inputs.csv'

# candidate local paths to read the current CSV (app runs from parthsarthi/)
_CSV_PATHS = [
    '../data/core/manual_inputs.csv',
    'data/core/manual_inputs.csv',
    './data/core/manual_inputs.csv',
]

NAVY    = '#0A1628'
SAFFRON = '#D97706'


# ---- the 13 manual fields (the contract with calculate_engine_a_v21.py) ----
MANUAL_FIELDS = [
    {'key': 'nifty_pe_ttm', 'label': 'Nifty 50 PE (TTM)', 'type': 'number',
     'min': 5.0, 'max': 50.0, 'step': 0.1, 'default': 22.0,
     'help': 'From Trendlyne. Feeds the yield-gap calculation.',
     'cadence': 'Monthly',
     'source_url': 'https://trendlyne.com/equity/PE/NIFTY/1887/nifty-50-price-to-earning-ratios/',
     'source_label': 'Trendlyne Nifty PE'},
    {'key': 'nifty_pe_pctile', 'label': 'Nifty PE Percentile (10Y, %)',
     'type': 'number', 'min': 0, 'max': 100, 'step': 1, 'default': 50,
     'help': '10-year historical percentile of current PE. Low = cheap.',
     'cadence': 'Monthly',
     'source_url': 'https://trendonify.com/india/stock-market/pe-ratio',
     'source_label': 'Trendonify PE percentile'},
    {'key': 'mcap_gdp_ratio', 'label': 'MCap/GDP Ratio (raw %)',
     'type': 'number', 'min': 10.0, 'max': 400.0, 'step': 0.01, 'default': 90.0,
     'help': 'Raw MCap/GDP % from GuruFocus. Compute converts to 20Y percentile.',
     'cadence': 'Monthly',
     'source_url': 'https://www.gurufocus.com/economic_indicators/4324/india-ratio-of-total-market-cap-over-gdp',
     'source_label': 'GuruFocus India MCap/GDP'},
    {'key': 'aaa_spread_bps', 'label': 'AAA-GSec Spread (basis points)',
     'type': 'number', 'min': 0, 'max': 500, 'step': 1, 'default': 75,
     'help': 'Raw AAA-GSec spread in bps. Source shows decimal % - multiply by 100.',
     'cadence': 'Monthly',
     'source_url': 'https://indiamacroindicators.co.in/economic-indicators/10-year-credit-spread-aaa-rated-bonds-g-sec',
     'source_label': 'India Macro AAA spread'},
    {'key': 'credit_growth_yoy', 'label': 'Bank Credit Growth YoY (%)',
     'type': 'number', 'min': -10.0, 'max': 30.0, 'step': 0.1, 'default': 12.0,
     'help': 'RBI weekly press release.', 'cadence': 'Bi-weekly',
     'source_url': 'https://tradingeconomics.com/india/loan-growth',
     'source_label': 'Trading Economics India loan growth'},
    {'key': 'pct_above_200dma', 'label': '% Nifty 500 above 200 DMA',
     'type': 'number', 'min': 0, 'max': 100, 'step': 1, 'default': 50,
     'help': 'Market breadth %. Above 70% = broad strength.',
     'cadence': 'Weekly',
     'source_url': 'https://trendlyne.com/fundamentals/stock-screener/797020/nifty-500-above-200-sma/index/NIFTY500/nifty-500/',
     'source_label': 'Trendlyne Nifty 500 > 200SMA screener'},
    {'key': 'fii_latest_month', 'label': 'FII Latest Month Net Flow (Cr)',
     'type': 'number', 'min': -200000.0, 'max': 200000.0, 'step': 100.0,
     'default': 0.0,
     'help': "Latest month's FII net flow in Cr. Compute uses it as a 30D proxy.",
     'cadence': 'Monthly',
     'source_url': 'https://trendlyne.com/macro-data/fii-dii/latest/cash-pastmonth/',
     'source_label': 'Trendlyne FII Last 30 Days'},
    {'key': 'dii_latest_month', 'label': 'DII Latest Month Net Flow (Cr)',
     'type': 'number', 'min': -100000.0, 'max': 200000.0, 'step': 100.0,
     'default': 30000.0,
     'help': "Latest month's DII net flow in Cr. Compute uses it as a 30D proxy.",
     'cadence': 'Monthly',
     'source_url': 'https://trendlyne.com/macro-data/fii-dii/latest/cash-pastmonth/',
     'source_label': 'Trendlyne DII Last 30 Days'},
    {'key': 'sip_yoy', 'label': 'SIP YoY (%)', 'type': 'number',
     'min': -30.0, 'max': 50.0, 'step': 0.5, 'default': 15.0,
     'help': 'AMFI monthly release.', 'cadence': 'Monthly',
     'source_url': 'https://www.amfiindia.com/research-information/amfi-monthly',
     'source_label': 'AMFI Monthly Note'},
    {'key': 'rbi_stance', 'label': 'RBI Monetary Policy Stance',
     'type': 'select', 'options': ['Accommodative', 'Neutral', 'Tightening'],
     'default': 'Neutral', 'help': 'Per the latest MPC statement.',
     'cadence': 'Per MPC (~6/year)',
     'source_url': 'https://www.rbi.org.in/Scripts/BS_PressReleaseDisplay.aspx',
     'source_label': 'RBI MPC press releases'},
    {'key': 'cpi_yoy_latest', 'label': 'CPI YoY Latest (%)', 'type': 'number',
     'min': -2.0, 'max': 15.0, 'step': 0.01, 'default': 4.0,
     'help': 'Latest CPI YoY %. Compute derives the 3M direction from past saves.',
     'cadence': 'Monthly (12th)',
     'source_url': 'https://tradingeconomics.com/india/inflation-cpi',
     'source_label': 'Trading Economics India CPI'},
    {'key': 'pmi_mfg', 'label': 'Manufacturing PMI', 'type': 'number',
     'min': 40.0, 'max': 65.0, 'step': 0.1, 'default': 53.0,
     'help': 'Above 50 = expansion. S&P Global India release.',
     'cadence': 'Monthly (1st)',
     'source_url': 'https://tradingeconomics.com/india/manufacturing-pmi',
     'source_label': 'Trading Economics India PMI'},
    {'key': 'gst_yoy', 'label': 'GST Collections YoY (%)', 'type': 'number',
     'min': -30.0, 'max': 50.0, 'step': 0.5, 'default': 12.0,
     'help': 'PIB monthly release.', 'cadence': 'Monthly (1st)',
     'source_url': 'https://pib.gov.in/AllRelease.aspx',
     'source_label': 'PIB GST releases'},
]

COMPONENT_GROUPS = [
    ('Valuation', ['nifty_pe_ttm', 'nifty_pe_pctile', 'mcap_gdp_ratio']),
    ('Credit & Rates', ['aaa_spread_bps', 'credit_growth_yoy']),
    ('Trend & Breadth', ['pct_above_200dma']),
    ('Flows', ['fii_latest_month', 'dii_latest_month', 'sip_yoy']),
    ('Macro India', ['rbi_stance', 'cpi_yoy_latest', 'pmi_mfg', 'gst_yoy']),
]

_FIELD_BY_KEY = {f['key']: f for f in MANUAL_FIELDS}


def _get_manual_csv_text():
    """
    Return the text of manual_inputs.csv.

    Reads from the GitHub repo — the SAME place this form commits to —
    so a value saved in an earlier session shows back correctly after a
    browser refresh. The Contents API is not CDN-cached, so a commit is
    reflected immediately.

    Falls back to the app's LOCAL copy only if the repo read fails (no
    token, network error, etc.). That local copy is frozen at the last
    deploy and can be stale — the repo is the source of truth. Before
    this fix the form always read the local copy, which is why saved
    values appeared to vanish on refresh.
    """
    token = _get_secret('GH_PAT')
    if token:
        text, err = read_file_from_repo(
            MANUAL_CSV_RELATIVE, token,
            GITHUB_OWNER, GITHUB_REPO, GITHUB_BRANCH)
        if text is not None:
            return text          # live repo file
        if err is None:
            return ''            # file does not exist in the repo yet
        # a real error — fall through to the local copy below

    for p in _CSV_PATHS:
        if os.path.exists(p):
            try:
                with open(p, 'r', encoding='utf-8') as f:
                    return f.read()
            except OSError:
                return ''
    return ''


def _load_current_values():
    """
    Parse manual_inputs.csv (long format: timestamp_ist, field, value,
    note) and return {field_key: (value_str, timestamp_str)} - the
    latest entry per field.
    """
    text = _get_manual_csv_text()
    latest = {}
    try:
        for row in csv.DictReader(io.StringIO(text)):
            fld = row.get('field')
            if fld:
                # later rows overwrite earlier - CSV is append-order
                latest[fld] = (row.get('value', ''),
                               row.get('timestamp_ist', ''))
    except csv.Error:
        return {}
    return latest


def _build_csv(existing_rows, changed_pairs):
    """Append changed fields to the existing rows and return CSV text."""
    ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(['timestamp_ist', 'field', 'value', 'note'])
    for r in existing_rows:
        writer.writerow([r.get('timestamp_ist', ''), r.get('field', ''),
                         r.get('value', ''), r.get('note', '')])
    for key, val in changed_pairs:
        writer.writerow([ts, key, val, ''])
    return out.getvalue()


def _read_existing_rows():
    """
    Return the full manual_inputs.csv as a list of row dicts.

    Reads from the repo (same source as _load_current_values), so a
    save appends to the LIVE file — never to a stale local copy that
    would silently drop history written by an earlier session.
    """
    text = _get_manual_csv_text()
    try:
        return list(csv.DictReader(io.StringIO(text)))
    except csv.Error:
        return []


def _changed(new_val, old_val):
    """True if the new value differs meaningfully from the stored one."""
    if old_val is None or old_val == '' or str(old_val).lower() == 'nan':
        return True
    try:
        return abs(float(new_val) - float(old_val)) > 1e-6
    except (ValueError, TypeError):
        return str(new_val) != str(old_val)


def _get_secret(name, default=None):
    """
    Safely read a Streamlit secret. st.secrets raises if no secrets file
    exists at all, so this wraps it - never crashes, returns the default.
    """
    try:
        return st.secrets.get(name, default)
    except Exception:
        return default


def render():
    """Render the Engine A Inputs tab. Called by app.py."""
    st.header('Engine A Inputs')
    st.caption('The 13 manual inputs behind the Engine A score. Each has a '
               'link to its official source - open it, read the number, '
               'enter it here, save. Only changed fields are committed.')
    st.divider()

    # password gate
    correct = _get_secret('ADMIN_PASSWORD', 'parthsarthi')
    if not st.session_state.get('ea_inputs_unlocked'):
        st.info('This form is password-protected.')
        pw = st.text_input('Password', type='password', key='ea_pw')
        if st.button('Unlock'):
            if pw == correct:
                st.session_state['ea_inputs_unlocked'] = True
                st.rerun()
            else:
                st.error('Wrong password.')
        return

    # confirmation from a save that just happened — survives the rerun
    # that reloads the form with the newly-saved values
    saved_msg = st.session_state.pop('ea_save_msg', None)
    if saved_msg:
        st.success(saved_msg)

    current = _load_current_values()

    # render fields grouped by component
    entered = {}
    for group_name, keys in COMPONENT_GROUPS:
        st.subheader(group_name)
        for key in keys:
            cfg = _FIELD_BY_KEY[key]
            cur_val, cur_ts = current.get(key, (None, None))

            if cur_val not in (None, '', 'nan'):
                st.caption(f'Last value: {cur_val}  ·  updated {cur_ts}  '
                           f'·  cadence: {cfg["cadence"]}')
            else:
                st.caption(f'Never set  ·  cadence: {cfg["cadence"]}')
            st.markdown(f'[Open {cfg["source_label"]}]({cfg["source_url"]})')

            if cfg['type'] == 'number':
                is_int = (isinstance(cfg['step'], int)
                          and isinstance(cfg['default'], int))
                coerce = int if is_int else float
                if cur_val not in (None, '', 'nan'):
                    try:
                        default = coerce(float(cur_val))
                    except (ValueError, TypeError):
                        default = cfg['default']
                else:
                    default = cfg['default']
                default = max(cfg['min'], min(cfg['max'], default))
                entered[key] = st.number_input(
                    cfg['label'], min_value=cfg['min'], max_value=cfg['max'],
                    value=default, step=cfg['step'], help=cfg['help'],
                    key=f'ea_input_{key}')
            elif cfg['type'] == 'select':
                dv = cur_val if cur_val in cfg['options'] else cfg['default']
                entered[key] = st.selectbox(
                    cfg['label'], options=cfg['options'],
                    index=cfg['options'].index(dv), help=cfg['help'],
                    key=f'ea_input_{key}')
            st.write('')
        st.divider()

    # save
    st.subheader('Save Changes')
    changed_pairs = [(k, v) for k, v in entered.items()
                     if _changed(v, current.get(k, (None, None))[0])]

    if not changed_pairs:
        st.info('No changes to save - all values match the last saved set.')
        return

    st.write(f'**{len(changed_pairs)}** field(s) changed: '
             + ', '.join(k for k, _ in changed_pairs))

    if st.button('Save & Commit to Engine A', type='primary'):
        token = _get_secret('GH_PAT')
        if not token:
            st.error('GH_PAT secret is not set on this app. Add it in the '
                     'Streamlit app settings (Secrets) before saving.')
            return
        with st.spinner('Committing manual_inputs.csv to the repo...'):
            existing = _read_existing_rows()
            csv_text = _build_csv(existing, changed_pairs)
            ok, err = commit_file_to_repo(
                content=csv_text, repo_path=MANUAL_CSV_RELATIVE,
                commit_msg=f'Manual inputs: {len(changed_pairs)} field update(s)',
                token=token, owner=GITHUB_OWNER, repo=GITHUB_REPO,
                branch=GITHUB_BRANCH)
        if ok:
            # Stash the confirmation, then rerun so the form reloads from
            # the repo and immediately shows the just-saved values (and
            # their fresh "last updated" timestamps).
            st.session_state['ea_save_msg'] = (
                f'Saved - {len(changed_pairs)} field(s) committed to the '
                'repo. Engine A will recompute on its next scheduled run.')
            st.rerun()
        else:
            st.error(f'Commit failed: {err}')


# ---- self-test (structure check) ----
if __name__ == '__main__':
    import ast
    src = open(__file__).read()
    ast.parse(src)
    print('=' * 56)
    print('ENGINE A INPUTS VIEW - structure self-test')
    print('=' * 56)
    print(f'Manual fields defined: {len(MANUAL_FIELDS)} (expected 13)')
    grouped = sum(len(keys) for _, keys in COMPONENT_GROUPS)
    print(f'Fields placed in component groups: {grouped}')
    print(f'All fields have source links: '
          f'{all("source_url" in f for f in MANUAL_FIELDS)}')
    funcs = [n.name for n in ast.walk(ast.parse(src))
             if isinstance(n, ast.FunctionDef)]
    print(f'render() present: {"render" in funcs}')
    print('\nSyntax valid. Form commits via github_io to manual_inputs.csv.')
    print('=' * 56)
