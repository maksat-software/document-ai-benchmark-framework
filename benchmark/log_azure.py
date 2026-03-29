"""Raw response logger for Azure Document Intelligence.

Writes one JSON file per document into benchmark/logs/azure/<run_id>/,
capturing the full AnalyzeResult from the Azure API including:
  - all detected documents with confidence scores
  - per-field confidence and bounding regions
  - page metadata (dimensions, angles, words, lines)
  - tables, key-value pairs, styles, languages
  - API version, model ID, warnings
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _make_serializable(obj: Any) -> Any:
    """Ensure all values are JSON-serializable."""
    if isinstance(obj, dict):
        return {k: _make_serializable(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_make_serializable(v) for v in obj]
    if isinstance(obj, (datetime,)):
        return obj.isoformat()
    if isinstance(obj, bytes):
        return f"<{len(obj)} bytes>"
    return obj


def log_azure_response(
    document_id: str,
    extraction_result: dict[str, Any],
    log_dir: str = "benchmark/logs/azure",
    run_id: str | None = None,
) -> str | None:
    """Write the full Azure raw response for a single document.

    Args:
        document_id: The document identifier.
        extraction_result: The full extraction result dict from extract(),
            must contain 'azure_raw_result'.
        log_dir: Base directory for Azure logs.
        run_id: Optional run identifier. Defaults to a timestamp.

    Returns:
        Path to the written log file, or None if no raw result was available.
    """
    azure_raw = extraction_result.get("azure_raw_result")
    if azure_raw is None:
        return None

    if run_id is None:
        run_id = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

    run_dir = Path(log_dir) / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    log_entry = {
        "document_id": document_id,
        "logged_at": datetime.now(timezone.utc).isoformat(),
        "provider": extraction_result.get("provider"),
        "model": extraction_result.get("model"),
        "latency_ms": extraction_result.get("latency_ms"),
        "errors": extraction_result.get("errors", []),
        "extracted_fields": extraction_result.get("fields"),
        "azure_analyze_result": _make_serializable(azure_raw),
    }

    file_path = run_dir / f"{document_id}.json"
    file_path.write_text(
        json.dumps(log_entry, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )

    return str(file_path)


def log_azure_run_summary(
    extractions: dict[str, dict[str, Any]],
    log_dir: str = "benchmark/logs/azure",
    run_id: str | None = None,
) -> str:
    """Log all Azure extractions for a benchmark run and write a summary.

    Args:
        extractions: Map of document_id -> extraction result.
        log_dir: Base directory for Azure logs.
        run_id: Optional run identifier. Defaults to a timestamp.

    Returns:
        Path to the run directory.
    """
    if run_id is None:
        run_id = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

    logged_files: list[str] = []
    for doc_id, result in extractions.items():
        path = log_azure_response(doc_id, result, log_dir=log_dir, run_id=run_id)
        if path:
            logged_files.append(path)

    # Write a run-level summary
    run_dir = Path(log_dir) / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    summary = {
        "run_id": run_id,
        "logged_at": datetime.now(timezone.utc).isoformat(),
        "total_documents": len(extractions),
        "documents_with_raw_response": len(logged_files),
        "documents": {},
    }

    for doc_id, result in extractions.items():
        azure_raw = result.get("azure_raw_result")
        doc_summary: dict[str, Any] = {
            "latency_ms": result.get("latency_ms"),
            "errors": result.get("errors", []),
            "extracted_fields": result.get("fields"),
        }

        # Extract per-field confidence from raw result
        if azure_raw and azure_raw.get("documents"):
            first_doc = azure_raw["documents"][0]
            doc_summary["document_type"] = first_doc.get("doc_type")
            doc_summary["document_confidence"] = first_doc.get("confidence")

            raw_fields = first_doc.get("fields", {})
            field_confidences = {}
            for field_name, field_data in raw_fields.items():
                if isinstance(field_data, dict):
                    field_confidences[field_name] = {
                        "confidence": field_data.get("confidence"),
                        "type": field_data.get("type"),
                        "content": field_data.get("content"),
                    }
            doc_summary["field_confidences"] = field_confidences

            # Page-level metadata
            pages = azure_raw.get("pages", [])
            doc_summary["page_count"] = len(pages)
            doc_summary["pages"] = [
                {
                    "page_number": p.get("page_number"),
                    "width": p.get("width"),
                    "height": p.get("height"),
                    "unit": p.get("unit"),
                    "angle": p.get("angle"),
                    "word_count": len(p.get("words", [])),
                    "line_count": len(p.get("lines", [])),
                }
                for p in pages
            ]

            # Table count
            tables = azure_raw.get("tables", [])
            doc_summary["table_count"] = len(tables)

            # Key-value pairs count
            kv_pairs = azure_raw.get("key_value_pairs", [])
            doc_summary["key_value_pair_count"] = len(kv_pairs)

            # API version and model
            doc_summary["api_version"] = azure_raw.get("api_version")
            doc_summary["model_id"] = azure_raw.get("model_id")

        summary["documents"][doc_id] = doc_summary

    summary_path = run_dir / "_summary.json"
    summary_path.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )

    return str(run_dir)
