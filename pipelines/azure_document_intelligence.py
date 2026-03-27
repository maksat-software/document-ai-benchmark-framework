"""Azure Document Intelligence pipeline for invoice extraction.

Calls the Azure Document Intelligence prebuilt invoice model and maps
the response to the standard invoice schema.

Return format (stable contract — shared with llm_extraction):
    {
        "document_id": str,
        "fields": {
            "invoice_number": str | None,
            "invoice_date": str | None,
            "vendor_name": str | None,
            "total_amount": float | None,
            "currency": str | None,
        },
        "raw_response": str | None,
        "errors": list[str],
        "provider": str,
        "model": str | None,
        "latency_ms": int,
    }
"""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any

from azure.ai.formrecognizer import DocumentAnalysisClient
from azure.core.credentials import AzureKeyCredential

from pipelines.normalize import REQUIRED_FIELDS, normalize_invoice

_EMPTY_FIELDS: dict[str, Any] = {f: None for f in REQUIRED_FIELDS}


def _get_client() -> DocumentAnalysisClient:
    """Create an Azure Document Intelligence client from environment variables."""
    endpoint = os.environ["AZURE_DI_ENDPOINT"]
    key = os.environ["AZURE_DI_KEY"]
    return DocumentAnalysisClient(
        endpoint=endpoint,
        credential=AzureKeyCredential(key),
    )


def _safe_field_value(fields: dict[str, Any], name: str) -> Any:
    """Get the .value of a named field, or None if the field is absent."""
    field = fields.get(name)
    if field is None:
        return None
    return field.value


def _safe_field_content(fields: dict[str, Any], name: str) -> str | None:
    """Get the .content (raw text) of a named field, or None."""
    field = fields.get(name)
    if field is None:
        return None
    return field.content


def _map_azure_fields(invoice: Any) -> dict[str, Any]:
    """Map Azure prebuilt invoice fields to our schema.

    Azure's prebuilt-invoice model returns typed field objects.
    Key mappings:
      - InvoiceId       -> invoice_number  (string)
      - InvoiceDate     -> invoice_date    (datetime.date)
      - VendorName      -> vendor_name     (string)
      - InvoiceTotal    -> total_amount    (CurrencyValue with .amount and .code)
    """
    fields = invoice.fields

    # InvoiceDate comes back as a datetime.date object
    date_value = _safe_field_value(fields, "InvoiceDate")
    invoice_date = date_value.isoformat() if date_value else None

    # InvoiceTotal is a CurrencyValue with .amount (float) and .code (str)
    total_field_value = _safe_field_value(fields, "InvoiceTotal")
    if total_field_value is not None and hasattr(total_field_value, "amount"):
        total_amount = total_field_value.amount
        currency = getattr(total_field_value, "code", None)
    else:
        # Fallback: treat value as a plain number, read currency from content
        total_amount = total_field_value
        currency = None

    return {
        "invoice_number": _safe_field_content(fields, "InvoiceId"),
        "invoice_date": invoice_date,
        "vendor_name": _safe_field_content(fields, "VendorName"),
        "total_amount": total_amount,
        "currency": currency,
    }


def extract(file_path: str) -> dict[str, Any]:
    """Extract invoice fields from a PDF using Azure Document Intelligence.

    Args:
        file_path: Path to the PDF file.

    Returns:
        Structured extraction result dict (see module docstring).
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"PDF not found: {file_path}")

    document_id = path.stem
    model_id = os.environ.get("AZURE_DI_MODEL_ID", "prebuilt-invoice")
    client = _get_client()

    start = time.perf_counter()
    with open(path, "rb") as f:
        poller = client.begin_analyze_document(model_id, f)
        result = poller.result()
    latency_ms = round((time.perf_counter() - start) * 1000)

    if not result.documents:
        return {
            "document_id": document_id,
            "fields": dict(_EMPTY_FIELDS),
            "raw_response": None,
            "errors": ["No invoice detected in document"],
            "provider": "azure",
            "model": model_id,
            "latency_ms": latency_ms,
        }

    raw_fields = _map_azure_fields(result.documents[0])
    normalized = normalize_invoice(raw_fields)

    errors: list[str] = []
    for field in normalized.pop("_normalization_failures", []):
        errors.append(f"Normalization failed for field: {field}")

    return {
        "document_id": document_id,
        "fields": {f: normalized.get(f) for f in REQUIRED_FIELDS},
        "raw_response": str(result.documents[0].fields) if result.documents else None,
        "errors": errors,
        "provider": "azure",
        "model": model_id,
        "latency_ms": latency_ms,
    }
