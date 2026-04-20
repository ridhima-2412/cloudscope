import os
import time
from datetime import datetime

import pandas as pd
import requests
import streamlit as st

st.set_page_config(
    page_title="CloudScope",
    page_icon="C",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700&family=JetBrains+Mono:wght@500;700&display=swap');

:root {
    --bg: #08111f;
    --bg-soft: #0d1b2f;
    --panel: rgba(11, 25, 43, 0.94);
    --panel-strong: rgba(13, 31, 53, 0.98);
    --panel-alt: rgba(18, 40, 66, 0.98);
    --border: rgba(148, 197, 255, 0.26);
    --border-strong: rgba(125, 211, 252, 0.42);
    --text: #f7fbff;
    --muted: #b4c6dc;
    --muted-strong: #d9e7f5;
    --accent: #7dd3fc;
    --accent-2: #38bdf8;
    --good: #4ade80;
    --warn: #f59e0b;
    --bad: #fb7185;
    --shadow: rgba(0, 0, 0, 0.28);
}

.stApp {
    background:
        radial-gradient(circle at top left, rgba(125, 211, 252, 0.18), transparent 34%),
        radial-gradient(circle at top right, rgba(56, 189, 248, 0.16), transparent 28%),
        linear-gradient(180deg, #07101d 0%, #0b1524 100%);
    color: var(--text);
    font-family: 'Space Grotesk', sans-serif;
}

[data-testid="stAppViewContainer"],
[data-testid="stAppViewContainer"] * {
    color: var(--text);
}

[data-testid="stSidebar"] {
    background: rgba(8, 17, 30, 0.98);
    border-right: 1px solid var(--border-strong);
}

[data-testid="stSidebar"] * {
    color: var(--text) !important;
}

[data-testid="stHeader"], footer, #MainMenu {
    visibility: hidden;
}

[data-testid="stToolbar"] {
    display: none;
}

.hero {
    padding: 1.5rem 1.6rem;
    border: 1px solid var(--border-strong);
    background: linear-gradient(135deg, rgba(12, 28, 49, 0.98), rgba(15, 51, 84, 0.92));
    border-radius: 24px;
    box-shadow: 0 18px 50px var(--shadow);
}

.eyebrow {
    color: var(--accent);
    font-size: 0.8rem;
    letter-spacing: 0.24em;
    text-transform: uppercase;
    font-weight: 700;
}

.hero-title {
    margin: 0.2rem 0 0 0;
    font-size: 2.35rem;
    line-height: 1;
    font-weight: 700;
    color: var(--text);
}

.hero-subtitle {
    color: var(--muted-strong);
    margin-top: 0.6rem;
    font-size: 1rem;
}

.panel {
    background: var(--panel);
    border: 1px solid var(--border);
    border-radius: 20px;
    padding: 1rem 1.1rem;
    box-shadow: 0 10px 30px var(--shadow);
}

.section-title {
    font-size: 0.8rem;
    letter-spacing: 0.18em;
    text-transform: uppercase;
    color: var(--muted-strong);
    margin-bottom: 0.75rem;
    font-weight: 700;
}

.metric-card {
    background: linear-gradient(180deg, rgba(11, 25, 43, 0.98), rgba(12, 23, 39, 0.94));
    border: 1px solid var(--border);
    border-radius: 20px;
    padding: 1rem;
    min-height: 148px;
    box-shadow: 0 12px 24px rgba(0, 0, 0, 0.16);
}

.metric-label {
    color: var(--muted-strong);
    text-transform: uppercase;
    letter-spacing: 0.12em;
    font-size: 0.76rem;
    font-weight: 700;
}

.metric-value {
    font-family: 'JetBrains Mono', monospace;
    font-size: 2rem;
    font-weight: 700;
    margin-top: 0.7rem;
    color: var(--text);
}

.metric-meta {
    color: var(--muted);
    margin-top: 0.4rem;
    font-size: 0.88rem;
    line-height: 1.45;
}

.metric-bar {
    margin-top: 0.85rem;
    height: 8px;
    border-radius: 999px;
    background: rgba(255, 255, 255, 0.12);
    overflow: hidden;
}

.metric-bar > span {
    display: block;
    height: 100%;
    border-radius: 999px;
}

.status-badge {
    display: inline-flex;
    align-items: center;
    gap: 0.45rem;
    padding: 0.45rem 0.9rem;
    border-radius: 999px;
    font-size: 0.78rem;
    text-transform: uppercase;
    letter-spacing: 0.12em;
    font-weight: 700;
    border: 1px solid transparent;
}

.status-healthy {
    color: var(--good);
    background: rgba(74, 222, 128, 0.12);
    border-color: rgba(74, 222, 128, 0.24);
}

.status-warning {
    color: var(--warn);
    background: rgba(251, 191, 36, 0.12);
    border-color: rgba(251, 191, 36, 0.24);
}

.status-critical {
    color: var(--bad);
    background: rgba(251, 113, 133, 0.12);
    border-color: rgba(251, 113, 133, 0.24);
}

.signal-card {
    padding: 1.1rem;
    border-radius: 20px;
    border: 1px solid var(--border);
    background: var(--panel-strong);
    text-align: center;
    box-shadow: 0 10px 24px rgba(0, 0, 0, 0.18);
}

.signal-value {
    font-family: 'JetBrains Mono', monospace;
    font-size: 2.8rem;
    font-weight: 700;
    color: var(--text);
}

.signal-label {
    color: var(--muted-strong);
    text-transform: uppercase;
    letter-spacing: 0.14em;
    font-size: 0.76rem;
    margin-top: 0.3rem;
}

.alert-card {
    border-radius: 16px;
    padding: 0.9rem 1rem;
    margin-bottom: 0.7rem;
    border: 1px solid var(--border-strong);
    background: rgba(12, 28, 46, 0.96);
    color: var(--text);
    line-height: 1.5;
}

.alert-critical {
    border-color: rgba(251, 113, 133, 0.55);
    background: rgba(84, 18, 38, 0.88);
}

.alert-warning {
    border-color: rgba(245, 158, 11, 0.55);
    background: rgba(88, 54, 7, 0.9);
}

.tiny {
    color: var(--muted);
    font-size: 0.8rem;
    line-height: 1.5;
}

.mono {
    font-family: 'JetBrains Mono', monospace;
}

.stMarkdown, .stCaption, .stAlert, .stCode, .stText {
    color: var(--text) !important;
}

[data-testid="stSidebar"] .stCaption,
.stCaption {
    color: var(--muted-strong) !important;
}

.stButton > button,
[data-testid="baseButton-secondary"],
[data-testid="baseButton-primary"] {
    background: linear-gradient(180deg, #1d4ed8, #1e40af) !important;
    color: #f8fbff !important;
    border: 1px solid rgba(147, 197, 253, 0.65) !important;
    border-radius: 12px !important;
    font-weight: 700 !important;
    box-shadow: 0 8px 20px rgba(30, 64, 175, 0.24) !important;
}

.stButton > button:hover {
    background: linear-gradient(180deg, #2563eb, #1d4ed8) !important;
    border-color: rgba(191, 219, 254, 0.9) !important;
}

.stButton > button:focus,
.stTextInput input:focus,
[data-baseweb="input"] input:focus,
[data-baseweb="select"] input:focus {
    box-shadow: 0 0 0 0.2rem rgba(125, 211, 252, 0.22) !important;
    border-color: var(--accent) !important;
}

.stTextInput label,
.stSlider label,
.stToggle label,
.stSelectbox label,
.stNumberInput label {
    color: var(--muted-strong) !important;
    font-weight: 600 !important;
}

.stTextInput input,
[data-baseweb="input"] input,
[data-baseweb="base-input"] input {
    background: rgba(13, 31, 53, 0.98) !important;
    color: var(--text) !important;
    border: 1px solid var(--border-strong) !important;
}

.stTextInput input::placeholder,
[data-baseweb="input"] input::placeholder,
[data-baseweb="base-input"] input::placeholder {
    color: #c7d7e8 !important;
    opacity: 1 !important;
}

.stSlider [data-baseweb="slider"] * {
    color: var(--text) !important;
}

.stSlider [role="slider"] {
    background: var(--accent-2) !important;
}

.stToggle [data-baseweb="checkbox"] * {
    color: var(--text) !important;
}

[data-testid="stMetric"] {
    background: var(--panel) !important;
    border: 1px solid var(--border) !important;
    border-radius: 18px !important;
}

[data-testid="stMetricLabel"],
[data-testid="stMetricValue"],
[data-testid="stMetricDelta"] {
    color: var(--text) !important;
}

[data-testid="stDataFrame"],
[data-testid="stTable"] {
    background: var(--panel) !important;
    border: 1px solid var(--border) !important;
    border-radius: 18px !important;
    overflow: hidden !important;
}

[data-testid="stDataFrame"] * {
    color: var(--text) !important;
}

[data-testid="stDataFrame"] [role="columnheader"] {
    background: rgba(21, 44, 73, 0.98) !important;
    color: var(--text) !important;
    font-weight: 700 !important;
}

[data-testid="stDataFrame"] [role="gridcell"] {
    background: rgba(10, 24, 42, 0.96) !important;
}

[data-testid="stDataFrame"] [role="row"]:nth-child(even) [role="gridcell"] {
    background: rgba(14, 30, 51, 0.98) !important;
}

[data-testid="stDataFrame"] svg text,
[data-testid="stDataFrame"] canvas {
    color: var(--text) !important;
}

.stAlert {
    background: var(--panel-alt) !important;
    border: 1px solid var(--border-strong) !important;
    color: var(--text) !important;
}

.stSuccess {
    background: rgba(17, 66, 43, 0.92) !important;
    border-color: rgba(74, 222, 128, 0.45) !important;
}

.stWarning {
    background: rgba(92, 58, 7, 0.95) !important;
    border-color: rgba(245, 158, 11, 0.5) !important;
}

.stError {
    background: rgba(90, 21, 39, 0.95) !important;
    border-color: rgba(251, 113, 133, 0.55) !important;
}

.stInfo {
    background: rgba(14, 46, 76, 0.96) !important;
    border-color: rgba(125, 211, 252, 0.45) !important;
}

[data-testid="stSpinner"] * {
    color: var(--text) !important;
}

[data-testid="stExpander"] * {
    color: var(--text) !important;
}

iframe[title="streamlit_vega_lite_chart"] {
    filter: brightness(1.08) contrast(1.12);
}

@media (max-width: 900px) {
    .hero-title {
        font-size: 1.9rem;
    }

    .metric-value {
        font-size: 1.7rem;
    }

    .signal-value {
        font-size: 2.2rem;
    }
}
</style>
""",
    unsafe_allow_html=True,
)

DEFAULT_BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000").rstrip("/")
DEFAULT_POLL_SECONDS = int(os.getenv("POLL_SECONDS", "5"))
REQUEST_TIMEOUT = 5


def safe_number(value, default=0.0):
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def severity_color(value: float, warning: float, critical: float, reverse: bool = False) -> str:
    if reverse:
        if value <= critical:
            return "#fb7185"
        if value <= warning:
            return "#fbbf24"
        return "#4ade80"
    if value >= critical:
        return "#fb7185"
    if value >= warning:
        return "#fbbf24"
    return "#4ade80"


def status_badge(status: str) -> str:
    normalized = (status or "healthy").lower()
    label = normalized.upper()
    dot = "●"
    return f'<span class="status-badge status-{normalized}">{dot} {label}</span>'


def fetch_json(path: str, base_url: str) -> tuple[dict | None, str | None]:
    try:
        response = requests.get(f"{base_url}{path}", timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        return response.json(), None
    except requests.exceptions.Timeout:
        return None, f"Timed out while requesting {path} from {base_url}."
    except requests.exceptions.ConnectionError:
        return None, f"Could not connect to backend at {base_url}."
    except requests.exceptions.HTTPError as exc:
        return None, f"Backend returned HTTP {exc.response.status_code} for {path}."
    except requests.exceptions.RequestException as exc:
        return None, f"Request failed for {path}: {exc}"
    except ValueError:
        return None, f"Backend returned invalid JSON for {path}."


def refresh_data(base_url: str) -> tuple[dict | None, dict | None, list, list[str]]:
    errors: list[str] = []

    metrics, metrics_error = fetch_json("/metrics", base_url)
    if metrics_error:
        errors.append(metrics_error)

    summary, summary_error = fetch_json("/summary", base_url)
    if summary_error:
        errors.append(summary_error)

    history_payload, history_error = fetch_json("/history", base_url)
    if history_error:
        errors.append(history_error)

    history = []
    if history_payload:
        history = history_payload.get("history", []) or []

    return metrics, summary, history, errors


def history_frame(history: list[dict]) -> pd.DataFrame:
    rows = []
    for item in history:
        data = item.get("data", {}) or {}
        connection = item.get("connection", {}) or {}
        rows.append(
            {
                "timestamp": item.get("timestamp"),
                "cpu": safe_number(data.get("cpu")),
                "memory": safe_number(data.get("memory")),
                "ram_usage": safe_number(data.get("ram_usage")),
                "disk": safe_number(data.get("disk")),
                "network": safe_number(data.get("network")),
                "network_in": safe_number(data.get("network_in")),
                "network_out": safe_number(data.get("network_out")),
                "latency": safe_number(data.get("latency")),
                "cost_optimization": safe_number(data.get("cost_optimization")),
                "process_count": safe_number(data.get("process_count")),
                "anomaly_score": safe_number(item.get("anomaly_score")),
                "status": item.get("status", "healthy"),
                "log_level": item.get("log_level", "INFO"),
                "data_source": item.get("data_source", "Unknown"),
                "connection_status": connection.get("status", "warning"),
                "alert_count": safe_number(item.get("alert_count")),
            }
        )

    frame = pd.DataFrame(rows)
    if frame.empty:
        return frame
    frame["timestamp"] = pd.to_datetime(frame["timestamp"], errors="coerce")
    frame = frame.dropna(subset=["timestamp"]).sort_values("timestamp")
    frame["label"] = frame["timestamp"].dt.strftime("%H:%M:%S")
    return frame


def render_metric_card(label: str, value: str, meta: str, percent: float, color: str):
    width = max(0.0, min(percent, 100.0))
    st.markdown(
        f"""
        <div class="metric-card">
            <div class="metric-label">{label}</div>
            <div class="metric-value" style="color:{color}">{value}</div>
            <div class="metric-meta">{meta}</div>
            <div class="metric-bar"><span style="width:{width}%; background:{color};"></span></div>
        </div>
        """,
        unsafe_allow_html=True,
    )


if "backend_url" not in st.session_state:
    st.session_state.backend_url = DEFAULT_BACKEND_URL
if "poll_seconds" not in st.session_state:
    st.session_state.poll_seconds = DEFAULT_POLL_SECONDS
if "auto_refresh" not in st.session_state:
    st.session_state.auto_refresh = True
if "last_metrics" not in st.session_state:
    st.session_state.last_metrics = None
if "last_summary" not in st.session_state:
    st.session_state.last_summary = None
if "last_history" not in st.session_state:
    st.session_state.last_history = []
if "errors" not in st.session_state:
    st.session_state.errors = []
if "last_updated" not in st.session_state:
    st.session_state.last_updated = None

with st.sidebar:
    st.markdown("## CloudScope")
    st.caption("Cloud monitoring and anomaly detection")
    st.divider()
    st.session_state.backend_url = st.text_input(
        "Backend URL",
        value=st.session_state.backend_url,
        help="Used for all API requests from the dashboard.",
    ).rstrip("/")
    st.session_state.auto_refresh = st.toggle(
        "Auto refresh",
        value=st.session_state.auto_refresh,
    )
    st.session_state.poll_seconds = st.slider(
        "Polling interval (seconds)",
        min_value=3,
        max_value=20,
        value=st.session_state.poll_seconds,
    )
    refresh_now = st.button("Refresh now", use_container_width=True)
    st.divider()
    st.caption("Expected endpoints: /health, /metrics, /history, /summary")

should_refresh = (
    refresh_now
    or st.session_state.last_metrics is None
    or st.session_state.auto_refresh
)

if should_refresh:
    with st.spinner("Refreshing monitoring data..."):
        metrics, summary, history, errors = refresh_data(st.session_state.backend_url)

    if metrics:
        st.session_state.last_metrics = metrics
    if summary:
        st.session_state.last_summary = summary
    if history:
        st.session_state.last_history = history
    st.session_state.errors = errors
    st.session_state.last_updated = datetime.now()

metrics = st.session_state.last_metrics
summary = st.session_state.last_summary
history = st.session_state.last_history

top_left, top_right = st.columns([2.6, 1.2])
with top_left:
    st.markdown(
        """
        <div class="hero">
            <div class="eyebrow">Realtime Cloud Observability</div>
            <div class="hero-title">CloudScope Dashboard</div>
            <div class="hero-subtitle">
                Unified live metrics, anomaly scoring, alerts, and history tracking for your cloud estate.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
with top_right:
    status = (metrics or {}).get("status", "healthy")
    connection = (metrics or {}).get("connection", {}) or {}
    data_source_label = (metrics or {}).get("data_source", "Unknown")
    st.markdown('<div class="panel">', unsafe_allow_html=True)
    st.markdown('<div class="section-title">Cluster Status</div>', unsafe_allow_html=True)
    st.markdown(status_badge(status), unsafe_allow_html=True)
    st.markdown(
        f'<div class="tiny" style="margin-top:0.8rem">Data source: <span class="mono">{data_source_label}</span></div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        f'<div class="tiny">Connection: {connection.get("label", connection.get("status", "Unknown"))}</div>',
        unsafe_allow_html=True,
    )
    timestamp_text = "No samples yet"
    if metrics and metrics.get("timestamp"):
        timestamp_text = f"Latest sample: {metrics['timestamp']}"
    st.markdown(
        f'<div class="tiny" style="margin-top:0.9rem">{timestamp_text}</div>',
        unsafe_allow_html=True,
    )
    if st.session_state.last_updated:
        st.markdown(
            f'<div class="tiny">Dashboard refresh: {st.session_state.last_updated.strftime("%H:%M:%S")}</div>',
            unsafe_allow_html=True,
        )
    st.markdown(
        f'<div class="tiny">Backend: <span class="mono">{st.session_state.backend_url}</span></div>',
        unsafe_allow_html=True,
    )
    if connection.get("target"):
        st.markdown(
            f'<div class="tiny">Target: <span class="mono">{connection.get("target")}</span></div>',
            unsafe_allow_html=True,
        )
    if connection.get("latency_ms") is not None:
        st.markdown(
            f'<div class="tiny">SSH latency: {safe_number(connection.get("latency_ms")):.1f} ms</div>',
            unsafe_allow_html=True,
        )
    st.markdown("</div>", unsafe_allow_html=True)

if st.session_state.errors:
    for error in st.session_state.errors:
        st.error(error)

if metrics and metrics.get("collection_error"):
    st.warning(metrics["collection_error"])

if not metrics or not summary:
    st.warning("No backend data available yet. Check the backend URL and API health, then refresh.")
    if st.session_state.auto_refresh:
        time.sleep(st.session_state.poll_seconds)
        st.rerun()
    st.stop()

data = metrics.get("data", {}) or {}
alerts = metrics.get("alerts", []) or []
frame = history_frame(history)

cpu = safe_number(data.get("cpu"))
memory = safe_number(data.get("memory"))
ram_usage = safe_number(data.get("ram_usage"))
ram_used_gb = safe_number(data.get("ram_used_gb"))
ram_total_gb = safe_number(data.get("ram_total_gb"), 64)
disk = safe_number(data.get("disk"))
network = safe_number(data.get("network"))
network_in = safe_number(data.get("network_in"))
network_out = safe_number(data.get("network_out"))
latency = safe_number(data.get("latency"))
cost_optimization = safe_number(data.get("cost_optimization"))
anomaly = safe_number(metrics.get("anomaly_score"))
log_level = metrics.get("log_level", "INFO")
memory_alert_count = len(metrics.get("memory_alerts", []) or [])
process_count = int(safe_number(data.get("process_count")))
connection = metrics.get("connection", {}) or {}

metric_cols = st.columns(5)
with metric_cols[0]:
    render_metric_card(
        "CPU usage",
        f"{cpu:.0f}%",
        f"Average: {safe_number(summary.get('cpu', {}).get('avg')):.1f}%",
        cpu,
        severity_color(cpu, 75, 90),
    )
with metric_cols[1]:
    render_metric_card(
        "Memory usage",
        f"{memory:.0f}%",
        f"RAM {ram_used_gb:.1f} / {ram_total_gb:.0f} GB",
        memory,
        severity_color(memory, 80, 90),
    )
with metric_cols[2]:
    render_metric_card(
        "Disk usage",
        f"{disk:.0f}%",
        f"Processes {process_count}",
        disk,
        severity_color(disk, 85, 90),
    )
with metric_cols[3]:
    render_metric_card(
        "Network throughput",
        f"{network:.1f} MB/s",
        f"In {network_in:.1f} | Out {network_out:.1f}",
        min(network / 9.5, 100),
        severity_color(network, 450, 700),
    )
with metric_cols[4]:
    render_metric_card(
        "Latency",
        f"{latency:.0f} ms",
        f"Current log level: {log_level}",
        latency / 8,
        severity_color(latency, 150, 300),
    )

signal_cols = st.columns([1.1, 1.1, 1.1, 1.1, 1.6])
with signal_cols[0]:
    st.markdown(
        f"""
        <div class="signal-card">
            <div class="signal-value" style="color:{severity_color(anomaly, 30, 60)}">{anomaly:.1f}</div>
            <div class="signal-label">Anomaly score</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
with signal_cols[1]:
    st.markdown(
        f"""
        <div class="signal-card">
            <div class="signal-value" style="color:{severity_color(cost_optimization, 45, 25, reverse=True)}">{cost_optimization:.0f}%</div>
            <div class="signal-label">Cost optimization</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
with signal_cols[2]:
    st.markdown(
        f"""
        <div class="signal-card">
            <div class="signal-value" style="color:{severity_color(ram_usage, 80, 90)}">{ram_usage:.0f}%</div>
            <div class="signal-label">RAM usage</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
with signal_cols[3]:
    st.markdown(
        f"""
        <div class="signal-card">
            <div class="signal-value" style="color:{severity_color(memory_alert_count, 1, 2)}">{memory_alert_count}</div>
            <div class="signal-label">Memory alerts</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
with signal_cols[4]:
    st.markdown('<div class="panel">', unsafe_allow_html=True)
    st.markdown('<div class="section-title">Tracking Summary</div>', unsafe_allow_html=True)
    st.write(f"History samples: `{len(frame)}`")
    st.write(f"Open alerts: `{metrics.get('alert_count', 0)}`")
    st.write(f"Simulator mode: `{data.get('mode', 'normal')}`")
    st.write(f"Connection: `{connection.get('label', connection.get('status', 'Unknown'))}`")
    st.write(f"Timestamp: `{metrics.get('timestamp', '-')}`")
    st.markdown("</div>", unsafe_allow_html=True)

chart_left, chart_right = st.columns([1.8, 1.2])
with chart_left:
    st.markdown('<div class="panel">', unsafe_allow_html=True)
    st.markdown('<div class="section-title">Infrastructure Trends</div>', unsafe_allow_html=True)
    if not frame.empty:
        trend_df = frame.set_index("label")[
            ["cpu", "memory", "ram_usage", "disk", "network", "latency"]
        ]
        st.line_chart(trend_df, height=300, use_container_width=True)
    else:
        st.info("History will appear here as soon as samples are available.")
    st.markdown("</div>", unsafe_allow_html=True)

with chart_right:
    st.markdown('<div class="panel">', unsafe_allow_html=True)
    st.markdown('<div class="section-title">Risk and Efficiency</div>', unsafe_allow_html=True)
    if not frame.empty:
        risk_df = frame.set_index("label")[["anomaly_score", "cost_optimization", "alert_count"]]
        st.area_chart(risk_df, height=300, use_container_width=True)
    else:
        st.info("Risk scoring chart is waiting for backend history.")
    st.markdown("</div>", unsafe_allow_html=True)

lower_left, lower_right = st.columns([1.15, 1.85])
with lower_left:
    st.markdown('<div class="panel">', unsafe_allow_html=True)
    st.markdown('<div class="section-title">Alerts Panel</div>', unsafe_allow_html=True)
    if alerts:
        for alert in alerts:
            severity = alert.get("severity", "warning")
            unit = alert.get("unit", "")
            value = alert.get("value", "-")
            message = alert.get("message", "Alert")
            metric = alert.get("metric", "metric").replace("_", " ").title()
            st.markdown(
                f"""
                <div class="alert-card alert-{severity}">
                    <strong>{severity.upper()}</strong><br/>
                    {message}<br/>
                    <span class="tiny">{metric}: {value}{unit}</span>
                </div>
                """,
                unsafe_allow_html=True,
            )
    else:
        st.success("No active alerts. System is operating within configured thresholds.")
    st.markdown("</div>", unsafe_allow_html=True)

with lower_right:
    st.markdown('<div class="panel">', unsafe_allow_html=True)
    st.markdown('<div class="section-title">Recent History Table</div>', unsafe_allow_html=True)
    if not frame.empty:
        table = frame[
            [
                "timestamp",
                "status",
                "log_level",
                "cpu",
                "memory",
                "ram_usage",
                "disk",
                "network",
                "network_in",
                "network_out",
                "latency",
                "process_count",
                "cost_optimization",
                "anomaly_score",
                "data_source",
                "connection_status",
                "alert_count",
            ]
        ].tail(12).copy()
        table["timestamp"] = table["timestamp"].dt.strftime("%Y-%m-%d %H:%M:%S")
        st.dataframe(table, use_container_width=True, hide_index=True)
    else:
        st.info("Recent samples will appear here after the first successful refresh.")
    st.markdown("</div>", unsafe_allow_html=True)

if st.session_state.auto_refresh:
    time.sleep(st.session_state.poll_seconds)
    st.rerun()
