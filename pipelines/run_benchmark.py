"""CLI benchmark runner.

Runs extraction pipelines against ground truth and reports KPIs.

Usage:
    python -m pipelines.run_benchmark --pipeline azure
    python -m pipelines.run_benchmark --pipeline openai
    python -m pipelines.run_benchmark --pipeline anthropic
    python -m pipelines.run_benchmark --pipeline all

    python -m pipelines.run_benchmark --pipeline azure --ground-truth data/ground_truth/invoices_medium.jsonl
    python -m pipelines.run_benchmark --pipeline azure --ground-truth data/ground_truth/invoices_hard.jsonl

    python -m pipelines.run_benchmark --pipeline openai --ground-truth data/ground_truth/invoices_easy.jsonl
    python -m pipelines.run_benchmark --pipeline anthropic --ground-truth data/ground_truth/invoices_easy.jsonl
    python -m pipelines.run_benchmark --pipeline anthropic_multimodal --ground-truth data/ground_truth/invoices_hard.jsonl
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from evaluation.report import print_summary, save_report
from evaluation.scoring import score_pipeline_run

PIPELINE_CHOICES = ["azure", "openai", "anthropic", "anthropic_multimodal", "all"]


# ---------------------------------------------------------------------------
# Ground truth loading
# ---------------------------------------------------------------------------


def _load_ground_truth(path: str) -> list[dict[str, Any]]:
    """Load ground truth from a JSON or JSONL file.

    JSON  → expects a list of objects.
    JSONL → one JSON object per line.
    """
    p = Path(path)
    text = p.read_text(encoding="utf-8")

    if p.suffix == ".jsonl":
        return [json.loads(line) for line in text.splitlines() if line.strip()]

    return json.loads(text)


# ---------------------------------------------------------------------------
# Pipeline runners
# ---------------------------------------------------------------------------


def _error_result(doc_id: str, exc: Exception, provider: str = "unknown") -> dict[str, Any]:
    """Build a failed extraction result matching the standard format."""
    return {
        "document_id": doc_id,
        "fields": {
            "invoice_number": None,
            "invoice_date": None,
            "vendor_name": None,
            "total_amount": None,
            "currency": None,
        },
        "raw_response": None,
        "errors": [str(exc)],
        "provider": provider,
        "model": None,
        "latency_ms": 0,
    }


def _run_azure(ground_truth: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Run Azure Document Intelligence on all documents."""
    from pipelines.azure_document_intelligence import extract

    extractions: dict[str, dict[str, Any]] = {}
    for entry in ground_truth:
        doc_id = entry["document_id"]
        file_path = entry["file_path"]
        print(f"  [azure] {doc_id}")
        try:
            extractions[doc_id] = extract(file_path)
        except Exception as exc:
            print(f"  [azure] ERROR {doc_id}: {exc}")
            extractions[doc_id] = _error_result(doc_id, exc, provider="azure")
    return extractions


def _run_anthropic_multimodal(
        ground_truth: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    """Run Anthropic multimodal (vision) extraction on all documents."""
    from pipelines.anthropic_multimodal_extraction import extract

    extractions: dict[str, dict[str, Any]] = {}
    for entry in ground_truth:
        doc_id = entry["document_id"]
        file_path = entry["file_path"]
        print(f"  [anthropic_multimodal] {doc_id}")
        try:
            extractions[doc_id] = extract(file_path)
        except Exception as exc:
            print(f"  [anthropic_multimodal] ERROR {doc_id}: {exc}")
            extractions[doc_id] = _error_result(doc_id, exc, provider="anthropic_multimodal")
    return extractions


def _run_llm(
        ground_truth: list[dict[str, Any]],
        provider: str,
) -> dict[str, dict[str, Any]]:
    """Run LLM extraction (openai or anthropic) on all documents."""
    from pipelines.llm_extraction import extract

    extractions: dict[str, dict[str, Any]] = {}
    for entry in ground_truth:
        doc_id = entry["document_id"]
        file_path = entry["file_path"]
        print(f"  [{provider}] {doc_id}")
        try:
            extractions[doc_id] = extract(file_path, provider=provider)
        except Exception as exc:
            print(f"  [{provider}] ERROR {doc_id}: {exc}")
            extractions[doc_id] = _error_result(doc_id, exc, provider=provider)
    return extractions


# ---------------------------------------------------------------------------
# Report helper
# ---------------------------------------------------------------------------


def _run_and_report(
        pipeline_name: str,
        ground_truth: list[dict[str, Any]],
        extractions: dict[str, dict[str, Any]],
        cost_per_document: float,
        output_dir: str,
) -> None:
    """Score extractions against ground truth, save report, print summary."""
    results = score_pipeline_run(ground_truth, extractions, cost_per_document)
    report_path = save_report(pipeline_name, results, output_dir)
    print_summary(pipeline_name, results["aggregate"])
    print(f"  Report saved to: {report_path}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> None:
    """Entry point for the benchmark runner."""
    parser = argparse.ArgumentParser(
        description="Run document extraction benchmark",
    )
    parser.add_argument(
        "--pipeline",
        choices=PIPELINE_CHOICES,
        default="all",
        help="Which pipeline to benchmark (default: all)",
    )
    parser.add_argument(
        "--ground-truth",
        default="data/ground_truth/invoices_easy.jsonl",
        help="Path to ground truth JSON or JSONL file",
    )
    parser.add_argument(
        "--output-dir",
        default="benchmark/outputs",
        help="Directory for benchmark report files",
    )
    parser.add_argument(
        "--azure-cost",
        type=float,
        default=0.01,
        help="Estimated cost per document for Azure DI (default: $0.01)",
    )
    parser.add_argument(
        "--openai-cost",
        type=float,
        default=0.03,
        help="Estimated cost per document for OpenAI (default: $0.03)",
    )
    parser.add_argument(
        "--anthropic-cost",
        type=float,
        default=0.03,
        help="Estimated cost per document for Anthropic text (default: $0.03)",
    )
    parser.add_argument(
        "--anthropic-multimodal-cost",
        type=float,
        default=0.05,
        help="Estimated cost per document for Anthropic multimodal (default: $0.05)",
    )
    args = parser.parse_args()

    load_dotenv()

    ground_truth = _load_ground_truth(args.ground_truth)
    print(f"Loaded {len(ground_truth)} documents from {args.ground_truth}\n")

    run_all = args.pipeline == "all"

    if args.pipeline == "azure" or run_all:
        print("Running Azure Document Intelligence pipeline...")
        extractions = _run_azure(ground_truth)
        _run_and_report("azure", ground_truth, extractions, args.azure_cost, args.output_dir)

    if args.pipeline == "openai" or run_all:
        print("Running OpenAI pipeline...")
        extractions = _run_llm(ground_truth, provider="openai")
        _run_and_report("openai", ground_truth, extractions, args.openai_cost, args.output_dir)

    if args.pipeline == "anthropic" or run_all:
        print("Running Anthropic pipeline...")
        extractions = _run_llm(ground_truth, provider="anthropic")
        _run_and_report("anthropic", ground_truth, extractions, args.anthropic_cost, args.output_dir)

    if args.pipeline == "anthropic_multimodal" or run_all:
        print("Running Anthropic multimodal pipeline...")
        extractions = _run_anthropic_multimodal(ground_truth)
        _run_and_report(
            "anthropic_multimodal", ground_truth, extractions,
            args.anthropic_multimodal_cost, args.output_dir,
        )


if __name__ == "__main__":
    main()
