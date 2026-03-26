"""KPI computation for benchmark evaluation.

Computes per-document and aggregate metrics:
  - field_accuracy         (per field and overall)
  - document_exact_match   (all 5 fields correct)
  - hitl_rate              (fraction needing human review)
  - parse_failure_rate     (fraction where extraction errored)
  - latency_per_document   (average ms)
  - cost_per_document      (estimated)

All comparisons operate on normalized values.
"""

from __future__ import annotations

from typing import Any

from evaluation.hitl import needs_review
from pipelines.normalize import REQUIRED_FIELDS

SCORED_FIELDS: list[str] = list(REQUIRED_FIELDS)


# ---------------------------------------------------------------------------
# Per-document metrics
# ---------------------------------------------------------------------------


def field_accuracy(expected: dict[str, Any], extracted: dict[str, Any]) -> dict[str, bool]:
    """Compare each scored field between expected and extracted values.

    Comparison rules:
      - Both None        → match (field legitimately absent in ground truth)
      - One None         → mismatch
      - total_amount     → numeric comparison with 0.01 tolerance
      - All other fields → case-insensitive string comparison after strip
    """
    results: dict[str, bool] = {}

    for field in SCORED_FIELDS:
        exp = expected.get(field)
        ext = extracted.get(field)

        # Both missing — agree on absence
        if exp is None and ext is None:
            results[field] = True
            continue

        # One side missing — mismatch
        if exp is None or ext is None:
            results[field] = False
            continue

        if field == "total_amount":
            try:
                results[field] = abs(float(exp) - float(ext)) < 0.01
            except (ValueError, TypeError):
                results[field] = False
        else:
            results[field] = str(exp).strip().lower() == str(ext).strip().lower()

    return results


def document_exact_match(field_results: dict[str, bool]) -> bool:
    """True when every scored field matched."""
    return all(field_results.values())


def is_parse_failure(extracted: dict[str, Any]) -> bool:
    """True when the extraction itself failed before any scoring.

    A parse failure means the pipeline could not produce usable output
    at all — as opposed to producing output that is merely inaccurate.
    """
    # Explicit error from pipeline
    if extracted.get("error"):
        return True

    # Every required field is None — pipeline returned nothing useful
    if all(extracted.get(f) is None for f in SCORED_FIELDS):
        return True

    return False


def compute_document_metrics(
    expected: dict[str, Any],
    extracted: dict[str, Any],
) -> dict[str, Any]:
    """Compute all metrics for a single document.

    Args:
        expected: Ground truth 'expected' dict.
        extracted: Normalized extraction result dict from a pipeline.

    Returns:
        Dict with field_accuracy, exact_match, hitl_flagged,
        hitl_reasons, parse_failure, and latency_ms.
    """
    fields = field_accuracy(expected, extracted)
    exact = document_exact_match(fields)
    flagged, reasons = needs_review(extracted)
    failed = is_parse_failure(extracted)

    return {
        "field_accuracy": fields,
        "exact_match": exact,
        "hitl_flagged": flagged,
        "hitl_reasons": reasons,
        "parse_failure": failed,
        "latency_ms": extracted.get("latency_ms", 0),
    }


# ---------------------------------------------------------------------------
# Aggregate metrics
# ---------------------------------------------------------------------------


def compute_aggregate_metrics(
    document_results: list[dict[str, Any]],
    cost_per_document: float = 0.0,
) -> dict[str, Any]:
    """Aggregate metrics across all documents in a benchmark run.

    Args:
        document_results: Per-document metric dicts from compute_document_metrics.
        cost_per_document: Estimated cost per document for this pipeline.
    """
    n = len(document_results)
    if n == 0:
        return {
            "total_documents": 0,
            "field_accuracy": {},
            "overall_field_accuracy": 0.0,
            "document_exact_match_rate": 0.0,
            "hitl_rate": 0.0,
            "parse_failure_rate": 0.0,
            "avg_latency_ms": 0.0,
            "cost_per_document": cost_per_document,
        }

    # Per-field accuracy rates
    field_correct: dict[str, int] = {f: 0 for f in SCORED_FIELDS}
    for result in document_results:
        for field, matched in result["field_accuracy"].items():
            if matched:
                field_correct[field] += 1

    field_rates = {f: round(count / n, 4) for f, count in field_correct.items()}
    overall_field_acc = round(sum(field_rates.values()) / len(field_rates), 4)

    exact_matches = sum(1 for r in document_results if r["exact_match"])
    hitl_count = sum(1 for r in document_results if r["hitl_flagged"])
    parse_fail_count = sum(1 for r in document_results if r["parse_failure"])

    avg_latency = round(
        sum(r.get("latency_ms", 0) for r in document_results) / n, 1
    )

    return {
        "total_documents": n,
        "field_accuracy": field_rates,
        "overall_field_accuracy": overall_field_acc,
        "document_exact_match_rate": round(exact_matches / n, 4),
        "hitl_rate": round(hitl_count / n, 4),
        "parse_failure_rate": round(parse_fail_count / n, 4),
        "avg_latency_ms": avg_latency,
        "cost_per_document": cost_per_document,
    }
