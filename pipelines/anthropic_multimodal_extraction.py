"""Multimodal Anthropic pipeline for invoice extraction.

Unlike the text-based Anthropic pipeline in llm_extraction.py, this
pipeline converts PDF pages to images and sends them to Anthropic's
vision API. This handles scan-like / image-based PDFs that yield no
extractable text.

Uses PyMuPDF (fitz) for PDF-to-image rendering — already a project
dependency, no new packages required.

Return format (same contract as all other pipelines):
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

import base64
import json
import os
import re
import time
from pathlib import Path
from typing import Any

import anthropic
import fitz  # PyMuPDF

from pipelines.normalize import REQUIRED_FIELDS, normalize_invoice

_PROVIDER = "anthropic_multimodal"

_SYSTEM_MESSAGE = """You are an information extraction system for invoice documents.
You will receive one or more page images from an invoice PDF.
Extract the requested fields by reading the document image.
Return only valid JSON. No explanations, no markdown, no extra text."""

_EXTRACTION_PROMPT = """\
Extract the following fields from the invoice image(s) above.

Return ONLY a valid JSON object with these exact keys:

{
  "invoice_number": string | null,
  "invoice_date": string | null,
  "vendor_name": string | null,
  "total_amount": number | null,
  "currency": string | null
}

Extraction rules:

1. invoice_number
- Usually labeled "Invoice No", "Invoice Number", "Invoice #", "Rechnung Nr", or similar
- Return exactly the invoice identifier shown in the document

2. invoice_date
- Extract the invoice issue date, not the due date
- Normalize to ISO format: YYYY-MM-DD
- If multiple dates exist, prefer the invoice issue date

3. vendor_name
- Extract the company issuing the invoice (the seller)
- Usually appears near the top of the document or in the header
- Ignore the customer / bill-to / ship-to company
- Prefer the legal entity name

4. total_amount
- Extract the final payable total
- Ignore subtotal, tax-only, and individual line-item amounts
- Return as a plain number: 1234.56
- Normalize European formats: "1.234,56" -> 1234.56

5. currency
- Return a 3-letter ISO 4217 code
- Map symbols: "$" -> "USD", "€" -> "EUR", "£" -> "GBP", "¥" -> "JPY"
- If the currency cannot be determined, return null

General rules:
- If a field is missing or uncertain, return null
- Do not guess — prefer null over incorrect values
- Return exactly one JSON object
- No explanation, no markdown fences, no extra text

Important:
- The input may be a scanned or degraded document.
- You must rely on visual understanding of the document, not pre-extracted text.

Output:
- Return ONLY JSON matching the schema."""

_EMPTY_FIELDS: dict[str, Any] = {f: None for f in REQUIRED_FIELDS}

# Maximum pages to render as images. Invoices are typically 1–3 pages.
# Limits cost and latency for the MVP.
_MAX_PAGES = 3

# DPI for rendering — 150 is a good balance between readability and size.
_RENDER_DPI = 150


# ---------------------------------------------------------------------------
# PDF to images
# ---------------------------------------------------------------------------


def _pdf_pages_to_base64(file_path: str) -> tuple[list[str], list[str]]:
    """Render PDF pages to base64-encoded PNG images.

    Returns:
        (images_b64, warnings) — list of base64 strings (one per page)
        and any warnings produced during rendering.
    """
    doc = fitz.open(file_path)
    images: list[str] = []
    warnings: list[str] = []
    total_pages = len(doc)

    pages_to_render = min(total_pages, _MAX_PAGES)
    if total_pages > _MAX_PAGES:
        warnings.append(
            f"PDF has {total_pages} pages; rendering first {_MAX_PAGES} only"
        )

    for i in range(pages_to_render):
        try:
            page = doc[i]
            # Render at target DPI
            matrix = fitz.Matrix(_RENDER_DPI / 72, _RENDER_DPI / 72)
            pixmap = page.get_pixmap(matrix=matrix)
            png_bytes = pixmap.tobytes("png")
            images.append(base64.standard_b64encode(png_bytes).decode("ascii"))
        except Exception as exc:
            warnings.append(f"Failed to render page {i + 1}: {exc}")

    doc.close()
    return images, warnings


# ---------------------------------------------------------------------------
# Response parsing (same logic as llm_extraction.py)
# ---------------------------------------------------------------------------

_FENCE_RE = re.compile(r"```(?:\w*)\s*\n(.*?)```", re.DOTALL)
_BRACE_RE = re.compile(r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}", re.DOTALL)


def _parse_response(content: str) -> dict[str, Any]:
    """Parse a JSON object from an LLM response."""
    text = content.strip()
    if not text:
        raise ValueError("Empty LLM response")

    # Strategy 1: direct parse
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass

    # Strategy 2: inside markdown fences
    fence_match = _FENCE_RE.search(text)
    if fence_match:
        try:
            parsed = json.loads(fence_match.group(1).strip())
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass

    # Strategy 3: first { ... } block
    for brace_match in _BRACE_RE.finditer(text):
        try:
            parsed = json.loads(brace_match.group(0))
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            continue

    raise ValueError(f"No valid JSON object found in response ({len(text)} chars)")


def _validate_fields(raw: Any) -> tuple[dict[str, Any], list[str]]:
    """Validate parsed response against expected schema."""
    warnings: list[str] = []

    if not isinstance(raw, dict):
        warnings.append(f"LLM returned {type(raw).__name__}, expected dict")
        return dict(_EMPTY_FIELDS), warnings

    missing = [f for f in REQUIRED_FIELDS if f not in raw]
    if missing:
        warnings.append(f"Response missing keys: {', '.join(missing)}")

    extra = [k for k in raw if k not in REQUIRED_FIELDS]
    if extra:
        warnings.append(f"Response has unexpected keys: {', '.join(extra)}")

    return {f: raw.get(f) for f in REQUIRED_FIELDS}, warnings


# ---------------------------------------------------------------------------
# Result builder
# ---------------------------------------------------------------------------


def _build_result(
        document_id: str,
        fields: dict[str, Any],
        model: str | None,
        latency_ms: int,
        raw_response: str | None,
        errors: list[str],
        input_tokens: int | None = None,
        output_tokens: int | None = None,
) -> dict[str, Any]:
    """Build the stable extraction result dict."""
    return {
        "document_id": document_id,
        "fields": {f: fields.get(f) for f in REQUIRED_FIELDS},
        "raw_response": raw_response,
        "errors": list(errors),
        "provider": _PROVIDER,
        "model": model,
        "latency_ms": latency_ms,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def extract(file_path: str, model: str | None = None) -> dict[str, Any]:
    """Extract invoice fields from a PDF using Anthropic's vision API.

    Converts PDF pages to images and sends them as a multimodal message.

    Args:
        file_path: Path to the PDF file.
        model: Override the model name. Defaults to ANTHROPIC_MODEL env var.

    Returns:
        Structured extraction result dict (see module docstring).
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"PDF not found: {file_path}")

    document_id = path.stem
    model = model or os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-6")
    errors: list[str] = []

    # --- Render PDF pages to images ---
    try:
        images_b64, render_warnings = _pdf_pages_to_base64(file_path)
        errors.extend(render_warnings)
    except Exception as exc:
        return _build_result(
            document_id=document_id,
            fields=_EMPTY_FIELDS,
            model=model,
            latency_ms=0,
            raw_response=None,
            errors=[f"PDF rendering failed: {exc}"],
        )

    if not images_b64:
        return _build_result(
            document_id=document_id,
            fields=_EMPTY_FIELDS,
            model=model,
            latency_ms=0,
            raw_response=None,
            errors=errors + ["No pages could be rendered from PDF"],
        )

    # --- Build multimodal message content ---
    # Each page image is a separate image block, followed by the text prompt.
    content_blocks: list[dict[str, Any]] = []
    for i, img_b64 in enumerate(images_b64):
        content_blocks.append({
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": "image/png",
                "data": img_b64,
            },
        })

    content_blocks.append({
        "type": "text",
        "text": _EXTRACTION_PROMPT,
    })

    # --- Call Anthropic API ---
    api_key = os.environ["ANTHROPIC_API_KEY"]
    base_url = os.environ.get("ANTHROPIC_BASE_URL")

    client_kwargs: dict[str, Any] = {"api_key": api_key}
    if base_url:
        client_kwargs["base_url"] = base_url

    client = anthropic.Anthropic(**client_kwargs)

    try:
        start = time.perf_counter()
        message = client.messages.create(
            model=model,
            max_tokens=1024,
            system=_SYSTEM_MESSAGE,
            messages=[{"role": "user", "content": content_blocks}],
            temperature=0.0,
        )
        latency_ms = round((time.perf_counter() - start) * 1000)
    except Exception as exc:
        return _build_result(
            document_id=document_id,
            fields=_EMPTY_FIELDS,
            model=model,
            latency_ms=0,
            raw_response=None,
            errors=errors + [f"API call failed: {exc}"],
        )

    raw_response = message.content[0].text if message.content else ""
    input_tokens = message.usage.input_tokens if message.usage else None
    output_tokens = message.usage.output_tokens if message.usage else None

    # --- Parse response ---
    try:
        raw_fields = _parse_response(raw_response)
    except (json.JSONDecodeError, ValueError) as exc:
        return _build_result(
            document_id=document_id,
            fields=_EMPTY_FIELDS,
            model=model,
            latency_ms=latency_ms,
            raw_response=raw_response,
            errors=errors + [f"JSON parse failed: {exc}"],
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )

    # --- Validate schema ---
    validated, schema_warnings = _validate_fields(raw_fields)
    errors.extend(schema_warnings)

    # --- Normalize ---
    normalized = normalize_invoice(validated)

    for field in normalized.pop("_normalization_failures", []):
        errors.append(f"Normalization failed for field: {field}")

    return _build_result(
        document_id=document_id,
        fields=normalized,
        model=model,
        latency_ms=latency_ms,
        raw_response=raw_response,
        errors=errors,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
    )
