from collections import deque
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import random
import time

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import paramiko

load_dotenv()

app = FastAPI(
    title="CloudScope API",
    description="Cloud infrastructure monitoring dashboard",
    version="2.2.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

HISTORY_LIMIT = 60
SIMULATED_RAM_TOTAL_GB = 64
metric_history: deque = deque(maxlen=HISTORY_LIMIT)

LOG_LEVEL_MAP = {
    "healthy": "INFO",
    "warning": "WARN",
    "critical": "ERROR",
}

LAST_CONNECTION_STATUS = {
    "status": "warning",
    "label": "Not configured",
    "message": "EC2 monitoring is not configured. Using simulated metrics.",
    "target": "",
    "latency_ms": None,
}

LAST_NETWORK_SAMPLE = {
    "rx_bytes": None,
    "tx_bytes": None,
    "timestamp": None,
}

REMOTE_METRICS_COMMAND = """python3 - <<'PY'
import json
import os
import time

def cpu_percent():
    def sample():
        with open('/proc/stat', 'r', encoding='utf-8') as handle:
            values = list(map(int, handle.readline().split()[1:8]))
        idle = values[3] + values[4]
        total = sum(values)
        return idle, total

    idle_1, total_1 = sample()
    time.sleep(0.2)
    idle_2, total_2 = sample()
    total_delta = max(total_2 - total_1, 1)
    idle_delta = max(idle_2 - idle_1, 0)
    return round(100.0 * (1.0 - (idle_delta / total_delta)), 1)

meminfo = {}
with open('/proc/meminfo', 'r', encoding='utf-8') as handle:
    for line in handle:
        key, value = line.split(':', 1)
        meminfo[key] = int(value.strip().split()[0])

mem_total_gb = round(meminfo.get('MemTotal', 0) / 1024 / 1024, 1)
mem_available_gb = round(meminfo.get('MemAvailable', meminfo.get('MemFree', 0)) / 1024 / 1024, 1)
ram_used_gb = round(max(mem_total_gb - mem_available_gb, 0), 1)
memory_pct = round((ram_used_gb / mem_total_gb) * 100, 1) if mem_total_gb else 0.0

fs = os.statvfs('/')
disk_total = fs.f_blocks * fs.f_frsize
disk_free = fs.f_bavail * fs.f_frsize
disk_used = max(disk_total - disk_free, 0)
disk_pct = round((disk_used / disk_total) * 100, 1) if disk_total else 0.0

rx_bytes = 0
tx_bytes = 0
with open('/proc/net/dev', 'r', encoding='utf-8') as handle:
    for line in handle.readlines()[2:]:
        iface, stats = line.split(':', 1)
        iface = iface.strip()
        if iface == 'lo':
            continue
        fields = stats.split()
        rx_bytes += int(fields[0])
        tx_bytes += int(fields[8])

process_count = sum(1 for name in os.listdir('/proc') if name.isdigit())
load_1, load_5, load_15 = os.getloadavg()

print(json.dumps({
    "cpu": cpu_percent(),
    "memory": memory_pct,
    "ram_usage": memory_pct,
    "ram_used_gb": ram_used_gb,
    "ram_total_gb": mem_total_gb,
    "disk": disk_pct,
    "network_in_bytes_total": rx_bytes,
    "network_out_bytes_total": tx_bytes,
    "process_count": process_count,
    "load_average": {
        "1m": round(load_1, 2),
        "5m": round(load_5, 2),
        "15m": round(load_15, 2),
    }
}))
PY"""


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _round(value: float, digits: int = 1) -> float:
    return round(value, digits)


def _truthy(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _env(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def monitoring_enabled() -> bool:
    return _truthy(_env("EC2_MONITORING_ENABLED"))


def ssh_key_path() -> str:
    configured = _env("EC2_SSH_KEY_PATH")
    if configured:
        return configured
    return _env("EC2_SSH_KEY_PATH_HOST")


def monitoring_target() -> str:
    display_name = _env("EC2_DISPLAY_NAME")
    host = _env("EC2_HOST")
    return display_name or host or "AWS EC2"


def load_private_key(path: str):
    key_loaders = (
        paramiko.RSAKey.from_private_key_file,
        paramiko.Ed25519Key.from_private_key_file,
        paramiko.ECDSAKey.from_private_key_file,
    )
    last_error = None
    for loader in key_loaders:
        try:
            return loader(path)
        except Exception as exc:
            last_error = exc
    if last_error:
        raise last_error
    raise RuntimeError("Unable to load SSH private key.")


def config_status() -> dict:
    host = _env("EC2_HOST")
    username = _env("EC2_USERNAME")
    region = _env("EC2_REGION", "us-east-1")
    key_path = ssh_key_path()
    password = _env("EC2_SSH_PASSWORD")
    port = int(_env("EC2_PORT", "22") or "22")

    return {
        "enabled": monitoring_enabled(),
        "region": region,
        "host": host,
        "username": username,
        "port": port,
        "key_path": key_path,
        "has_password": bool(password),
        "configured": bool(host and username and (key_path or password)),
    }


def generate_simulated_metrics() -> dict:
    mode = random.choice(["normal", "normal", "normal", "attack"])

    if mode == "attack":
        cpu = random.randint(78, 100)
        memory = random.randint(74, 97)
        disk = random.randint(70, 95)
        network = random.randint(400, 950)
        latency = random.randint(180, 800)
        process_count = random.randint(180, 260)
    else:
        cpu = random.randint(18, 62)
        memory = random.randint(28, 68)
        disk = random.randint(40, 75)
        network = random.randint(10, 300)
        latency = random.randint(12, 80)
        process_count = random.randint(90, 165)

    cpu = int(_clamp(cpu + random.randint(-3, 3), 0, 100))
    memory = int(_clamp(memory + random.randint(-2, 2), 0, 100))
    disk = int(_clamp(disk + random.randint(-2, 3), 0, 100))
    network = int(_clamp(network + random.randint(-25, 25), 0, 950))
    latency = int(_clamp(latency + random.randint(-20, 20), 1, 800))

    ram_used_gb = _round(SIMULATED_RAM_TOTAL_GB * (memory / 100), 1)
    cost_optimization = _round(
        _clamp(100 - ((cpu * 0.45) + (memory * 0.35) + (disk * 0.20)), 5, 98)
    )

    return {
        "mode": mode,
        "cpu": cpu,
        "memory": memory,
        "ram_usage": memory,
        "ram_used_gb": ram_used_gb,
        "ram_total_gb": SIMULATED_RAM_TOTAL_GB,
        "disk": disk,
        "network": network,
        "network_in": _round(network * 0.55, 1),
        "network_out": _round(network * 0.45, 1),
        "latency": latency,
        "cost_optimization": cost_optimization,
        "process_count": process_count,
        "load_average": {
            "1m": _round(cpu / 32, 2),
            "5m": _round(memory / 40, 2),
            "15m": _round(disk / 55, 2),
        },
    }


def compute_network_rates(rx_bytes: int, tx_bytes: int) -> tuple[float, float, float]:
    now = time.monotonic()
    rx_rate = 0.0
    tx_rate = 0.0

    if (
        LAST_NETWORK_SAMPLE["rx_bytes"] is not None
        and LAST_NETWORK_SAMPLE["tx_bytes"] is not None
        and LAST_NETWORK_SAMPLE["timestamp"] is not None
    ):
        elapsed = max(now - LAST_NETWORK_SAMPLE["timestamp"], 0.001)
        rx_rate = max((rx_bytes - LAST_NETWORK_SAMPLE["rx_bytes"]) / elapsed / 1024 / 1024, 0)
        tx_rate = max((tx_bytes - LAST_NETWORK_SAMPLE["tx_bytes"]) / elapsed / 1024 / 1024, 0)

    LAST_NETWORK_SAMPLE["rx_bytes"] = rx_bytes
    LAST_NETWORK_SAMPLE["tx_bytes"] = tx_bytes
    LAST_NETWORK_SAMPLE["timestamp"] = now

    total_rate = rx_rate + tx_rate
    return _round(total_rate), _round(rx_rate), _round(tx_rate)


def fetch_ssh_metrics() -> tuple[dict | None, dict, str | None]:
    config = config_status()
    target = monitoring_target()

    if not config["enabled"]:
        return None, {
            "status": "warning",
            "label": "Not configured",
            "message": "EC2 monitoring is disabled. Using simulated metrics.",
            "target": target,
            "latency_ms": None,
        }, None

    if not config["configured"]:
        return None, {
            "status": "warning",
            "label": "Not configured",
            "message": "Set EC2_HOST, EC2_USERNAME, and EC2_SSH_KEY_PATH or EC2_SSH_PASSWORD.",
            "target": target,
            "latency_ms": None,
        }, "EC2 monitoring is enabled but required SSH settings are missing."

    key_path = config["key_path"]
    if key_path:
        expanded = Path(key_path).expanduser()
        if not expanded.exists():
            return None, {
                "status": "disconnected",
                "label": "Disconnected",
                "message": f"SSH key file was not found: {expanded}",
                "target": target,
                "latency_ms": None,
            }, f"SSH key file not found: {expanded}"
        key_path = str(expanded)
        private_key = load_private_key(key_path)
    else:
        private_key = None

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    started = time.monotonic()

    try:
        client.connect(
            hostname=config["host"],
            port=config["port"],
            username=config["username"],
            pkey=private_key,
            password=_env("EC2_SSH_PASSWORD") or None,
            timeout=float(_env("EC2_CONNECT_TIMEOUT", "8") or "8"),
            banner_timeout=float(_env("EC2_CONNECT_TIMEOUT", "8") or "8"),
            auth_timeout=float(_env("EC2_CONNECT_TIMEOUT", "8") or "8"),
            look_for_keys=False,
            allow_agent=False,
        )
        latency_ms = _round((time.monotonic() - started) * 1000, 1)
        _, stdout, stderr = client.exec_command(
            REMOTE_METRICS_COMMAND,
            timeout=float(_env("EC2_COMMAND_TIMEOUT", "10") or "10"),
        )
        output = stdout.read().decode("utf-8").strip()
        error_output = stderr.read().decode("utf-8").strip()
        exit_code = stdout.channel.recv_exit_status()

        if exit_code != 0:
            raise RuntimeError(error_output or "Remote metric collection command failed.")
        if not output:
            raise RuntimeError("Remote metric collection returned no output.")

        payload = json.loads(output)
        network_total, network_in, network_out = compute_network_rates(
            int(payload.get("network_in_bytes_total", 0)),
            int(payload.get("network_out_bytes_total", 0)),
        )
        cpu = _round(float(payload.get("cpu", 0)))
        memory = _round(float(payload.get("memory", 0)))
        disk = _round(float(payload.get("disk", 0)))
        ram_total_gb = _round(float(payload.get("ram_total_gb", 0)))
        ram_used_gb = _round(float(payload.get("ram_used_gb", 0)))
        latency = max(latency_ms, 1.0)
        cost_optimization = _round(
            _clamp(100 - ((cpu * 0.45) + (memory * 0.35) + (disk * 0.20)), 5, 98)
        )

        metrics = {
            "mode": "live",
            "cpu": cpu,
            "memory": memory,
            "ram_usage": memory,
            "ram_used_gb": ram_used_gb,
            "ram_total_gb": ram_total_gb,
            "disk": disk,
            "network": network_total,
            "network_in": network_in,
            "network_out": network_out,
            "latency": _round(latency),
            "cost_optimization": cost_optimization,
            "process_count": int(payload.get("process_count", 0)),
            "load_average": payload.get("load_average", {}),
        }

        connection = {
            "status": "connected",
            "label": "Connected",
            "message": f"Live metrics collected from {target} over SSH.",
            "target": target,
            "latency_ms": latency_ms,
        }
        return metrics, connection, None
    except Exception as exc:
        connection = {
            "status": "disconnected",
            "label": "Disconnected",
            "message": f"Unable to connect to {target} over SSH.",
            "target": target,
            "latency_ms": None,
        }
        return None, connection, str(exc)
    finally:
        client.close()


def build_alerts(metrics: dict) -> list[dict]:
    alerts: list[dict] = []

    if metrics["cpu"] >= 90:
        alerts.append({"severity": "critical", "metric": "cpu", "message": "CPU critically high", "value": metrics["cpu"], "unit": "%"})
    elif metrics["cpu"] >= 75:
        alerts.append({"severity": "warning", "metric": "cpu", "message": "CPU usage elevated", "value": metrics["cpu"], "unit": "%"})

    if metrics["memory"] >= 90:
        alerts.append({"severity": "critical", "metric": "memory", "message": "Memory critically high", "value": metrics["memory"], "unit": "%"})
    elif metrics["memory"] >= 80:
        alerts.append({"severity": "warning", "metric": "memory", "message": "High memory usage", "value": metrics["memory"], "unit": "%"})

    if metrics["disk"] >= 90:
        alerts.append({"severity": "critical", "metric": "disk", "message": "Disk usage critical", "value": metrics["disk"], "unit": "%"})
    elif metrics["disk"] >= 85:
        alerts.append({"severity": "warning", "metric": "disk", "message": "Disk usage approaching limit", "value": metrics["disk"], "unit": "%"})

    if metrics["network"] >= 700:
        alerts.append({"severity": "critical", "metric": "network", "message": "Network throughput spike detected", "value": metrics["network"], "unit": "MB/s"})
    elif metrics["network"] >= 450:
        alerts.append({"severity": "warning", "metric": "network", "message": "Network traffic elevated", "value": metrics["network"], "unit": "MB/s"})

    if metrics["latency"] >= 300:
        alerts.append({"severity": "critical", "metric": "latency", "message": "Response latency critical", "value": metrics["latency"], "unit": "ms"})
    elif metrics["latency"] >= 150:
        alerts.append({"severity": "warning", "metric": "latency", "message": "Elevated SSH latency", "value": metrics["latency"], "unit": "ms"})

    if metrics["cost_optimization"] <= 25:
        alerts.append({"severity": "warning", "metric": "cost_optimization", "message": "Cost efficiency has dropped", "value": metrics["cost_optimization"], "unit": "%"})

    return alerts


def anomaly_score(metrics: dict) -> float:
    weights = {"cpu": 0.30, "memory": 0.25, "disk": 0.15, "latency": 0.20, "network": 0.10}
    thresholds = {"cpu": 70, "memory": 70, "disk": 75, "latency": 120, "network": 350}
    maxima = {"cpu": 100, "memory": 100, "disk": 100, "latency": 800, "network": 950}

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
    data, connection, collection_error = fetch_ssh_metrics()
    source_type = "aws_ec2"
    source_label = "AWS EC2 via SSH"
    collection_method = "ssh"

    if data is None:
        data = generate_simulated_metrics()
        source_type = "simulated"
        source_label = "Simulated fallback"
        collection_method = "generator"
        if connection["status"] == "connected":
            connection["status"] = "warning"
            connection["label"] = "Warning"

    alerts = build_alerts(data)
    score = anomaly_score(data)
    status = determine_status(alerts)
    timestamp = _utc_now()

    if connection["status"] == "disconnected" and status == "healthy":
        log_level = "ERROR"
    else:
        log_level = LOG_LEVEL_MAP[status]

    snapshot = {
        "timestamp": timestamp,
        "data": data,
        "alerts": alerts,
        "alert_count": len(alerts),
        "memory_alerts": [alert for alert in alerts if alert["metric"] in {"memory", "ram_usage"}],
        "anomaly_score": score,
        "status": status,
        "log_level": log_level,
        "data_source": source_label,
        "data_source_type": source_type,
        "collection_method": collection_method,
        "connection": connection,
        "collection_error": collection_error,
    }
    LAST_CONNECTION_STATUS.update(connection)
    metric_history.append(snapshot)
    return snapshot


def seed_count() -> int:
    return 1 if monitoring_enabled() else 18


def ensure_history() -> None:
    while len(metric_history) < seed_count():
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
        "monitoring_enabled": monitoring_enabled(),
        "target": monitoring_target(),
        "region": config_status()["region"],
    }


@app.get("/health", tags=["General"])
def health():
    return {"status": "ok", "timestamp": _utc_now()}


@app.get("/connection", tags=["General"])
def connection_status():
    config = config_status()
    return {
        "enabled": config["enabled"],
        "configured": config["configured"],
        "region": config["region"],
        "target": monitoring_target(),
        "method": "ssh",
        "connection": LAST_CONNECTION_STATUS,
        "timestamp": _utc_now(),
    }


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
        "data_source": latest["data_source"],
        "data_source_type": latest["data_source_type"],
        "collection_method": latest["collection_method"],
        "connection": latest["connection"],
        "cpu": _series("cpu"),
        "memory": _series("memory"),
        "ram_usage": _series("ram_usage"),
        "disk": _series("disk"),
        "network": _series("network"),
        "latency": _series("latency"),
        "cost_optimization": _series("cost_optimization"),
    }
