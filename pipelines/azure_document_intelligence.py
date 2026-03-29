"""Azure Document Intelligence pipeline for invoice extraction.

Calls the Azure Document Intelligence prebuilt invoice model and maps
the response to the standard invoice schema.

Uses the azure-ai-documentintelligence SDK (>=1.0.0).

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
        "azure_raw_result": dict | None,
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

from azure.ai.documentintelligence import DocumentIntelligenceClient
from azure.ai.documentintelligence.models import AnalyzeDocumentRequest
from azure.core.credentials import AzureKeyCredential

from pipelines.normalize import REQUIRED_FIELDS, normalize_invoice

_EMPTY_FIELDS: dict[str, Any] = {f: None for f in REQUIRED_FIELDS}


def _get_client() -> DocumentIntelligenceClient:
    """Create an Azure Document Intelligence client from environment variables."""
    endpoint = os.environ["AZURE_DI_ENDPOINT"]
    key = os.environ["AZURE_DI_KEY"]
    return DocumentIntelligenceClient(
        endpoint=endpoint,
        credential=AzureKeyCredential(key),
    )


def _safe_field(fields: Any, name: str) -> Any | None:
    """Get a named DocumentField from the fields mapping, or None."""
    if fields is None:
        return None
    # SDK objects support both attribute and dict-style access
    if hasattr(fields, "get"):
        return fields.get(name)
    return getattr(fields, name, None)


def _map_azure_fields(invoice: Any) -> dict[str, Any]:
    """Map Azure prebuilt invoice fields to our schema.

    azure-ai-documentintelligence 1.0.x returns DocumentField objects
    with snake_case typed value attributes:
      - InvoiceId       -> invoice_number  (.content)
      - InvoiceDate     -> invoice_date    (.value_date)
      - VendorName      -> vendor_name     (.content)
      - InvoiceTotal    -> total_amount    (.value_currency.amount / .value_currency.currency_code)
    """
    fields = getattr(invoice, "fields", None) or {}

    # InvoiceId
    invoice_id_field = _safe_field(fields, "InvoiceId")
    invoice_number = getattr(invoice_id_field, "content", None) if invoice_id_field else None

    # InvoiceDate — value_date returns an ISO date string (YYYY-MM-DD)
    date_field = _safe_field(fields, "InvoiceDate")
    invoice_date = getattr(date_field, "value_date", None) if date_field else None

    # VendorName
    vendor_field = _safe_field(fields, "VendorName")
    vendor_name = getattr(vendor_field, "content", None) if vendor_field else None

    # InvoiceTotal — value_currency is a CurrencyValue with .amount and .currency_code
    total_field = _safe_field(fields, "InvoiceTotal")
    total_amount = None
    currency = None
    if total_field is not None:
        currency_value = getattr(total_field, "value_currency", None)
        if currency_value is not None:
            total_amount = getattr(currency_value, "amount", None)
            currency = getattr(currency_value, "currency_code", None)
        else:
            # Fallback: try value_number for plain numeric total
            total_amount = getattr(total_field, "value_number", None)

    return {
        "invoice_number": invoice_number,
        "invoice_date": invoice_date,
        "vendor_name": vendor_name,
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
        file_bytes = f.read()

    poller = client.begin_analyze_document(
        model_id,
        body=AnalyzeDocumentRequest(bytes_source=file_bytes),
    )
    result = poller.result()
    latency_ms = round((time.perf_counter() - start) * 1000)

    # Serialize the full AnalyzeResult for logging
    azure_raw_result = result.as_dict() if hasattr(result, "as_dict") else None

    documents = result.documents or []

    if not documents:
        return {
            "document_id": document_id,
            "fields": dict(_EMPTY_FIELDS),
            "raw_response": None,
            "azure_raw_result": azure_raw_result,
            "errors": ["No invoice detected in document"],
            "provider": "azure",
            "model": model_id,
            "latency_ms": latency_ms,
        }

    first_doc = documents[0]
    raw_fields = _map_azure_fields(first_doc)
    normalized = normalize_invoice(raw_fields)

    errors: list[str] = []
    for field in normalized.pop("_normalization_failures", []):
        errors.append(f"Normalization failed for field: {field}")

    # Build raw_response for debugging
    raw_response_str = str(first_doc.fields) if first_doc.fields else None

    return {
        "document_id": document_id,
        "fields": {f: normalized.get(f) for f in REQUIRED_FIELDS},
        "raw_response": raw_response_str,
        "azure_raw_result": azure_raw_result,
        "errors": errors,
        "provider": "azure",
        "model": model_id,
        "latency_ms": latency_ms,
    }
