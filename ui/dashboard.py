# dashboard.py  —  CloudScope v2
import streamlit as st
import requests
import time
import pandas as pd
from datetime import datetime

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="CloudScope",
    page_icon="☁️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
/* ── Fonts ── */
@import url('https://fonts.googleapis.com/css2?family=Space+Mono:wght@400;700&family=DM+Sans:wght@300;400;500;600&display=swap');

/* ── Root palette ── */
:root {
    --bg:        #0d1117;
    --surface:   #161b22;
    --border:    #30363d;
    --accent:    #58a6ff;
    --green:     #3fb950;
    --yellow:    #d29922;
    --red:       #f85149;
    --text:      #e6edf3;
    --muted:     #8b949e;
}

/* ── Global ── */
html, body, [class*="css"] {
    background-color: var(--bg) !important;
    color: var(--text) !important;
    font-family: 'DM Sans', sans-serif;
}

/* ── Sidebar ── */
[data-testid="stSidebar"] {
    background-color: var(--surface) !important;
    border-right: 1px solid var(--border);
}

/* ── Metric cards ── */
.metric-card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 20px 24px;
    margin-bottom: 4px;
    transition: border-color 0.2s;
}
.metric-card:hover { border-color: var(--accent); }
.metric-label {
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: var(--muted);
    margin-bottom: 6px;
}
.metric-value {
    font-family: 'Space Mono', monospace;
    font-size: 32px;
    font-weight: 700;
    line-height: 1;
    margin-bottom: 10px;
}
.metric-bar-bg {
    background: #21262d;
    border-radius: 4px;
    height: 6px;
    width: 100%;
    overflow: hidden;
}
.metric-bar-fill {
    height: 6px;
    border-radius: 4px;
    transition: width 0.5s ease;
}

/* ── Alert cards ── */
.alert-card {
    border-radius: 10px;
    padding: 12px 16px;
    margin-bottom: 8px;
    font-size: 14px;
    font-weight: 500;
    display: flex;
    align-items: center;
    gap: 10px;
}
.alert-critical {
    background: rgba(248,81,73,0.12);
    border: 1px solid rgba(248,81,73,0.4);
    color: #f85149;
}
.alert-warning {
    background: rgba(210,153,34,0.12);
    border: 1px solid rgba(210,153,34,0.4);
    color: #d29922;
}
.alert-ok {
    background: rgba(63,185,80,0.10);
    border: 1px solid rgba(63,185,80,0.35);
    color: #3fb950;
}

/* ── Status badge ── */
.status-badge {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 4px 12px;
    border-radius: 20px;
    font-size: 12px;
    font-weight: 600;
    letter-spacing: 0.05em;
    text-transform: uppercase;
}
.status-healthy  { background:rgba(63,185,80,0.15);  color:#3fb950; }
.status-warning  { background:rgba(210,153,34,0.15); color:#d29922; }
.status-critical { background:rgba(248,81,73,0.15);  color:#f85149; }

/* ── Anomaly score ring ── */
.score-ring {
    font-family: 'Space Mono', monospace;
    font-size: 48px;
    font-weight: 700;
    text-align: center;
    margin: 8px 0 4px;
}
.score-label {
    font-size: 11px;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    color: var(--muted);
    text-align: center;
}

/* ── Section headers ── */
.section-header {
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.14em;
    text-transform: uppercase;
    color: var(--muted);
    margin: 20px 0 10px;
    padding-bottom: 6px;
    border-bottom: 1px solid var(--border);
}

/* ── Timestamp ── */
.ts {
    font-family: 'Space Mono', monospace;
    font-size: 11px;
    color: var(--muted);
}

/* ── Hide Streamlit chrome ── */
#MainMenu, footer, header { visibility: hidden; }
[data-testid="stToolbar"] { display: none; }
</style>
""", unsafe_allow_html=True)

# ── Config ────────────────────────────────────────────────────────────────────
BACKEND_URL  = "http://backend:8000"
HISTORY_SIZE = 30

# ── Session state ─────────────────────────────────────────────────────────────
if "history" not in st.session_state:
    st.session_state.history = []
if "last_fetch" not in st.session_state:
    st.session_state.last_fetch = None
if "auto_refresh" not in st.session_state:
    st.session_state.auto_refresh = False

# ── Data fetching ─────────────────────────────────────────────────────────────
def fetch_metrics() -> dict | None:
    """Fetch /metrics from backend with retry. Returns None on failure."""
    for attempt in range(3):
        try:
            r = requests.get(f"{BACKEND_URL}/metrics", timeout=5)
            r.raise_for_status()
            return r.json()
        except requests.exceptions.ConnectionError:
            if attempt == 2:
                st.toast("⚠️ Cannot reach backend — check it's running", icon="🔴")
            time.sleep(0.8)
        except requests.exceptions.Timeout:
            st.toast("⚠️ Request timed out", icon="🕐")
            break
        except Exception as e:
            st.toast(f"Unexpected error: {e}", icon="❌")
            break
    return None

def fetch_history() -> list:
    """Fetch /history from backend for trend charts."""
    try:
        r = requests.get(f"{BACKEND_URL}/history", timeout=5)
        r.raise_for_status()
        return r.json().get("history", [])
    except Exception:
        return []

# ── Helpers ───────────────────────────────────────────────────────────────────
def _colour(val: float, warn: float, crit: float) -> str:
    if val >= crit: return "#f85149"
    if val >= warn: return "#d29922"
    return "#3fb950"

def _status_badge(status: str) -> str:
    icons = {"healthy": "●", "warning": "◐", "critical": "●"}
    icon  = icons.get(status, "●")
    return f'<span class="status-badge status-{status}">{icon} {status.upper()}</span>'

def _score_colour(score: float) -> str:
    if score >= 60: return "#f85149"
    if score >= 30: return "#d29922"
    return "#3fb950"

def render_metric_card(label: str, value: int, unit: str,
                       warn: float, crit: float, max_val: float = 100):
    col   = _colour(value, warn, crit)
    pct   = min(value / max_val * 100, 100)
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-label">{label}</div>
        <div class="metric-value" style="color:{col}">{value}<span style="font-size:16px;color:#8b949e">{unit}</span></div>
        <div class="metric-bar-bg">
            <div class="metric-bar-fill" style="width:{pct}%;background:{col}"></div>
        </div>
    </div>""", unsafe_allow_html=True)

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## ☁️ CloudScope")
    st.markdown('<div class="ts">Cloud Infrastructure Monitor</div>', unsafe_allow_html=True)
    st.divider()

    st.markdown('<div class="section-header">Controls</div>', unsafe_allow_html=True)
    auto = st.toggle("Auto-refresh (5s)", value=st.session_state.auto_refresh)
    st.session_state.auto_refresh = auto

    manual = st.button("⟳  Refresh Now", use_container_width=True)

    st.divider()
    st.markdown('<div class="section-header">Backend</div>', unsafe_allow_html=True)
    backend_input = st.text_input("URL", value=BACKEND_URL, label_visibility="collapsed")
    if backend_input:
        BACKEND_URL = backend_input.rstrip("/")

    st.divider()
    st.markdown('<div class="section-header">Thresholds</div>', unsafe_allow_html=True)
    cpu_warn  = st.slider("CPU warn %",    50, 95, 75)
    cpu_crit  = st.slider("CPU critical %",60, 100, 90)
    mem_warn  = st.slider("Mem warn %",    50, 95, 80)
    mem_crit  = st.slider("Mem critical %",60, 100, 90)

    st.divider()
    if st.button("🗑  Clear History", use_container_width=True):
        st.session_state.history = []
        st.rerun()

# ── Main header ───────────────────────────────────────────────────────────────
col_title, col_status = st.columns([3, 1])
with col_title:
    st.markdown("# ☁️ CloudScope Dashboard")

# ── Fetch ─────────────────────────────────────────────────────────────────────
should_fetch = manual or st.session_state.auto_refresh

payload = None
if should_fetch:
    with st.spinner("Fetching metrics…"):
        payload = fetch_metrics()

    if payload:
        st.session_state.last_fetch = payload
        ts = datetime.now().strftime("%H:%M:%S")
        row = {
            "time":    ts,
            "cpu":     payload["data"]["cpu"],
            "memory":  payload["data"]["memory"],
            "disk":    payload["data"]["disk"],
            "network": payload["data"]["network"],
            "latency": payload["data"]["latency"],
            "score":   payload["anomaly_score"],
        }
        st.session_state.history.append(row)
        if len(st.session_state.history) > HISTORY_SIZE:
            st.session_state.history.pop(0)

# Use cached payload if no fresh fetch
display = payload or st.session_state.get("last_fetch")

# ── Status bar ────────────────────────────────────────────────────────────────
with col_status:
    if display:
        status = display.get("status", "healthy")
        st.markdown(_status_badge(status), unsafe_allow_html=True)
        st.markdown(
            f'<div class="ts" style="text-align:right">Updated {datetime.now().strftime("%H:%M:%S")}</div>',
            unsafe_allow_html=True
        )

# ── No data yet ───────────────────────────────────────────────────────────────
if not display:
    st.markdown("""
    <div style="text-align:center;padding:80px 0;color:#8b949e">
        <div style="font-size:56px;margin-bottom:16px">☁️</div>
        <div style="font-size:20px;font-weight:600;color:#e6edf3;margin-bottom:8px">No data yet</div>
        <div style="font-size:14px">Click <b>Refresh Now</b> or enable Auto-refresh to start monitoring</div>
    </div>
    """, unsafe_allow_html=True)
    if st.session_state.auto_refresh:
        time.sleep(5)
        st.rerun()
    st.stop()

# ── Metrics row ───────────────────────────────────────────────────────────────
st.markdown('<div class="section-header">Live Metrics</div>', unsafe_allow_html=True)

d = display["data"]
c1, c2, c3, c4, c5 = st.columns(5)

with c1:
    render_metric_card("CPU", d["cpu"], "%", cpu_warn, cpu_crit)
with c2:
    render_metric_card("Memory", d["memory"], "%", mem_warn, mem_crit)
with c3:
    render_metric_card("Disk", d["disk"], "%", 80, 90)
with c4:
    render_metric_card("Latency", d["latency"], "ms", 150, 300, max_val=800)
with c5:
    render_metric_card("Network", d["network"], "MB/s", 400, 700, max_val=950)

# ── Anomaly score + Alerts ────────────────────────────────────────────────────
score_col, alert_col = st.columns([1, 2])

with score_col:
    st.markdown('<div class="section-header">Anomaly Score</div>', unsafe_allow_html=True)
    score = display.get("anomaly_score", 0)
    sc    = _score_colour(score)
    mode  = display["data"].get("mode", "normal")
    st.markdown(f"""
    <div class="metric-card" style="text-align:center">
        <div class="score-ring" style="color:{sc}">{score}</div>
        <div class="score-label">out of 100</div>
        <div style="margin-top:12px">
            <span class="status-badge status-{'critical' if score>=60 else 'warning' if score>=30 else 'healthy'}">
                {'ANOMALOUS' if score>=60 else 'ELEVATED' if score>=30 else 'NORMAL'}
            </span>
        </div>
        <div class="ts" style="margin-top:10px">Simulator: {mode.upper()}</div>
    </div>""", unsafe_allow_html=True)

with alert_col:
    st.markdown('<div class="section-header">Alerts</div>', unsafe_allow_html=True)
    alerts = display.get("alerts", [])
    if not alerts:
        st.markdown('<div class="alert-card alert-ok">✔ All systems operating normally</div>',
                    unsafe_allow_html=True)
    else:
        for a in alerts:
            sev   = a.get("severity", "warning")
            icon  = "🔴" if sev == "critical" else "🟡"
            label = "CRITICAL" if sev == "critical" else "WARNING"
            msg   = a.get("message", "Alert")
            val   = a.get("value", "")
            unit  = "ms" if a.get("metric") == "latency" else \
                    ("MB/s" if a.get("metric") == "network" else "%")
            st.markdown(
                f'<div class="alert-card alert-{sev}">'
                f'{icon} <b>[{label}]</b> {msg} &nbsp;'
                f'<span style="opacity:.7">({val}{unit})</span></div>',
                unsafe_allow_html=True
            )

# ── Trend charts ──────────────────────────────────────────────────────────────
if len(st.session_state.history) >= 2:
    st.markdown('<div class="section-header">Trends</div>', unsafe_allow_html=True)
    df = pd.DataFrame(st.session_state.history).set_index("time")

    chart_col1, chart_col2 = st.columns(2)
    with chart_col1:
        st.caption("CPU & Memory %")
        st.line_chart(df[["cpu", "memory"]], height=180, use_container_width=True)
    with chart_col2:
        st.caption("Latency (ms) & Anomaly Score")
        st.line_chart(df[["latency", "score"]], height=180, use_container_width=True)

    with st.expander("📋 Raw History Table"):
        st.dataframe(
            df.style.background_gradient(subset=["cpu","memory","disk","score"],
                                         cmap="RdYlGn_r"),
            use_container_width=True
        )

# ── Auto-refresh loop ─────────────────────────────────────────────────────────
if st.session_state.auto_refresh:
    time.sleep(5)
    st.rerun()
