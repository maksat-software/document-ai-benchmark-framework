"""Report generation for benchmark results.

Writes benchmark results to JSON files and prints a summary to stdout.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def save_report(
        pipeline_name: str,
        results: dict[str, Any],
        output_dir: str = "benchmark/outputs",
) -> str:
    """Save benchmark results to a JSON file.

    Args:
        pipeline_name: Name of the pipeline (e.g. 'azure_di', 'llm').
        results: The scored results dict from scoring.score_pipeline_run.
        output_dir: Directory to write the report file.

    Returns:
        The path to the written report file.
    """
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    filename = f"{pipeline_name}_{timestamp}.json"
    filepath = out_path / filename

    report = {
        "pipeline": pipeline_name,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "aggregate": results["aggregate"],
        "per_document": results["per_document"],
    }

    filepath.write_text(json.dumps(report, indent=2, default=str))
    return str(filepath)


def print_summary(pipeline_name: str, aggregate: dict[str, Any]) -> None:
    """Print a human-readable summary of aggregate metrics to stdout."""
    print(f"\n{'=' * 60}")
    print(f"  Benchmark Results: {pipeline_name}")
    print(f"{'=' * 60}")
    print(f"  Documents evaluated:      {aggregate['total_documents']}")
    print(f"  Overall field accuracy:   {aggregate['overall_field_accuracy']:.2%}")
    print(f"  Document exact match:     {aggregate['document_exact_match_rate']:.2%}")
    print(f"  HITL rate:                {aggregate['hitl_rate']:.2%}")
    print(f"  Parse failure rate:       {aggregate['parse_failure_rate']:.2%}")
    print(f"  Avg latency (ms):         {aggregate['avg_latency_ms']:.1f}")
    print(f"  Cost per document:        ${aggregate['cost_per_document']:.4f}")

    print(f"\n  Per-field accuracy:")
    for field, rate in aggregate.get("field_accuracy", {}).items():
        print(f"    {field:25s} {rate:.2%}")

    print(f"{'=' * 60}\n")
