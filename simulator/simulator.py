# simulator.py
import random
import time
import signal
import sys
from datetime import datetime, timezone
from collections import deque

# ── Config (tweak without touching logic) ────────────────────────────────────
INTERVAL_SECONDS = 2
HISTORY_SIZE     = 20
ATTACK_CHANCE    = 0.25          # 25 % of ticks are "attack" mode

THRESHOLDS = {
    "cpu":     {"warning": 75,  "critical": 90},
    "memory":  {"warning": 80,  "critical": 90},
    "disk":    {"warning": 80,  "critical": 90},
    "latency": {"warning": 150, "critical": 300},
    "network": {"warning": 400, "critical": 700},
}

# ── Terminal colours (degrade gracefully on Windows) ────────────────────────
class C:
    RESET   = "\033[0m"
    BOLD    = "\033[1m"
    GREEN   = "\033[92m"
    YELLOW  = "\033[93m"
    RED     = "\033[91m"
    CYAN    = "\033[96m"
    MAGENTA = "\033[95m"
    DIM     = "\033[2m"

# ── State ────────────────────────────────────────────────────────────────────
history: deque = deque(maxlen=HISTORY_SIZE)
tick = 0

# ── Metric generation ────────────────────────────────────────────────────────
def generate_metrics(mode: str) -> dict:
    """Return a full metric snapshot for the given mode."""
    if mode == "normal":
        base = dict(cpu=random.randint(18, 62), memory=random.randint(28, 68),
                    disk=random.randint(40, 75), network=random.randint(10, 300),
                    latency=random.randint(12, 80))
    else:  # attack
        base = dict(cpu=random.randint(78, 100), memory=random.randint(74, 97),
                    disk=random.randint(70, 95),  network=random.randint(400, 950),
                    latency=random.randint(200, 800))

    # Small random drift so values feel alive between ticks
    base["cpu"]    = _clamp(base["cpu"]    + random.randint(-3, 3), 0, 100)
    base["memory"] = _clamp(base["memory"] + random.randint(-2, 2), 0, 100)
    return base


def _clamp(val: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, val))

# ── Alert engine ─────────────────────────────────────────────────────────────
def evaluate_alerts(metrics: dict) -> list[dict]:
    """Return alert objects for every threshold breach (all metrics, same tick)."""
    alerts = []
    for metric, levels in THRESHOLDS.items():
        val = metrics.get(metric, 0)
        if val >= levels["critical"]:
            alerts.append({"metric": metric, "value": val, "severity": "critical"})
        elif val >= levels["warning"]:
            alerts.append({"metric": metric, "value": val, "severity": "warning"})
    return alerts

# ── Anomaly score ─────────────────────────────────────────────────────────────
def anomaly_score(metrics: dict) -> float:
    """
    Weighted score 0–100 based on how far each metric is past its warning threshold.
    Higher = more anomalous.
    """
    weights  = {"cpu": 0.35, "memory": 0.30, "disk": 0.15, "latency": 0.15, "network": 0.05}
    maximums = {"cpu": 100,  "memory": 100,  "disk": 100,  "latency": 800,  "network": 950}

    score = 0.0
    for key, w in weights.items():
        val = metrics.get(key, 0)
        lo  = THRESHOLDS[key]["warning"]
        hi  = maximums[key]
        if val > lo:
            score += w * min((val - lo) / (hi - lo), 1.0)
    return round(score * 100, 1)

# ── Trend arrow ───────────────────────────────────────────────────────────────
def trend_arrow(metric: str, current: int) -> str:
    """↑ / ↓ / → based on last snapshot in history."""
    if not history:
        return "→"
    prev = history[-1]["metrics"].get(metric, current)
    diff = current - prev
    if diff > 3:  return f"{C.RED}↑{C.RESET}"
    if diff < -3: return f"{C.GREEN}↓{C.RESET}"
    return f"{C.DIM}→{C.RESET}"

# ── Summary over stored history ───────────────────────────────────────────────
def print_summary():
    if not history:
        return
    print(f"\n{C.BOLD}{C.CYAN}{'═'*44}{C.RESET}")
    print(f"{C.BOLD}  SESSION SUMMARY  ({len(history)} samples){C.RESET}")
    print(f"{C.CYAN}{'═'*44}{C.RESET}")
    for key in ("cpu", "memory", "disk", "latency", "network"):
        vals = [s["metrics"][key] for s in history]
        unit = "ms" if key == "latency" else ("MB/s" if key == "network" else "%")
        print(f"  {key.upper():<10}  avg {sum(vals)//len(vals):>4}{unit}  "
              f"max {max(vals):>4}{unit}  min {min(vals):>4}{unit}")
    total_alerts = sum(len(s["alerts"]) for s in history)
    print(f"\n  Total alerts fired : {total_alerts}")
    print(f"{C.CYAN}{'═'*44}{C.RESET}\n")

# ── Graceful exit ─────────────────────────────────────────────────────────────
def _handle_exit(sig, frame):
    print(f"\n{C.YELLOW}[SIMULATOR] Shutting down…{C.RESET}")
    print_summary()
    sys.exit(0)

signal.signal(signal.SIGINT,  _handle_exit)
signal.signal(signal.SIGTERM, _handle_exit)

# ── Main loop ─────────────────────────────────────────────────────────────────
def main():
    global tick
    print(f"{C.BOLD}{C.CYAN}  CloudScope Simulator v2  —  Ctrl+C to quit{C.RESET}\n")

    while True:
        tick += 1
        mode    = "attack" if random.random() < ATTACK_CHANCE else "normal"
        metrics = generate_metrics(mode)
        alerts  = evaluate_alerts(metrics)
        score   = anomaly_score(metrics)
        ts      = datetime.now(timezone.utc).strftime("%H:%M:%S UTC")

        # Store snapshot
        history.append({"tick": tick, "mode": mode, "metrics": metrics,
                         "alerts": alerts, "anomaly_score": score})

        # ── Header ────────────────────────────────────────────────────────────
        mode_colour = C.RED if mode == "attack" else C.GREEN
        print(f"{C.DIM}[{ts}  tick #{tick:04d}]{C.RESET}  "
              f"Mode: {mode_colour}{C.BOLD}{mode.upper():<8}{C.RESET}  "
              f"Anomaly score: {_score_colour(score)}{score:5.1f}/100{C.RESET}")

        # ── Metrics table ─────────────────────────────────────────────────────
        rows = [
            ("CPU",     metrics["cpu"],     "%",    "cpu"),
            ("Memory",  metrics["memory"],  "%",    "memory"),
            ("Disk",    metrics["disk"],    "%",    "disk"),
            ("Latency", metrics["latency"], "ms",   "latency"),
            ("Network", metrics["network"], "MB/s", "network"),
        ]
        for label, val, unit, key in rows:
            bar   = _bar(val, max_val=800 if key == "latency" else (950 if key == "network" else 100))
            arrow = trend_arrow(key, val)
            col   = _metric_colour(key, val)
            print(f"  {label:<10} {col}{val:>4}{unit:<5}{C.RESET} {arrow}  {bar}")

        # ── Alerts ────────────────────────────────────────────────────────────
        if alerts:
            print()
            for a in alerts:
                icon = "🔴" if a["severity"] == "critical" else "🟡"
                sev  = f"{C.RED}CRITICAL{C.RESET}" if a["severity"] == "critical" \
                       else f"{C.YELLOW}WARNING{C.RESET}"
                print(f"  {icon} [{sev}] {a['metric'].upper()} at {a['value']} — "
                      + ("Immediate attention required!" if a["severity"] == "critical"
                         else "Monitor closely."))
        else:
            print(f"  {C.GREEN}✔ All systems normal{C.RESET}")

        print(f"{C.DIM}{'─'*56}{C.RESET}\n")
        time.sleep(INTERVAL_SECONDS)


# ── Colour helpers ────────────────────────────────────────────────────────────
def _metric_colour(key: str, val: int) -> str:
    if val >= THRESHOLDS[key]["critical"]: return C.RED
    if val >= THRESHOLDS[key]["warning"]:  return C.YELLOW
    return C.GREEN

def _score_colour(score: float) -> str:
    if score >= 60: return C.RED
    if score >= 30: return C.YELLOW
    return C.GREEN

def _bar(val: int, max_val: int = 100, width: int = 16) -> str:
    filled = round((val / max_val) * width)
    pct    = val / max_val
    col    = C.RED if pct >= 0.85 else (C.YELLOW if pct >= 0.65 else C.GREEN)
    return f"{col}{'█' * filled}{'░' * (width - filled)}{C.RESET}"


if __name__ == "__main__":
    main()
