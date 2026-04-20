from collections import deque
from datetime import datetime, timezone
import random

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="CloudScope API",
    description="Cloud infrastructure monitoring dashboard",
    version="2.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

HISTORY_LIMIT = 60
RAM_TOTAL_GB = 64
metric_history: deque = deque(maxlen=HISTORY_LIMIT)

LOG_LEVEL_MAP = {
    "healthy": "INFO",
    "warning": "WARN",
    "critical": "ERROR",
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _round(value: float, digits: int = 1) -> float:
    return round(value, digits)


def generate_metrics() -> dict:
    mode = random.choice(["normal", "normal", "normal", "attack"])

    if mode == "attack":
        cpu = random.randint(78, 100)
        memory = random.randint(74, 97)
        disk = random.randint(70, 95)
        network = random.randint(400, 950)
        latency = random.randint(180, 800)
    else:
        cpu = random.randint(18, 62)
        memory = random.randint(28, 68)
        disk = random.randint(40, 75)
        network = random.randint(10, 300)
        latency = random.randint(12, 80)

    cpu = int(_clamp(cpu + random.randint(-3, 3), 0, 100))
    memory = int(_clamp(memory + random.randint(-2, 2), 0, 100))
    disk = int(_clamp(disk + random.randint(-2, 3), 0, 100))
    network = int(_clamp(network + random.randint(-25, 25), 0, 950))
    latency = int(_clamp(latency + random.randint(-20, 20), 1, 800))

    ram_used_gb = _round(RAM_TOTAL_GB * (memory / 100), 1)
    cost_optimization = _round(
        _clamp(100 - ((cpu * 0.45) + (memory * 0.35) + (disk * 0.20)), 5, 98)
    )

    return {
        "mode": mode,
        "cpu": cpu,
        "memory": memory,
        "ram_usage": memory,
        "ram_used_gb": ram_used_gb,
        "ram_total_gb": RAM_TOTAL_GB,
        "disk": disk,
        "network": network,
        "latency": latency,
        "cost_optimization": cost_optimization,
    }


def build_alerts(metrics: dict) -> list[dict]:
    alerts: list[dict] = []

    if metrics["cpu"] >= 90:
        alerts.append(
            {
                "severity": "critical",
                "metric": "cpu",
                "message": "CPU critically high",
                "value": metrics["cpu"],
                "unit": "%",
            }
        )
    elif metrics["cpu"] >= 75:
        alerts.append(
            {
                "severity": "warning",
                "metric": "cpu",
                "message": "CPU usage elevated",
                "value": metrics["cpu"],
                "unit": "%",
            }
        )

    if metrics["memory"] >= 90:
        alerts.append(
            {
                "severity": "critical",
                "metric": "memory",
                "message": "Memory critically high",
                "value": metrics["memory"],
                "unit": "%",
            }
        )
    elif metrics["memory"] >= 80:
        alerts.append(
            {
                "severity": "warning",
                "metric": "memory",
                "message": "High memory usage",
                "value": metrics["memory"],
                "unit": "%",
            }
        )

    if metrics["disk"] >= 90:
        alerts.append(
            {
                "severity": "critical",
                "metric": "disk",
                "message": "Disk usage critical",
                "value": metrics["disk"],
                "unit": "%",
            }
        )
    elif metrics["disk"] >= 85:
        alerts.append(
            {
                "severity": "warning",
                "metric": "disk",
                "message": "Disk usage approaching limit",
                "value": metrics["disk"],
                "unit": "%",
            }
        )

    if metrics["network"] >= 700:
        alerts.append(
            {
                "severity": "critical",
                "metric": "network",
                "message": "Network throughput spike detected",
                "value": metrics["network"],
                "unit": "MB/s",
            }
        )
    elif metrics["network"] >= 450:
        alerts.append(
            {
                "severity": "warning",
                "metric": "network",
                "message": "Network traffic elevated",
                "value": metrics["network"],
                "unit": "MB/s",
            }
        )

    if metrics["latency"] >= 300:
        alerts.append(
            {
                "severity": "critical",
                "metric": "latency",
                "message": "Response latency critical",
                "value": metrics["latency"],
                "unit": "ms",
            }
        )
    elif metrics["latency"] >= 150:
        alerts.append(
            {
                "severity": "warning",
                "metric": "latency",
                "message": "Elevated response latency",
                "value": metrics["latency"],
                "unit": "ms",
            }
        )

    if metrics["cost_optimization"] <= 25:
        alerts.append(
            {
                "severity": "warning",
                "metric": "cost_optimization",
                "message": "Cost efficiency has dropped",
                "value": metrics["cost_optimization"],
                "unit": "%",
            }
        )

    return alerts


def anomaly_score(metrics: dict) -> float:
    weights = {
        "cpu": 0.30,
        "memory": 0.25,
        "disk": 0.15,
        "latency": 0.20,
        "network": 0.10,
    }
    thresholds = {
        "cpu": 70,
        "memory": 70,
        "disk": 75,
        "latency": 120,
        "network": 350,
    }
    maxima = {
        "cpu": 100,
        "memory": 100,
        "disk": 100,
        "latency": 800,
        "network": 950,
    }

    score = 0.0
    for key, weight in weights.items():
        value = metrics[key]
        low = thresholds[key]
        high = maxima[key]
        if value > low:
            score += weight * min((value - low) / (high - low), 1.0)

    return _round(score * 100)


def determine_status(alerts: list[dict]) -> str:
    if any(alert["severity"] == "critical" for alert in alerts):
        return "critical"
    if alerts:
        return "warning"
    return "healthy"


def create_snapshot() -> dict:
    data = generate_metrics()
    alerts = build_alerts(data)
    score = anomaly_score(data)
    status = determine_status(alerts)
    timestamp = _utc_now()

    snapshot = {
        "timestamp": timestamp,
        "data": data,
        "alerts": alerts,
        "alert_count": len(alerts),
        "memory_alerts": [
            alert for alert in alerts if alert["metric"] in {"memory", "ram_usage"}
        ],
        "anomaly_score": score,
        "status": status,
        "log_level": LOG_LEVEL_MAP[status],
    }
    metric_history.append(snapshot)
    return snapshot


def ensure_history(seed_count: int = 18) -> None:
    while len(metric_history) < seed_count:
        create_snapshot()


def _series(metric: str) -> dict:
    values = [snapshot["data"][metric] for snapshot in metric_history]
    return {
        "current": values[-1],
        "avg": _round(sum(values) / len(values)),
        "max": max(values),
        "min": min(values),
    }


@app.get("/", tags=["General"])
def home():
    return {
        "message": "CloudScope API is running",
        "version": app.version,
        "docs": "/docs",
    }


@app.get("/health", tags=["General"])
def health():
    return {"status": "ok", "timestamp": _utc_now()}


@app.get("/metrics", tags=["Metrics"])
def get_metrics():
    return create_snapshot()


@app.get("/history", tags=["Metrics"])
def get_history():
    ensure_history()
    return {"count": len(metric_history), "history": list(metric_history)}


@app.get("/summary", tags=["Metrics"])
def get_summary():
    ensure_history()

    latest = metric_history[-1]
    return {
        "samples": len(metric_history),
        "timestamp": latest["timestamp"],
        "status": latest["status"],
        "log_level": latest["log_level"],
        "anomaly_score": latest["anomaly_score"],
        "alerts_open": latest["alert_count"],
        "cpu": _series("cpu"),
        "memory": _series("memory"),
        "ram_usage": _series("ram_usage"),
        "disk": _series("disk"),
        "network": _series("network"),
        "latency": _series("latency"),
        "cost_optimization": _series("cost_optimization"),
    }

