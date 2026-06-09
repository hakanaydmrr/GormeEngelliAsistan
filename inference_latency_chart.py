import json
import sys
from pathlib import Path

try:
    import matplotlib.pyplot as plt
except ImportError:
    print("matplotlib yüklü değil. Bu scripti çalıştırmak için \"pip install matplotlib\" komutunu kullanın.")
    sys.exit(1)

ROOT = Path(__file__).resolve().parent
LOG_PATH = ROOT / "latency_data.jsonl"


def load_latency_averages():
    if not LOG_PATH.exists():
        return {}

    stats = {"local_reflex": [], "cloud_cognitive": []}
    with open(LOG_PATH, "r", encoding="utf-8") as file:
        for line in file:
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            component = entry.get("component")
            ms = entry.get("ms")
            if component in stats and isinstance(ms, (int, float)):
                stats[component].append(ms)

    averages = {}
    for component, values in stats.items():
        if values:
            averages[component] = sum(values) / len(values)
    return averages


def get_chart_data():
    averages = load_latency_averages()
    labels = ["Local Reflex Layer", "Cloud Cognitive Layer"]
    colors = ["#4CAF50", "#2196F3"]

    if "local_reflex" in averages or "cloud_cognitive" in averages:
        local_latency = averages.get("local_reflex", 32)
        cloud_latency = averages.get("cloud_cognitive", 2500)
        return labels, [local_latency, cloud_latency], colors, averages

    return labels, [32, 2500], colors, {}


labels, latencies, colors, averages = get_chart_data()
plt.figure(figsize=(8, 5))
bars = plt.bar(labels, latencies, color=colors, edgecolor="black")

for ix, bar in enumerate(bars):
    yval = bar.get_height()
    label_text = f"{yval:.0f} ms"
    plt.text(bar.get_x() + bar.get_width() / 2, yval + max(latencies) * 0.02, label_text, ha="center", va="bottom", fontsize=11)

subtitle = "Gerçek proje verisinden hesaplandı." if averages else "Veri yok, varsayılan değerler kullanıldı."
plt.title("Inference Latency Comparison")
plt.suptitle(subtitle, fontsize=10, alpha=0.8)
plt.ylabel("Latency (ms)")
plt.ylim(0, max(latencies) * 1.2)
plt.grid(axis="y", linestyle="--", alpha=0.5)
plt.tight_layout()

output_path = ROOT / "inference_latency_chart.png"
plt.savefig(output_path, dpi=150)
print(f"Saved chart to {output_path}")
if averages:
    print(f"Averages used: {averages}")
