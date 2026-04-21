from collections import deque
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import random
import time

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
import paramiko

load_dotenv()

app = FastAPI(
    title="CloudScope API",
    description="Cloud infrastructure monitoring dashboard",
    version="3.0.0",
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

# ── How long (seconds) before we consider EC2 "gone" and fall back ───────────
HEARTBEAT_TIMEOUT_SECONDS = 60

metric_history: deque = deque(maxlen=HISTORY_LIMIT)

LOG_LEVEL_MAP = {
    "healthy": "INFO",
    "warning": "WARN",
    "critical": "ERROR",
}

# ── Last-known real data from EC2 (populated by SSH poll OR agent push) ───────
LAST_REAL_DATA: dict | None = None
LAST_REAL_DATA_TS: float | None = None        # monotonic time of last real sample
LAST_REAL_DATA_WALL: str | None = None        # human-readable UTC timestamp

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
import json, os, time

def cpu_percent():
    def sample():
        with open('/proc/stat', 'r', encoding='utf-8') as h:
            vals = list(map(int, h.readline().split()[1:8]))
        idle = vals[3] + vals[4]
        return idle, sum(vals)
    i1, t1 = sample(); time.sleep(0.2); i2, t2 = sample()
    td = max(t2-t1, 1); id_ = max(i2-i1, 0)
    return round(100.0 * (1.0 - id_/td), 1)

mem = {}
with open('/proc/meminfo', 'r', encoding='utf-8') as h:
    for line in h:
        k, v = line.split(':', 1)
        mem[k] = int(v.strip().split()[0])

tot_gb  = round(mem.get('MemTotal', 0)/1024/1024, 1)
avail   = mem.get('MemAvailable', mem.get('MemFree', 0))
avail_gb = round(avail/1024/1024, 1)
used_gb = round(max(tot_gb - avail_gb, 0), 1)
mem_pct = round((used_gb/tot_gb)*100, 1) if tot_gb else 0.0

fs = os.statvfs('/')
dt = fs.f_blocks * fs.f_frsize
df = fs.f_bavail * fs.f_frsize
disk_pct = round(max(dt-df, 0)/dt*100, 1) if dt else 0.0

rx = tx = 0
with open('/proc/net/dev', 'r', encoding='utf-8') as h:
    for line in h.readlines()[2:]:
        iface, stats = line.split(':', 1)
        if iface.strip() == 'lo': continue
        f = stats.split()
        rx += int(f[0]); tx += int(f[8])

pc = sum(1 for n in os.listdir('/proc') if n.isdigit())
l1, l5, l15 = os.getloadavg()

print(json.dumps({"cpu": cpu_percent(), "memory": mem_pct, "ram_usage": mem_pct,
    "ram_used_gb": used_gb, "ram_total_gb": tot_gb, "disk": disk_pct,
    "network_in_bytes_total": rx, "network_out_bytes_total": tx,
    "process_count": pc, "load_average": {"1m": round(l1,2),"5m": round(l5,2),"15m": round(l15,2)}}))
PY"""


# ── Helpers ───────────────────────────────────────────────────────────────────

def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()

def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))

def _round(v: float, d: int = 1) -> float:
    return round(v, d)

def _truthy(v: str | None) -> bool:
    return str(v or "").strip().lower() in {"1", "true", "yes", "on"}

def _env(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()

def monitoring_enabled() -> bool:
    return _truthy(_env("EC2_MONITORING_ENABLED"))

def ssh_key_path() -> str:
    return _env("EC2_SSH_KEY_PATH") or _env("EC2_SSH_KEY_PATH_HOST")

def monitoring_target() -> str:
    return _env("EC2_DISPLAY_NAME") or _env("EC2_HOST") or "AWS EC2"


# ── Data-source decision ──────────────────────────────────────────────────────

def _seconds_since_last_real() -> float | None:
    if LAST_REAL_DATA_TS is None:
        return None
    return time.monotonic() - LAST_REAL_DATA_TS


def data_source_mode() -> str:
    """
    Returns one of:
      'live'       – EC2 is up and SSH just succeeded
      'last_known' – EC2 went down within HEARTBEAT_TIMEOUT_SECONDS seconds
      'simulated'  – No real data ever received, or timeout exceeded
    """
    age = _seconds_since_last_real()
    if age is None:
        return "simulated"
    if age <= HEARTBEAT_TIMEOUT_SECONDS:
        return "last_known"     # will be overwritten to 'live' if SSH succeeds
    return "simulated"


# ── Simulated data ────────────────────────────────────────────────────────────

def generate_simulated_metrics() -> dict:
    mode = random.choice(["normal", "normal", "normal", "attack"])
    if mode == "attack":
        cpu, memory, disk = random.randint(78, 100), random.randint(74, 97), random.randint(70, 95)
        network, latency, process_count = random.randint(400, 950), random.randint(180, 800), random.randint(180, 260)
    else:
        cpu, memory, disk = random.randint(18, 62), random.randint(28, 68), random.randint(40, 75)
        network, latency, process_count = random.randint(10, 300), random.randint(12, 80), random.randint(90, 165)

    cpu     = int(_clamp(cpu     + random.randint(-3,  3),  0, 100))
    memory  = int(_clamp(memory  + random.randint(-2,  2),  0, 100))
    disk    = int(_clamp(disk    + random.randint(-2,  3),  0, 100))
    network = int(_clamp(network + random.randint(-25, 25), 0, 950))
    latency = int(_clamp(latency + random.randint(-20, 20), 1, 800))

    ram_used_gb      = _round(SIMULATED_RAM_TOTAL_GB * (memory / 100), 1)
    cost_optimization = _round(_clamp(100 - (cpu*0.45 + memory*0.35 + disk*0.20), 5, 98))

    return {
        "mode": mode, "cpu": cpu, "memory": memory, "ram_usage": memory,
        "ram_used_gb": ram_used_gb, "ram_total_gb": SIMULATED_RAM_TOTAL_GB,
        "disk": disk, "network": network,
        "network_in": _round(network * 0.55, 1), "network_out": _round(network * 0.45, 1),
        "latency": latency, "cost_optimization": cost_optimization,
        "process_count": process_count,
        "load_average": {"1m": _round(cpu/32,2), "5m": _round(memory/40,2), "15m": _round(disk/55,2)},
    }


# ── Network rates ─────────────────────────────────────────────────────────────

def compute_network_rates(rx_bytes: int, tx_bytes: int) -> tuple[float, float, float]:
    now = time.monotonic()
    rx_rate = tx_rate = 0.0
    if all(v is not None for v in LAST_NETWORK_SAMPLE.values()):
        elapsed = max(now - LAST_NETWORK_SAMPLE["timestamp"], 0.001)
        rx_rate = max((rx_bytes - LAST_NETWORK_SAMPLE["rx_bytes"]) / elapsed / 1024 / 1024, 0)
        tx_rate = max((tx_bytes - LAST_NETWORK_SAMPLE["tx_bytes"]) / elapsed / 1024 / 1024, 0)
    LAST_NETWORK_SAMPLE.update({"rx_bytes": rx_bytes, "tx_bytes": tx_bytes, "timestamp": now})
    total = rx_rate + tx_rate
    return _round(total), _round(rx_rate), _round(tx_rate)


# ── SSH collection ────────────────────────────────────────────────────────────

def load_private_key(path: str):
    for loader in (paramiko.RSAKey.from_private_key_file,
                   paramiko.Ed25519Key.from_private_key_file,
                   paramiko.ECDSAKey.from_private_key_file):
        try:
            return loader(path)
        except Exception:
            pass
    raise RuntimeError("Unable to load SSH private key.")


def config_status() -> dict:
    host      = _env("EC2_HOST")
    username  = _env("EC2_USERNAME")
    region    = _env("EC2_REGION", "us-east-1")
    key_path  = ssh_key_path()
    password  = _env("EC2_SSH_PASSWORD")
    port      = int(_env("EC2_PORT", "22") or "22")
    return {
        "enabled": monitoring_enabled(), "region": region,
        "host": host, "username": username, "port": port,
        "key_path": key_path, "has_password": bool(password),
        "configured": bool(host and username and (key_path or password)),
    }


def fetch_ssh_metrics() -> tuple[dict | None, dict, str | None]:
    global LAST_REAL_DATA, LAST_REAL_DATA_TS, LAST_REAL_DATA_WALL
    config = config_status()
    target = monitoring_target()

    if not config["enabled"]:
        return None, {
            "status": "warning", "label": "Not configured",
            "message": "EC2 monitoring disabled. Using simulated metrics.",
            "target": target, "latency_ms": None,
        }, None

    if not config["configured"]:
        return None, {
            "status": "warning", "label": "Not configured",
            "message": "Set EC2_HOST, EC2_USERNAME, and EC2_SSH_KEY_PATH or EC2_SSH_PASSWORD.",
            "target": target, "latency_ms": None,
        }, "EC2 monitoring enabled but SSH settings missing."

    key_path = config["key_path"]
    if key_path:
        expanded = Path(key_path).expanduser()
        if not expanded.exists():
            return None, {
                "status": "disconnected", "label": "Disconnected",
                "message": f"SSH key not found: {expanded}",
                "target": target, "latency_ms": None,
            }, f"SSH key not found: {expanded}"
        private_key = load_private_key(str(expanded))
    else:
        private_key = None

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    started = time.monotonic()

    try:
        client.connect(
            hostname=config["host"], port=config["port"], username=config["username"],
            pkey=private_key, password=_env("EC2_SSH_PASSWORD") or None,
            timeout=float(_env("EC2_CONNECT_TIMEOUT", "8") or "8"),
            banner_timeout=float(_env("EC2_CONNECT_TIMEOUT", "8") or "8"),
            auth_timeout=float(_env("EC2_CONNECT_TIMEOUT", "8") or "8"),
            look_for_keys=False, allow_agent=False,
        )
        latency_ms = _round((time.monotonic() - started) * 1000, 1)
        _, stdout, stderr = client.exec_command(
            REMOTE_METRICS_COMMAND,
            timeout=float(_env("EC2_COMMAND_TIMEOUT", "10") or "10"),
        )
        output     = stdout.read().decode("utf-8").strip()
        error_out  = stderr.read().decode("utf-8").strip()
        exit_code  = stdout.channel.recv_exit_status()

        if exit_code != 0:
            raise RuntimeError(error_out or "Remote command failed.")
        if not output:
            raise RuntimeError("Remote command returned no output.")

        payload = json.loads(output)
        net_total, net_in, net_out = compute_network_rates(
            int(payload.get("network_in_bytes_total",  0)),
            int(payload.get("network_out_bytes_total", 0)),
        )
        cpu     = _round(float(payload.get("cpu",    0)))
        memory  = _round(float(payload.get("memory", 0)))
        disk    = _round(float(payload.get("disk",   0)))
        ram_total_gb = _round(float(payload.get("ram_total_gb", 0)))
        ram_used_gb  = _round(float(payload.get("ram_used_gb",  0)))
        latency      = max(latency_ms, 1.0)
        cost_opt     = _round(_clamp(100 - (cpu*0.45 + memory*0.35 + disk*0.20), 5, 98))

        metrics = {
            "mode": "live", "cpu": cpu, "memory": memory, "ram_usage": memory,
            "ram_used_gb": ram_used_gb, "ram_total_gb": ram_total_gb, "disk": disk,
            "network": net_total, "network_in": net_in, "network_out": net_out,
            "latency": _round(latency), "cost_optimization": cost_opt,
            "process_count": int(payload.get("process_count", 0)),
            "load_average": payload.get("load_average", {}),
        }
        connection = {
            "status": "connected", "label": "Connected",
            "message": f"Live metrics from {target} via SSH.",
            "target": target, "latency_ms": latency_ms,
        }

        # ── Cache the fresh real data ─────────────────────────────────────────
        LAST_REAL_DATA      = metrics.copy()
        LAST_REAL_DATA_TS   = time.monotonic()
        LAST_REAL_DATA_WALL = _utc_now()

        return metrics, connection, None

    except Exception as exc:
        connection = {
            "status": "disconnected", "label": "Disconnected",
            "message": f"Cannot reach {target} via SSH.",
            "target": target, "latency_ms": None,
        }
        return None, connection, str(exc)
    finally:
        client.close()


# ── Agent push endpoint ───────────────────────────────────────────────────────

@app.post("/push", tags=["Agent"])
async def agent_push(request: Request):
    """
    EC2 agent calls POST /push with a JSON body containing metric fields.
    This updates the last-known cache exactly like a successful SSH poll.
    """
    global LAST_REAL_DATA, LAST_REAL_DATA_TS, LAST_REAL_DATA_WALL
    try:
        payload = await request.json()
    except Exception:
        return {"ok": False, "error": "Invalid JSON body"}

    # Compute derived fields if raw bytes provided
    if "network_in_bytes_total" in payload and "network_out_bytes_total" in payload:
        net_total, net_in, net_out = compute_network_rates(
            int(payload["network_in_bytes_total"]),
            int(payload["network_out_bytes_total"]),
        )
    else:
        net_in   = float(payload.get("network_in",  0))
        net_out  = float(payload.get("network_out", 0))
        net_total = net_in + net_out

    cpu    = _round(float(payload.get("cpu",    0)))
    memory = _round(float(payload.get("memory", 0)))
    disk   = _round(float(payload.get("disk",   0)))
    ram_total_gb = _round(float(payload.get("ram_total_gb", SIMULATED_RAM_TOTAL_GB)))
    ram_used_gb  = _round(float(payload.get("ram_used_gb",  ram_total_gb * memory / 100)))
    latency      = _round(float(payload.get("latency", 5)))
    cost_opt     = _round(_clamp(100 - (cpu*0.45 + memory*0.35 + disk*0.20), 5, 98))

    LAST_REAL_DATA = {
        "mode": "live", "cpu": cpu, "memory": memory, "ram_usage": memory,
        "ram_used_gb": ram_used_gb, "ram_total_gb": ram_total_gb, "disk": disk,
        "network": net_total, "network_in": net_in, "network_out": net_out,
        "latency": latency, "cost_optimization": cost_opt,
        "process_count": int(payload.get("process_count", 0)),
        "load_average": payload.get("load_average", {}),
    }
    LAST_REAL_DATA_TS   = time.monotonic()
    LAST_REAL_DATA_WALL = _utc_now()

    return {"ok": True, "received_at": LAST_REAL_DATA_WALL}


# ── Alerts / scoring / status ─────────────────────────────────────────────────

def build_alerts(metrics: dict) -> list[dict]:
    alerts: list[dict] = []
    checks = [
        ("cpu",               90, 75,  "%",    "CPU critically high",          "CPU usage elevated"),
        ("memory",            90, 80,  "%",    "Memory critically high",       "High memory usage"),
        ("disk",              90, 85,  "%",    "Disk usage critical",          "Disk nearing limit"),
        ("network",          700, 450, "MB/s", "Network throughput spike",     "Network traffic elevated"),
        ("latency",          300, 150, "ms",   "Response latency critical",    "Elevated latency"),
        ("cost_optimization", 25, None, "%",   None,                           "Cost efficiency dropped"),
    ]
    for metric, crit, warn, unit, crit_msg, warn_msg in checks:
        val = metrics.get(metric, 0)
        if crit_msg and val >= crit:
            alerts.append({"severity": "critical", "metric": metric, "message": crit_msg, "value": val, "unit": unit})
        elif warn is not None and val >= warn:
            alerts.append({"severity": "warning", "metric": metric, "message": warn_msg, "value": val, "unit": unit})
        elif metric == "cost_optimization" and val <= 25:
            alerts.append({"severity": "warning", "metric": metric, "message": warn_msg, "value": val, "unit": unit})
    return alerts


def anomaly_score(metrics: dict) -> float:
    weights    = {"cpu": 0.30, "memory": 0.25, "disk": 0.15, "latency": 0.20, "network": 0.10}
    thresholds = {"cpu": 70,   "memory": 70,   "disk": 75,   "latency": 120,  "network": 350}
    maxima     = {"cpu": 100,  "memory": 100,  "disk": 100,  "latency": 800,  "network": 950}
    score = 0.0
    for key, w in weights.items():
        val = metrics.get(key, 0)
        lo, hi = thresholds[key], maxima[key]
        if val > lo:
            score += w * min((val - lo) / (hi - lo), 1.0)
    return _round(score * 100)


def determine_status(alerts: list[dict]) -> str:
    if any(a["severity"] == "critical" for a in alerts):
        return "critical"
    return "warning" if alerts else "healthy"


# ── Snapshot builder ──────────────────────────────────────────────────────────

def create_snapshot() -> dict:
    global LAST_CONNECTION_STATUS
    collection_error = None

    # 1. Try SSH
    data, connection, collection_error = fetch_ssh_metrics()

    if data is not None:
        source_type   = "aws_ec2"
        source_label  = "AWS EC2 via SSH"
        collection_method = "ssh"
    else:
        # 2. Try last-known cache
        age = _seconds_since_last_real()
        if LAST_REAL_DATA is not None and age is not None and age <= HEARTBEAT_TIMEOUT_SECONDS:
            data             = LAST_REAL_DATA.copy()
            data["mode"]     = "last_known"
            source_type      = "last_known"
            age_s            = int(age)
            source_label     = f"Last known EC2 data ({age_s}s ago)"
            collection_method = "cache"
            connection = {
                "status": "disconnected",
                "label": "Offline – cached",
                "message": f"EC2 unreachable. Showing last known data from {age_s}s ago.",
                "target": monitoring_target(),
                "latency_ms": None,
                "last_real_at": LAST_REAL_DATA_WALL,
                "cache_age_seconds": age_s,
            }
        else:
            # 3. Full simulator fallback
            data             = generate_simulated_metrics()
            source_type      = "simulated"
            source_label     = "Simulated fallback"
            collection_method = "generator"
            if LAST_REAL_DATA is not None:
                reason = f"EC2 offline for >{HEARTBEAT_TIMEOUT_SECONDS}s. Simulating."
            else:
                reason = "No EC2 connection ever established. Using simulator."
            connection = {
                "status": "disconnected",
                "label": "Offline – simulated",
                "message": reason,
                "target": monitoring_target(),
                "latency_ms": None,
                "last_real_at": LAST_REAL_DATA_WALL,
                "cache_age_seconds": None,
            }

    alerts = build_alerts(data)
    score  = anomaly_score(data)
    status = determine_status(alerts)
    ts     = _utc_now()

    log_level = "ERROR" if (connection["status"] == "disconnected" and status == "healthy") \
        else LOG_LEVEL_MAP[status]

    snapshot = {
        "timestamp": ts, "data": data, "alerts": alerts,
        "alert_count": len(alerts),
        "memory_alerts": [a for a in alerts if a["metric"] in {"memory", "ram_usage"}],
        "anomaly_score": score, "status": status, "log_level": log_level,
        "data_source": source_label, "data_source_type": source_type,
        "collection_method": collection_method, "connection": connection,
        "collection_error": collection_error,
    }
    LAST_CONNECTION_STATUS = connection
    metric_history.append(snapshot)
    return snapshot


def seed_count() -> int:
    return 1 if monitoring_enabled() else 18


def ensure_history() -> None:
    while len(metric_history) < seed_count():
        create_snapshot()


def _series(metric: str) -> dict:
    vals = [s["data"][metric] for s in metric_history]
    return {"current": vals[-1], "avg": _round(sum(vals)/len(vals)), "max": max(vals), "min": min(vals)}


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/", tags=["General"])
def home():
    return {
        "message": "CloudScope API is running", "version": app.version,
        "monitoring_enabled": monitoring_enabled(), "target": monitoring_target(),
        "region": config_status()["region"],
        "heartbeat_timeout_seconds": HEARTBEAT_TIMEOUT_SECONDS,
    }


@app.get("/health", tags=["General"])
def health():
    age = _seconds_since_last_real()
    return {
        "status": "ok", "timestamp": _utc_now(),
        "last_real_data_age_seconds": round(age, 1) if age is not None else None,
        "data_source_mode": data_source_mode(),
    }


@app.get("/connection", tags=["General"])
def connection_status():
    config = config_status()
    return {
        "enabled": config["enabled"], "configured": config["configured"],
        "region": config["region"], "target": monitoring_target(), "method": "ssh",
        "connection": LAST_CONNECTION_STATUS, "timestamp": _utc_now(),
        "heartbeat_timeout_seconds": HEARTBEAT_TIMEOUT_SECONDS,
        "last_real_data_age_seconds": _seconds_since_last_real(),
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
        "samples": len(metric_history), "timestamp": latest["timestamp"],
        "status": latest["status"], "log_level": latest["log_level"],
        "anomaly_score": latest["anomaly_score"], "alerts_open": latest["alert_count"],
        "data_source": latest["data_source"], "data_source_type": latest["data_source_type"],
        "collection_method": latest["collection_method"], "connection": latest["connection"],
        "cpu": _series("cpu"), "memory": _series("memory"), "ram_usage": _series("ram_usage"),
        "disk": _series("disk"), "network": _series("network"),
        "latency": _series("latency"), "cost_optimization": _series("cost_optimization"),
    }