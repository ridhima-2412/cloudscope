# main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime, timezone
from collections import deque
import random
import math

app = FastAPI(
    title="CloudScope API",
    description="Cloud Infrastructure Monitoring Dashboard",
    version="2.0.0"
)

# ── CORS (allows your frontend to call this API) ──────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],          # tighten to your frontend URL in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── In-memory metric history (last 20 snapshots) ──────────────────────────────
metric_history: deque = deque(maxlen=20)

# ── Helpers ───────────────────────────────────────────────────────────────────

def _clamp(value: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, value))


def generate_metrics() -> dict:
    """
    Simulate system metrics.
    'attack' mode spikes CPU/memory to mimic an incident.
    """
    mode = random.choice(["normal", "normal", "normal", "attack"])  # 25 % attack chance

    if mode == "normal":
        cpu     = random.randint(18, 62)
        memory  = random.randint(28, 68)
        disk    = random.randint(40, 75)
        network = random.randint(10, 300)   # MB/s
        latency = random.randint(12, 80)    # ms
    else:
        cpu     = random.randint(78, 100)
        memory  = random.randint(74, 97)
        disk    = random.randint(70, 95)
        network = random.randint(400, 950)
        latency = random.randint(200, 800)

    # Small random drift so repeated calls feel alive
    cpu     = _clamp(cpu     + random.randint(-3, 3), 0, 100)
    memory  = _clamp(memory  + random.randint(-2, 2), 0, 100)

    return {
        "mode":    mode,
        "cpu":     cpu,
        "memory":  memory,
        "disk":    disk,
        "network": network,   # MB/s outbound
        "latency": latency,   # ms avg response time
    }


def build_alerts(data: dict) -> list[dict]:
    """
    Return a list of alert objects (severity + message).
    Multiple alerts can fire simultaneously.
    """
    alerts = []

    if data["cpu"] >= 90:
        alerts.append({"severity": "critical", "message": "CPU critically high", "metric": "cpu", "value": data["cpu"]})
    elif data["cpu"] >= 75:
        alerts.append({"severity": "warning",  "message": "CPU usage elevated",  "metric": "cpu", "value": data["cpu"]})

    if data["memory"] >= 90:
        alerts.append({"severity": "critical", "message": "Memory critically high", "metric": "memory", "value": data["memory"]})
    elif data["memory"] >= 80:
        alerts.append({"severity": "warning",  "message": "High memory usage",     "metric": "memory", "value": data["memory"]})

    if data["disk"] >= 85:
        alerts.append({"severity": "warning", "message": "Disk usage approaching limit", "metric": "disk", "value": data["disk"]})

    if data["latency"] >= 300:
        alerts.append({"severity": "critical", "message": "Response latency critical", "metric": "latency", "value": data["latency"]})
    elif data["latency"] >= 150:
        alerts.append({"severity": "warning",  "message": "Elevated response latency", "metric": "latency", "value": data["latency"]})

    return alerts


def anomaly_score(data: dict) -> float:
    """
    Lightweight anomaly score (0–100).
    Weighted average of how far each metric is into the 'danger zone'.
    """
    weights = {"cpu": 0.35, "memory": 0.30, "disk": 0.15, "latency": 0.20}
    thresholds = {"cpu": 70, "memory": 70, "disk": 75, "latency": 120}
    maxima     = {"cpu": 100, "memory": 100, "disk": 100, "latency": 800}

    score = 0.0
    for key, w in weights.items():
        val = data[key]
        lo  = thresholds[key]
        hi  = maxima[key]
        if val > lo:
            score += w * min((val - lo) / (hi - lo), 1.0)

    return round(score * 100, 1)


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/", tags=["General"])
def home():
    return {
        "message": "CloudScope API is running 🚀",
        "version": "2.0.0",
        "docs":    "/docs",
    }


@app.get("/health", tags=["General"])
def health():
    """Standard liveness probe — returns 200 if the API is up."""
    return {"status": "ok", "timestamp": datetime.now(timezone.utc).isoformat()}


@app.get("/metrics", tags=["Metrics"])
def get_metrics():
    """
    Returns a fresh snapshot of simulated system metrics,
    along with alerts and an AI anomaly score.
    """
    data      = generate_metrics()
    alerts    = build_alerts(data)
    a_score   = anomaly_score(data)

    snapshot = {
        "timestamp":     datetime.now(timezone.utc).isoformat(),
        "data":          data,
        "alerts":        alerts,
        "alert_count":   len(alerts),
        "anomaly_score": a_score,
        "status":        "critical" if any(a["severity"] == "critical" for a in alerts)
                         else "warning" if alerts
                         else "healthy",
    }

    metric_history.append(snapshot)   # store for /history
    return snapshot


@app.get("/history", tags=["Metrics"])
def get_history():
    """
    Returns the last ≤20 metric snapshots — use this to power trend charts.
    """
    return {
        "count":   len(metric_history),
        "history": list(metric_history),
    }


@app.get("/summary", tags=["Metrics"])
def get_summary():
    """
    Aggregated stats across stored history — handy for KPI cards.
    """
    if not metric_history:
        return {"message": "No data yet — call /metrics first."}

    cpus      = [s["data"]["cpu"]     for s in metric_history]
    memories  = [s["data"]["memory"]  for s in metric_history]
    latencies = [s["data"]["latency"] for s in metric_history]

    return {
        "samples": len(metric_history),
        "cpu": {
            "avg": round(sum(cpus)     / len(cpus), 1),
            "max": max(cpus),
            "min": min(cpus),
        },
        "memory": {
            "avg": round(sum(memories) / len(memories), 1),
            "max": max(memories),
            "min": min(memories),
        },
        "latency": {
            "avg": round(sum(latencies) / len(latencies), 1),
            "max": max(latencies),
            "min": min(latencies),
        },
        "total_alerts": sum(s["alert_count"] for s in metric_history),
    }
