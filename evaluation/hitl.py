"""Human-in-the-loop (HITL) flagging logic.

Determines whether a normalized extraction result requires manual review.

A document is flagged for human review when ANY of these conditions hold:
  1. The extraction itself failed (an 'error' key is present).
  2. Any required field is missing (None after normalization).
  3. A required field was present in the raw output but normalization
     failed (e.g. unparseable date, non-numeric amount).
  4. invoice_date is not in valid YYYY-MM-DD format.
  5. total_amount is not a valid non-negative number.
  6. Schema validation fails (extra or missing keys).

The function returns (flagged, reasons) so that downstream reporting
can explain *why* a document was flagged.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from pipelines.normalize import REQUIRED_FIELDS

# Date must be a real calendar date, not just matching the regex
_DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def needs_review(extracted: dict[str, Any]) -> tuple[bool, list[str]]:
    """Check whether a normalized extraction result needs human review.

    Args:
        extracted: The normalized extraction result dict. Expected to
            contain the five invoice fields plus optional metadata
            (latency_ms, provider, model, error, _normalization_failures).

    Returns:
        A tuple of (flagged, reasons) where flagged is True if the
        document needs review and reasons lists every triggered rule.
    """
    reasons: list[str] = []

    # ------------------------------------------------------------------
    # 1. Extraction-level error
    # ------------------------------------------------------------------
    error = extracted.get("error")
    if error:
        reasons.append(f"extraction_error: {error}")

    # ------------------------------------------------------------------
    # 2. Missing required fields (None after normalization)
    # ------------------------------------------------------------------
    for field in REQUIRED_FIELDS:
        if extracted.get(field) is None:
            reasons.append(f"missing_field: {field}")

    # ------------------------------------------------------------------
    # 3. Normalization failures (raw value existed but could not convert)
    # ------------------------------------------------------------------
    norm_failures: list[str] = extracted.get("_normalization_failures", [])
    for field in norm_failures:
        reasons.append(f"normalization_failed: {field}")

    # ------------------------------------------------------------------
    # 4. invoice_date format and validity check
    # ------------------------------------------------------------------
    date_val = extracted.get("invoice_date")
    if date_val is not None:
        date_str = str(date_val)
        if not _DATE_PATTERN.match(date_str):
            reasons.append("invalid_date_format: expected YYYY-MM-DD")
        else:
            # Verify it's an actual calendar date (e.g. reject 2026-02-30)
            try:
                datetime.strptime(date_str, "%Y-%m-%d")
            except ValueError:
                reasons.append(f"invalid_calendar_date: {date_str}")

    # ------------------------------------------------------------------
    # 5. total_amount type and value check
    # ------------------------------------------------------------------
    amount = extracted.get("total_amount")
    if amount is not None:
        if not isinstance(amount, (int, float)):
            reasons.append(f"invalid_total_amount_type: {type(amount).__name__}")
        elif amount < 0:
            reasons.append(f"negative_total_amount: {amount}")

    # ------------------------------------------------------------------
    # 6. currency format check
    # ------------------------------------------------------------------
    currency = extracted.get("currency")
    if currency is not None:
        if not re.match(r"^[A-Z]{3}$", str(currency)):
            reasons.append(f"invalid_currency_format: {currency}")

    # Deduplicate while preserving order (e.g. missing_field and
    # normalization_failed can overlap for the same field)
    seen: set[str] = set()
    unique_reasons: list[str] = []
    for r in reasons:
        if r not in seen:
            seen.add(r)
            unique_reasons.append(r)

    flagged = len(unique_reasons) > 0
    return flagged, unique_reasons
