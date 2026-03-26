"""Normalization utilities for extracted invoice fields.

Converts raw extraction outputs into a canonical form so that
scoring comparisons are consistent across pipelines.

Every normalizer follows the same contract:
  - Returns the normalized value on success.
  - Returns None when the input is missing (None / empty string).
  - Returns None when the input is present but cannot be normalized.

normalize_invoice() returns both the normalized dict and a list of
fields where normalization failed (raw value was present but could
not be converted). This failure list feeds directly into HITL logic.
"""

from __future__ import annotations

import math
import re
from datetime import datetime
from typing import Any

# ---------------------------------------------------------------------------
# Date normalization
# ---------------------------------------------------------------------------

# Ordered from most specific to least specific to avoid ambiguous parses.
_DATE_FORMATS = [
    "%Y-%m-%d",      # 2026-03-15
    "%d.%m.%Y",      # 15.03.2026
    "%d/%m/%Y",      # 15/03/2026
    "%m/%d/%Y",      # 03/15/2026
    "%d-%m-%Y",      # 15-03-2026
    "%B %d, %Y",     # March 15, 2026
    "%b %d, %Y",     # Mar 15, 2026
    "%d %B %Y",      # 15 March 2026
    "%d %b %Y",      # 15 Mar 2026
    "%Y%m%d",        # 20260315
]

# Reasonable date boundaries for invoices
_MIN_YEAR = 2000
_MAX_YEAR = 2100


def normalize_date(value: Any) -> str | None:
    """Normalize a date value to YYYY-MM-DD (ISO 8601).

    Accepts strings in common invoice date formats and datetime.date objects.
    Returns None if the value is missing or cannot be parsed.
    """
    if value is None:
        return None

    # Handle datetime.date / datetime.datetime objects directly
    if hasattr(value, "isoformat") and hasattr(value, "year"):
        if _MIN_YEAR <= value.year <= _MAX_YEAR:
            return value.strftime("%Y-%m-%d")
        return None

    text = str(value).strip()
    if not text:
        return None

    for fmt in _DATE_FORMATS:
        try:
            parsed = datetime.strptime(text, fmt)
        except ValueError:
            continue

        if _MIN_YEAR <= parsed.year <= _MAX_YEAR:
            return parsed.strftime("%Y-%m-%d")

    return None


# ---------------------------------------------------------------------------
# Amount normalization
# ---------------------------------------------------------------------------


def normalize_amount(value: Any) -> float | None:
    """Normalize a monetary amount to a non-negative float, rounded to 2 decimals.

    Handles:
      - int / float pass-through
      - Strings with currency symbols, whitespace, commas
      - European format (1.234,56)

    Returns None if the value is missing, negative, NaN, Inf,
    or cannot be parsed to a valid number.
    """
    if value is None:
        return None

    if isinstance(value, (int, float)):
        if math.isnan(value) or math.isinf(value):
            return None
        if value < 0:
            return None
        return round(float(value), 2)

    text = str(value).strip()
    if not text:
        return None

    # Strip everything that isn't a digit, comma, period, or minus sign
    text = re.sub(r"[^\d.,\-]", "", text)

    if not text or text == "-":
        return None

    # European format: 1.234,56  or  1.234,5  or  1.234
    # Pattern: digit groups separated by dots, optional comma + decimals
    if re.match(r"^\d{1,3}(\.\d{3})+(,\d{1,2})?$", text):
        text = text.replace(".", "").replace(",", ".")
    # Simple comma-as-decimal: 1234,56
    elif re.match(r"^\d+(,\d{1,2})$", text):
        text = text.replace(",", ".")
    else:
        # Standard format: commas are thousands separators
        text = text.replace(",", "")

    try:
        result = float(text)
    except ValueError:
        return None

    if math.isnan(result) or math.isinf(result):
        return None
    if result < 0:
        return None

    return round(result, 2)


# ---------------------------------------------------------------------------
# Currency normalization
# ---------------------------------------------------------------------------

_CURRENCY_SYMBOL_MAP: dict[str, str] = {
    "$": "USD",
    "€": "EUR",
    "£": "GBP",
    "¥": "JPY",
    "₣": "CHF",
    "₹": "INR",
    "₽": "RUB",
    "₺": "TRY",
    "R$": "BRL",
    "kr": "SEK",  # also NOK/DKK — ambiguous, but common default
    "zł": "PLN",
}


def normalize_currency(value: Any) -> str | None:
    """Normalize a currency indicator to an uppercase 3-letter ISO 4217 code.

    Accepts ISO codes (case-insensitive) and common currency symbols.
    Returns None if the value is missing or unrecognized.
    """
    if value is None:
        return None

    text = str(value).strip()
    if not text:
        return None

    # Try symbol map first (case-sensitive for symbols like kr, zł)
    if text in _CURRENCY_SYMBOL_MAP:
        return _CURRENCY_SYMBOL_MAP[text]

    # Try uppercase match
    upper = text.upper()
    if upper in _CURRENCY_SYMBOL_MAP.values():
        return upper

    # Accept any 3-letter uppercase code
    if re.match(r"^[A-Z]{3}$", upper):
        return upper

    return None


# ---------------------------------------------------------------------------
# String normalization
# ---------------------------------------------------------------------------


def normalize_string(value: Any) -> str | None:
    """Normalize a string field: trim whitespace, collapse inner whitespace.

    Returns None if the value is missing or empty after trimming.
    """
    if value is None:
        return None

    text = str(value).strip()
    text = re.sub(r"\s+", " ", text)

    return text if text else None


# ---------------------------------------------------------------------------
# Invoice-level normalization
# ---------------------------------------------------------------------------

# The five fields that every extraction must produce.
REQUIRED_FIELDS = ("invoice_number", "invoice_date", "vendor_name", "total_amount", "currency")

# Maps field name to the normalizer that should be applied.
_FIELD_NORMALIZERS: dict[str, Any] = {
    "invoice_number": normalize_string,
    "invoice_date": normalize_date,
    "vendor_name": normalize_string,
    "total_amount": normalize_amount,
    "currency": normalize_currency,
}


def normalize_invoice(raw: dict[str, Any]) -> dict[str, Any]:
    """Normalize all fields of a raw invoice extraction result.

    Returns a dict with:
      - The five canonical invoice fields (normalized values or None).
      - '_normalization_failures': list of field names where the raw value
        was present but normalization returned None. This is consumed by
        HITL logic to flag documents that need human review.
    """
    normalized: dict[str, Any] = {}
    failures: list[str] = []

    for field, normalizer in _FIELD_NORMALIZERS.items():
        raw_value = raw.get(field)
        result = normalizer(raw_value)
        normalized[field] = result

        # A normalization failure is when a raw value existed but
        # the normalizer could not convert it.
        raw_is_present = raw_value is not None and str(raw_value).strip() != ""
        if raw_is_present and result is None:
            failures.append(field)

    normalized["_normalization_failures"] = failures
    return normalized
