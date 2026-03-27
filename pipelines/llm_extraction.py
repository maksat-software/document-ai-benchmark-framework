"""LLM-based pipeline for invoice extraction.

Supports two providers:
  - provider="openai"    → uses OPENAI_API_KEY, OPENAI_MODEL
  - provider="anthropic" → uses ANTHROPIC_API_KEY, ANTHROPIC_MODEL

Reads a local PDF, extracts text via PyMuPDF, prompts the model for
strict JSON, validates the response schema, normalizes fields, and
returns a structured extraction result.

Return format (stable contract — matches azure pipeline):
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

import json
import os
import re
import time
from pathlib import Path
from typing import Any

import anthropic
import fitz  # PyMuPDF
from openai import OpenAI
from openai.types.chat import (
    ChatCompletionSystemMessageParam,
    ChatCompletionUserMessageParam,
)

from pipelines.normalize import REQUIRED_FIELDS, normalize_invoice

SUPPORTED_PROVIDERS = ("openai", "anthropic")

_SYSTEM_MESSAGE = """You are an information extraction system for invoice documents.
Return only valid JSON. No explanations, no markdown, no extra text."""

_EXTRACTION_PROMPT = """\
Your task is to extract structured fields from the provided invoice text.

Return ONLY valid JSON.

Output schema:
{
  "invoice_number": string | null,
  "invoice_date": string | null,
  "vendor_name": string | null,
  "total_amount": number | null,
  "currency": string | null
}

Extraction rules:

1. invoice_number
- Usually labeled as "Invoice No", "Invoice Number", "Invoice #", "Rechnung Nr", or similar
- Return exactly the invoice identifier shown in the document

2. invoice_date
- Extract the invoice issue date, not the due date
- Normalize to ISO format: YYYY-MM-DD
- If multiple dates exist, prefer the invoice issue date

3. vendor_name
- Extract the company issuing the invoice
- Usually appears near the top of the document
- Ignore the customer / bill-to company
- Prefer the legal entity / company name over the address

4. total_amount
- Extract the final payable total
- Ignore subtotal, tax, and line-item amounts unless clearly the final total
- Convert to a plain number
- Normalize formats:
  - "1,234.56" -> 1234.56
  - "1.234,56" -> 1234.56

5. currency
- Extract a 3-letter ISO currency code if possible
- Map common symbols:
  - "$" -> USD
  - "€" -> EUR
  - "CHF" -> CHF
- If unclear, return null

General rules:
- If a field is missing or uncertain, return null
- Do not guess
- Prefer null over incorrect values
- Return only one JSON object
- Do not include any explanation

Invoice text:
"""

_EMPTY_FIELDS: dict[str, Any] = {f: None for f in REQUIRED_FIELDS}

# Hard limit on text sent to the LLM to avoid blowing up context/cost.
# ~50 pages of dense text at ~3k chars/page. Invoices are typically 1–3 pages.
_MAX_TEXT_CHARS = 150_000


# ---------------------------------------------------------------------------
# PDF text extraction
# ---------------------------------------------------------------------------


def _extract_text_from_pdf(file_path: str) -> tuple[str, list[str]]:
    """Extract plain text from a PDF using PyMuPDF.

    Returns:
        (text, warnings) — the extracted text and any warnings produced
        during extraction (e.g. image-only pages).
    """
    doc = fitz.open(file_path)
    pages: list[str] = []
    warnings: list[str] = []
    empty_page_count = 0

    for page in doc:
        page_text = page.get_text()
        pages.append(page_text)
        if not page_text.strip():
            empty_page_count += 1

    doc.close()

    total_pages = len(pages)
    if total_pages > 0 and empty_page_count == total_pages:
        warnings.append(
            f"All {total_pages} page(s) returned no text; "
            "document is likely scan/image-based (not OCR'd)"
        )
    elif empty_page_count > 0:
        warnings.append(
            f"{empty_page_count}/{total_pages} page(s) returned no text; "
            "some pages may be scan/image-based"
        )

    text = "\n\n".join(pages)

    if len(text) > _MAX_TEXT_CHARS:
        warnings.append(
            f"Text truncated from {len(text)} to {_MAX_TEXT_CHARS} chars"
        )
        text = text[:_MAX_TEXT_CHARS]

    return text, warnings


# ---------------------------------------------------------------------------
# Response parsing
# ---------------------------------------------------------------------------

# Matches a fenced code block: ```<optional lang>\n...\n```
_FENCE_RE = re.compile(r"```(?:\w*)\s*\n(.*?)```", re.DOTALL)

# Matches { ... } allowing nested braces (one level deep)
_BRACE_RE = re.compile(r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}", re.DOTALL)


def _parse_llm_response(content: str) -> dict[str, Any]:
    """Parse a JSON object from an LLM response.

    Tries three strategies in order:
      1. Direct json.loads (clean JSON)
      2. Extract from markdown code fences (```json ... ```)
      3. Find first { ... } block in prose text

    Raises ValueError if no valid JSON object is found.
    """
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

    # Strategy 3: first { ... } block in text
    for brace_match in _BRACE_RE.finditer(text):
        try:
            parsed = json.loads(brace_match.group(0))
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            continue

    raise ValueError(f"No valid JSON object found in LLM response ({len(text)} chars)")


# ---------------------------------------------------------------------------
# Schema validation
# ---------------------------------------------------------------------------


def _validate_raw_fields(raw: Any) -> tuple[dict[str, Any], list[str]]:
    """Validate the parsed LLM response against the expected schema.

    Returns:
        (validated_dict, warnings) — the dict with only recognized keys,
        plus any warnings about unexpected structure.
    """
    warnings: list[str] = []

    if not isinstance(raw, dict):
        warnings.append(f"LLM returned {type(raw).__name__}, expected dict")
        return {f: None for f in REQUIRED_FIELDS}, warnings

    missing = [f for f in REQUIRED_FIELDS if f not in raw]
    if missing:
        warnings.append(f"LLM response missing keys: {', '.join(missing)}")

    extra = [k for k in raw if k not in REQUIRED_FIELDS]
    if extra:
        warnings.append(f"LLM response has unexpected keys: {', '.join(extra)}")

    validated = {f: raw.get(f) for f in REQUIRED_FIELDS}
    return validated, warnings


# ---------------------------------------------------------------------------
# Provider: OpenAI
# ---------------------------------------------------------------------------


def _call_openai(
        text: str, model: str | None = None,
) -> tuple[str, int, str, int | None, int | None]:
    """Call OpenAI chat completions API.

    Returns:
        (raw_content, latency_ms, resolved_model, input_tokens, output_tokens)
    """
    api_key = os.environ["OPENAI_API_KEY"]
    base_url = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")
    model = model or os.environ.get("OPENAI_MODEL", "gpt-4o")

    client = OpenAI(api_key=api_key, base_url=base_url)

    messages: list[ChatCompletionSystemMessageParam | ChatCompletionUserMessageParam] = [
        ChatCompletionSystemMessageParam(role="system", content=_SYSTEM_MESSAGE),
        ChatCompletionUserMessageParam(
            role="user",
            content=f"{_EXTRACTION_PROMPT}{text}",
        ),
    ]

    start = time.perf_counter()
    response = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=0.0,
    )
    latency_ms = round((time.perf_counter() - start) * 1000)

    raw_content = response.choices[0].message.content or ""

    input_tokens = None
    output_tokens = None
    if response.usage:
        input_tokens = response.usage.prompt_tokens
        output_tokens = response.usage.completion_tokens

    return raw_content, latency_ms, model, input_tokens, output_tokens


# ---------------------------------------------------------------------------
# Provider: Anthropic
# ---------------------------------------------------------------------------


def _call_anthropic(
        text: str, model: str | None = None,
) -> tuple[str, int, str, int | None, int | None]:
    """Call Anthropic messages API.

    Returns:
        (raw_content, latency_ms, resolved_model, input_tokens, output_tokens)
    """
    api_key = os.environ["ANTHROPIC_API_KEY"]
    base_url = os.environ.get("ANTHROPIC_BASE_URL")
    model = model or os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-6")

    client_kwargs: dict[str, Any] = {"api_key": api_key}
    if base_url:
        client_kwargs["base_url"] = base_url

    client = anthropic.Anthropic(**client_kwargs)

    start = time.perf_counter()
    message = client.messages.create(
        model=model,
        max_tokens=1024,
        system=_SYSTEM_MESSAGE,
        messages=[
            {"role": "user", "content": f"{_EXTRACTION_PROMPT}{text}"},
        ],
        temperature=0.0,
    )
    latency_ms = round((time.perf_counter() - start) * 1000)

    raw_content = message.content[0].text if message.content else ""

    input_tokens = message.usage.input_tokens if message.usage else None
    output_tokens = message.usage.output_tokens if message.usage else None

    return raw_content, latency_ms, model, input_tokens, output_tokens


# ---------------------------------------------------------------------------
# Result builder
# ---------------------------------------------------------------------------

_PROVIDER_CALLERS = {
    "openai": _call_openai,
    "anthropic": _call_anthropic,
}


def _build_result(
        document_id: str,
        fields: dict[str, Any],
        provider: str,
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
        "provider": provider,
        "model": model,
        "latency_ms": latency_ms,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def extract(
        file_path: str,
        provider: str = "openai",
        model: str | None = None,
) -> dict[str, Any]:
    """Extract invoice fields from a PDF using an LLM.

    Args:
        file_path: Path to the PDF file.
        provider: LLM provider — "openai" or "anthropic".
        model: Override the model name. If None, reads from env
               (OPENAI_MODEL or ANTHROPIC_MODEL).

    Returns:
        Structured extraction result dict (see module docstring).
    """
    if provider not in SUPPORTED_PROVIDERS:
        raise ValueError(
            f"Unsupported provider '{provider}'. Choose from: {SUPPORTED_PROVIDERS}"
        )

    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"PDF not found: {file_path}")

    document_id = path.stem
    errors: list[str] = []

    # --- Extract text from PDF ---
    text, text_warnings = _extract_text_from_pdf(file_path)
    errors.extend(text_warnings)

    if not text.strip():
        return _build_result(
            document_id=document_id,
            fields=_EMPTY_FIELDS,
            provider=provider,
            model=model,
            latency_ms=0,
            raw_response=None,
            errors=errors or ["No text extracted from PDF"],
        )

    # --- Call the LLM provider ---
    caller = _PROVIDER_CALLERS[provider]
    try:
        raw_response, latency_ms, resolved_model, in_tok, out_tok = caller(text, model)
    except Exception as exc:
        return _build_result(
            document_id=document_id,
            fields=_EMPTY_FIELDS,
            provider=provider,
            model=model,
            latency_ms=0,
            raw_response=None,
            errors=errors + [f"API call failed: {exc}"],
        )

    # --- Parse the JSON response ---
    try:
        raw_fields = _parse_llm_response(raw_response)
    except (json.JSONDecodeError, ValueError) as exc:
        return _build_result(
            document_id=document_id,
            fields=_EMPTY_FIELDS,
            provider=provider,
            model=resolved_model,
            latency_ms=latency_ms,
            raw_response=raw_response,
            errors=errors + [f"JSON parse failed: {exc}"],
            input_tokens=in_tok,
            output_tokens=out_tok,
        )

    # --- Validate schema before normalization ---
    validated, schema_warnings = _validate_raw_fields(raw_fields)
    errors.extend(schema_warnings)

    # --- Normalize fields ---
    normalized = normalize_invoice(validated)

    for field in normalized.pop("_normalization_failures", []):
        errors.append(f"Normalization failed for field: {field}")

    return _build_result(
        document_id=document_id,
        fields=normalized,
        provider=provider,
        model=resolved_model,
        latency_ms=latency_ms,
        raw_response=raw_response,
        errors=errors,
        input_tokens=in_tok,
        output_tokens=out_tok,
    )
