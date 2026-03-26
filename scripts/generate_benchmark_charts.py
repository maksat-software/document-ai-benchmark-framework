from pathlib import Path
import matplotlib.pyplot as plt

OUTPUT_DIR = Path("benchmark_charts")
OUTPUT_DIR.mkdir(exist_ok=True)

results = {
    "Azure DI": {
        "datasets": ["Easy", "Medium", "Hard"],
        "accuracy": [100, 92, 48],
        "exact_match": [100, 60, 0],
        "hitl": [0, 0, 60],
        "latency": [5600.8, 5613.4, 5683.4],
        "cost": [0.01, 0.01, 0.01],
    },
    "GPT-5.4": {
        "datasets": ["Easy", "Medium", "Hard"],
        "accuracy": [100, 100, 0],
        "exact_match": [100, 100, 0],
        "hitl": [0, 0, 100],
        "latency": [1807.4, 1397.2, 0],
        "cost": [0.03, 0.03, 0.03],
    },
    "Claude Sonnet 4.6": {
        "datasets": ["Easy", "Medium", "Hard"],
        "accuracy": [100, 96, 0],
        "exact_match": [100, 80, 0],
        "hitl": [0, 0, 100],
        "latency": [2101.8, 1747.4, 0],
        "cost": [0.03, 0.03, 0.03],
    },
}

datasets = ["Easy", "Medium", "Hard"]


def plot_metric(metric_name: str, ylabel: str, filename: str):
    plt.figure(figsize=(9, 5))
    for pipeline, vals in results.items():
        plt.plot(datasets, vals[metric_name], marker="o", label=pipeline)
    plt.title(metric_name.replace("_", " ").title())
    plt.ylabel(ylabel)
    plt.xlabel("Dataset")
    plt.legend()
    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / filename, dpi=200)
    plt.close()


def plot_latency_vs_accuracy():
    plt.figure(figsize=(7, 5))
    for pipeline, vals in results.items():
        plt.scatter(vals["latency"], vals["accuracy"], label=pipeline)
        for x, y, ds in zip(vals["latency"], vals["accuracy"], vals["datasets"]):
            plt.annotate(f"{pipeline} / {ds}", (x, y), fontsize=8)
    plt.xlabel("Latency (ms)")
    plt.ylabel("Field Accuracy (%)")
    plt.title("Latency vs Accuracy")
    plt.legend()
    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / "latency_vs_accuracy.png", dpi=200)
    plt.close()


def plot_cost_vs_accuracy():
    plt.figure(figsize=(7, 5))
    for pipeline, vals in results.items():
        plt.scatter(vals["cost"], vals["accuracy"], label=pipeline)
        for x, y, ds in zip(vals["cost"], vals["accuracy"], vals["datasets"]):
            plt.annotate(f"{pipeline} / {ds}", (x, y), fontsize=8)
    plt.xlabel("Cost per Document ($)")
    plt.ylabel("Field Accuracy (%)")
    plt.title("Cost vs Accuracy")
    plt.legend()
    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / "cost_vs_accuracy.png", dpi=200)
    plt.close()


if __name__ == "__main__":
    plot_metric("accuracy", "Field Accuracy (%)", "degradation_curve_accuracy.png")
    plot_metric("exact_match", "Exact Match (%)", "degradation_curve_exact_match.png")
    plot_metric("hitl", "HITL Rate (%)", "hitl_rate.png")
    plot_metric("latency", "Latency (ms)", "latency_by_dataset.png")
    plot_latency_vs_accuracy()
    plot_cost_vs_accuracy()
    print(f"Charts written to: {OUTPUT_DIR.resolve()}")
