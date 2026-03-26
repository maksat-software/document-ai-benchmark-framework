"""Scoring module: orchestrates per-document and aggregate evaluation.

Entry point for scoring a pipeline run against ground truth.

Accepts extraction results in the standard nested format:
    { "fields": {...}, "errors": [...], "provider": str, "latency_ms": int, ... }

Flattens them to the format that metrics.py and hitl.py expect
(invoice fields at top level).
"""

from __future__ import annotations

from typing import Any

from evaluation.metrics import compute_aggregate_metrics, compute_document_metrics
from pipelines.normalize import REQUIRED_FIELDS

# Non-fatal error prefixes — these are warnings, not extraction failures.
_NON_FATAL_PREFIXES = (
    "Normalization failed",
    "LLM response missing keys",
    "LLM response has unexpected keys",
)


def _flatten_extraction(raw: dict[str, Any]) -> dict[str, Any]:
    """Convert a nested extraction result to the flat format expected by metrics/hitl.

    Handles the standard format where invoice fields live under "fields"
    and errors are in "errors". Also handles legacy flat dicts (no "fields" key)
    from older pipeline versions.
    """
    if "fields" not in raw:
        # Legacy flat format — pass through as-is
        return raw

    fields: dict[str, Any] = raw.get("fields") or {}
    flat: dict[str, Any] = {f: fields.get(f) for f in REQUIRED_FIELDS}

    # Latency lives at top level in the current format
    flat["latency_ms"] = raw.get("latency_ms", 0)

    # Map errors list → "error" string for hitl/metrics compatibility.
    # Only fatal errors count as extraction failures.
    errors: list[str] = raw.get("errors") or []
    fatal_errors = [
        e for e in errors
        if not any(e.startswith(p) for p in _NON_FATAL_PREFIXES)
    ]
    if fatal_errors:
        flat["error"] = "; ".join(fatal_errors)

    # Reconstruct _normalization_failures for HITL from the errors list.
    _NORM_PREFIX = "Normalization failed for field: "
    norm_failures = [
        e.removeprefix(_NORM_PREFIX)
        for e in errors
        if e.startswith(_NORM_PREFIX)
    ]
    if norm_failures:
        flat["_normalization_failures"] = norm_failures

    return flat


def score_pipeline_run(
    ground_truth: list[dict[str, Any]],
    extractions: dict[str, dict[str, Any]],
    cost_per_document: float = 0.0,
) -> dict[str, Any]:
    """Score a full pipeline run against ground truth.

    Args:
        ground_truth: List of ground truth entries. Each must have
            'document_id' (str) and 'expected' (dict with the 5 fields).
        extractions: Mapping of document_id -> extraction result dict.
            Missing document_ids are treated as total extraction failures.
        cost_per_document: Estimated cost per document for this pipeline.

    Returns:
        {
            "per_document": [ ... per-doc metric dicts ... ],
            "aggregate": { ... aggregate KPIs ... },
        }
    """
    per_document: list[dict[str, Any]] = []

    for gt_entry in ground_truth:
        doc_id = gt_entry["document_id"]
        expected = gt_entry["expected"]

        raw_extracted = extractions.get(doc_id)
        if raw_extracted is None:
            # Document was never processed — treat as complete failure
            extracted: dict[str, Any] = {
                "invoice_number": None,
                "invoice_date": None,
                "vendor_name": None,
                "total_amount": None,
                "currency": None,
                "error": f"No extraction result for document {doc_id}",
            }
        else:
            extracted = _flatten_extraction(raw_extracted)

        doc_metrics = compute_document_metrics(expected, extracted)
        doc_metrics["document_id"] = doc_id
        per_document.append(doc_metrics)

    aggregate = compute_aggregate_metrics(per_document, cost_per_document)

    return {
        "per_document": per_document,
        "aggregate": aggregate,
    }
