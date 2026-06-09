import json
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
LATENCY_LOG_PATH = REPO_ROOT / "latency_data.jsonl"


def log_latency(component: str, ms: float, metadata: dict | None = None) -> None:
    entry = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "component": component,
        "ms": float(ms),
        "metadata": metadata or {}
    }
    try:
        with open(LATENCY_LOG_PATH, "a", encoding="utf-8") as log_file:
            log_file.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:
        pass


def read_latency_data() -> list[dict]:
    if not LATENCY_LOG_PATH.exists():
        return []

    entries = []
    try:
        with open(LATENCY_LOG_PATH, "r", encoding="utf-8") as log_file:
            for line in log_file:
                try:
                    payload = json.loads(line)
                    if isinstance(payload, dict):
                        entries.append(payload)
                except json.JSONDecodeError:
                    continue
    except Exception:
        return []
    return entries


def summarize_latency() -> dict[str, dict[str, float]]:
    entries = read_latency_data()
    summary: dict[str, dict[str, float]] = {}
    counts: dict[str, int] = {}
    for entry in entries:
        component = entry.get("component")
        ms = entry.get("ms")
        if component is None or ms is None:
            continue
        summary.setdefault(component, 0.0)
        counts.setdefault(component, 0)
        summary[component] += float(ms)
        counts[component] += 1

    return {
        component: {
            "average": summary[component] / counts[component],
            "count": counts[component]
        }
        for component in summary
    }
