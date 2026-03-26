#!/usr/bin/env python3
"""Generate synthetic benchmark dataset: invoice PDFs and ground truth JSONL.

Produces:
  - 5 easy invoices   (clean, standard layout, digital-native)
  - 5 medium invoices (varied layouts, mixed languages, format variation)
  - 5 hard invoices   (scan-like noise, rotation, unusual layouts)
  - 3 OOD receipts    (not invoices, for robustness testing)

Usage:
    python data/generate_dataset.py

Dependencies:
    pip install reportlab Pillow
"""

from __future__ import annotations

import io
import json
import math
import random
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFilter, ImageFont
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, letter
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.platypus import Table, TableStyle

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "data" / "raw"
GT_DIR = ROOT / "data" / "ground_truth"

# ---------------------------------------------------------------------------
# Deterministic seed
# ---------------------------------------------------------------------------

random.seed(42)

# ---------------------------------------------------------------------------
# Fictional vendor data
# ---------------------------------------------------------------------------

VENDORS_EASY = [
    ("Acme Solutions Inc.", "USD"),
    ("Greenfield Logistics LLC", "USD"),
    ("Maple Leaf Trading Co.", "CAD"),
    ("Sunrise Digital Services", "USD"),
    ("Atlantic Freight Corp.", "USD"),
]

VENDORS_MEDIUM = [
    ("Müller & Schmidt GmbH", "EUR"),
    ("Bäckerei Sonnenschein OHG", "EUR"),
    ("Nordic Supply AB", "SEK"),
    ("Dubois & Fils SARL", "EUR"),
    ("Kowalski Sp. z o.o.", "PLN"),
]

VENDORS_HARD = [
    ("東京テクノロジー株式会社", "JPY"),
    ("Fernández Hermanos S.L.", "EUR"),
    ("Özdemir Ticaret A.Ş.", "TRY"),
    ("Волга-Транс ООО", "RUB"),
    ("Al-Rashid Trading Est.", "SAR"),
]

RECEIPT_VENDORS = [
    ("QuickMart Express", "USD"),
    ("Café Blümchen", "EUR"),
    ("7-Twelve Convenience", "GBP"),
]


# ---------------------------------------------------------------------------
# Data generators
# ---------------------------------------------------------------------------


def _easy_records() -> list[dict[str, Any]]:
    """Generate 5 easy invoice records with clean, standard data."""
    records = []
    for i, (vendor, currency) in enumerate(VENDORS_EASY, start=1):
        doc_id = f"invoice_easy_{i:03d}"
        amount = round(random.uniform(500, 15000), 2)
        month = (i * 2) % 12 + 1
        records.append({
            "document_id": f"{doc_id}.pdf",
            "file_path": f"data/raw/invoices_easy/{doc_id}.pdf",
            "difficulty": "easy",
            "document_type": "invoice",
            "expected": {
                "invoice_number": f"INV-2026-{i:04d}",
                "invoice_date": f"2026-{month:02d}-{10 + i:02d}",
                "vendor_name": vendor,
                "total_amount": amount,
                "currency": currency,
            },
        })
    return records


def _medium_records() -> list[dict[str, Any]]:
    """Generate 5 medium invoice records with format variation."""
    records = []
    date_formats_display = [
        "2026-{m:02d}-{d:02d}",
        "{d:02d}.{m:02d}.2026",
        "{d:02d}/{m:02d}/2026",
        "{m:02d}-{d:02d}-2026",
        "2026/{m:02d}/{d:02d}",
    ]
    invoice_number_patterns = [
        "RE-2026-{i:05d}",
        "2026/{i:04d}",
        "RG{i:06d}",
        "F-{i:04d}/2026",
        "Nr. {i:04d}",
    ]
    for i, (vendor, currency) in enumerate(VENDORS_MEDIUM, start=1):
        doc_id = f"invoice_medium_{i:03d}"
        amount = round(random.uniform(200, 50000), 2)
        month = (i * 3) % 12 + 1
        day = 5 + i * 3
        inv_num = invoice_number_patterns[i - 1].format(i=1000 + i)
        records.append({
            "document_id": f"{doc_id}.pdf",
            "file_path": f"data/raw/invoices_medium/{doc_id}.pdf",
            "difficulty": "medium",
            "document_type": "invoice",
            "expected": {
                "invoice_number": inv_num,
                "invoice_date": f"2026-{month:02d}-{day:02d}",
                "vendor_name": vendor,
                "total_amount": amount,
                "currency": currency,
            },
            # Store the display date format for PDF rendering
            "_display_date": date_formats_display[i - 1].format(m=month, d=day),
        })
    return records


def _hard_records() -> list[dict[str, Any]]:
    """Generate 5 hard invoice records with challenging characteristics."""
    records = []
    for i, (vendor, currency) in enumerate(VENDORS_HARD, start=1):
        doc_id = f"invoice_hard_{i:03d}"
        amount = round(random.uniform(100, 100000), 2)
        month = (i * 2 + 1) % 12 + 1
        day = min(28, 3 + i * 5)
        records.append({
            "document_id": f"{doc_id}.pdf",
            "file_path": f"data/raw/invoices_hard/{doc_id}.pdf",
            "difficulty": "hard",
            "document_type": "invoice",
            "expected": {
                "invoice_number": f"H-{2026}{i:03d}-X",
                "invoice_date": f"2026-{month:02d}-{day:02d}",
                "vendor_name": vendor,
                "total_amount": amount,
                "currency": currency,
            },
        })
    return records


def _receipt_records() -> list[dict[str, Any]]:
    """Generate 3 OOD receipt records."""
    records = []
    for i, (vendor, currency) in enumerate(RECEIPT_VENDORS, start=1):
        doc_id = f"receipt_ood_{i:03d}"
        amount = round(random.uniform(5, 120), 2)
        records.append({
            "document_id": f"{doc_id}.pdf",
            "file_path": f"data/raw/receipts_ood/{doc_id}.pdf",
            "difficulty": "ood",
            "document_type": "receipt",
            "expected": {
                "invoice_number": None,
                "invoice_date": f"2026-03-{10 + i:02d}",
                "vendor_name": vendor,
                "total_amount": amount,
                "currency": currency,
            },
        })
    return records


# ---------------------------------------------------------------------------
# PDF generators
# ---------------------------------------------------------------------------


def _generate_easy_pdf(record: dict[str, Any], output_path: Path) -> None:
    """Generate a clean, standard-layout invoice PDF."""
    exp = record["expected"]
    c = canvas.Canvas(str(output_path), pagesize=letter)
    width, height = letter

    # Header
    c.setFont("Helvetica-Bold", 24)
    c.drawString(50, height - 60, "INVOICE")

    # Vendor info
    c.setFont("Helvetica", 12)
    c.drawString(50, height - 100, exp["vendor_name"])
    c.drawString(50, height - 116, "123 Business Avenue")
    c.drawString(50, height - 132, "Suite 100, Business City")

    # Invoice details box (right side)
    c.setFont("Helvetica-Bold", 10)
    c.drawRightString(width - 50, height - 100, "Invoice Number:")
    c.drawRightString(width - 50, height - 116, "Invoice Date:")
    c.drawRightString(width - 50, height - 132, "Currency:")

    c.setFont("Helvetica", 10)
    c.drawRightString(width - 180, height - 100, exp["invoice_number"])
    c.drawRightString(width - 180, height - 116, exp["invoice_date"])
    c.drawRightString(width - 180, height - 132, exp["currency"])

    # Bill To section
    c.setFont("Helvetica-Bold", 10)
    c.drawString(50, height - 180, "Bill To:")
    c.setFont("Helvetica", 10)
    c.drawString(50, height - 196, "Sample Customer Corp.")
    c.drawString(50, height - 212, "456 Client Road")

    # Line items table
    line_items = _random_line_items(exp["total_amount"], exp["currency"])
    table_data = [["Description", "Qty", "Unit Price", "Amount"]]
    for item in line_items:
        table_data.append([
            item["desc"],
            str(item["qty"]),
            f"{item['unit_price']:.2f}",
            f"{item['amount']:.2f}",
        ])

    table = Table(table_data, colWidths=[250, 60, 100, 100])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2c3e50")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#ecf0f1")]),
    ]))
    table.wrapOn(c, width, height)
    table.drawOn(c, 50, height - 340)

    # Total
    c.setFont("Helvetica-Bold", 12)
    c.drawRightString(width - 50, height - 370, f"Total: {exp['currency']} {exp['total_amount']:,.2f}")

    # Footer
    c.setFont("Helvetica", 8)
    c.drawString(50, 40, "Thank you for your business. Payment due within 30 days.")

    c.save()


def _generate_medium_pdf(record: dict[str, Any], output_path: Path) -> None:
    """Generate a medium-difficulty invoice with varied layout and labels."""
    exp = record["expected"]
    display_date = record.get("_display_date", exp["invoice_date"])
    c = canvas.Canvas(str(output_path), pagesize=A4)
    width, height = A4
    idx = int(record["document_id"].split("_")[-1].replace(".pdf", ""))

    # Alternate between layout styles
    if idx % 2 == 1:
        _medium_layout_german(c, width, height, exp, display_date)
    else:
        _medium_layout_tabular(c, width, height, exp, display_date)

    c.save()


def _medium_layout_german(
        c: canvas.Canvas,
        width: float,
        height: float,
        exp: dict[str, Any],
        display_date: str,
) -> None:
    """German-style invoice layout with mixed labels."""
    # Company header
    c.setFont("Helvetica-Bold", 18)
    c.drawString(40, height - 50, exp["vendor_name"])
    c.setFont("Helvetica", 9)
    c.drawString(40, height - 66, "Musterstraße 42 · 10115 Berlin · Deutschland")
    c.drawString(40, height - 78, "USt-IdNr: DE123456789 · Steuernummer: 27/123/45678")

    # Line
    c.setStrokeColor(colors.HexColor("#888888"))
    c.line(40, height - 90, width - 40, height - 90)

    # Recipient
    c.setFont("Helvetica", 9)
    c.drawString(40, height - 115, "An:")
    c.setFont("Helvetica", 10)
    c.drawString(40, height - 130, "Musterfirma GmbH")
    c.drawString(40, height - 144, "Beispielweg 7, 80331 München")

    # Invoice meta (right column, German labels)
    meta_x = width - 200
    c.setFont("Helvetica-Bold", 10)
    c.drawString(meta_x, height - 115, "Rechnungsnummer:")
    c.drawString(meta_x, height - 131, "Rechnungsdatum:")
    c.drawString(meta_x, height - 147, "Währung:")
    c.setFont("Helvetica", 10)
    c.drawString(meta_x + 120, height - 115, exp["invoice_number"])
    c.drawString(meta_x + 120, height - 131, display_date)
    c.drawString(meta_x + 120, height - 147, exp["currency"])

    # Title
    c.setFont("Helvetica-Bold", 14)
    c.drawString(40, height - 190, "Rechnung")

    # Line items
    line_items = _random_line_items(exp["total_amount"], exp["currency"])
    table_data = [["Pos.", "Beschreibung", "Menge", "Einzelpreis", "Betrag"]]
    for j, item in enumerate(line_items, 1):
        table_data.append([
            str(j),
            item["desc"],
            str(item["qty"]),
            _format_amount_eu(item["unit_price"]),
            _format_amount_eu(item["amount"]),
        ])

    # Subtotal / tax / total rows
    subtotal = sum(it["amount"] for it in line_items)
    tax = round(exp["total_amount"] - subtotal, 2)
    table_data.append(["", "", "", "Zwischensumme:", _format_amount_eu(subtotal)])
    if abs(tax) > 0.01:
        table_data.append(["", "", "", "MwSt. (19%):", _format_amount_eu(tax)])
    table_data.append(["", "", "", "Gesamtbetrag:", _format_amount_eu(exp["total_amount"])])

    table = Table(table_data, colWidths=[35, 220, 50, 90, 90])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#34495e")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ALIGN", (2, 0), (-1, -1), "RIGHT"),
        ("GRID", (0, 0), (-1, len(line_items)), 0.4, colors.grey),
        ("LINEABOVE", (3, -1), (-1, -1), 1, colors.black),
        ("FONTNAME", (3, -1), (-1, -1), "Helvetica-Bold"),
    ]))
    table.wrapOn(c, width, height)
    table.drawOn(c, 40, height - 200 - len(table_data) * 18 - 30)

    # Footer
    c.setFont("Helvetica", 7)
    c.drawString(40, 35, "Bankverbindung: Deutsche Bank · IBAN: DE89 3704 0044 0532 0130 00 · BIC: COBADEFFXXX")


def _medium_layout_tabular(
        c: canvas.Canvas,
        width: float,
        height: float,
        exp: dict[str, Any],
        display_date: str,
) -> None:
    """Tabular / compact invoice layout."""
    # Company block top-right
    c.setFont("Helvetica-Bold", 14)
    c.drawRightString(width - 40, height - 50, exp["vendor_name"])
    c.setFont("Helvetica", 8)
    c.drawRightString(width - 40, height - 64, "Industriestraße 15 · 70173 Stuttgart")

    # Large "INVOICE" label
    c.setFont("Helvetica-Bold", 28)
    c.drawString(40, height - 55, "INVOICE")

    # Meta as a small table
    meta_data = [
        ["Invoice No.", exp["invoice_number"]],
        ["Date", display_date],
        ["Currency", exp["currency"]],
    ]
    meta_table = Table(meta_data, colWidths=[80, 140])
    meta_table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.black),
        ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.grey),
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f0f0f0")),
    ]))
    meta_table.wrapOn(c, width, height)
    meta_table.drawOn(c, 40, height - 140)

    # Line items
    line_items = _random_line_items(exp["total_amount"], exp["currency"])
    table_data = [["#", "Item", "Qty", "Price", "Total"]]
    for j, item in enumerate(line_items, 1):
        table_data.append([
            str(j), item["desc"], str(item["qty"]),
            f"{item['unit_price']:,.2f}", f"{item['amount']:,.2f}",
        ])
    table_data.append(["", "", "", "TOTAL:", f"{exp['total_amount']:,.2f}"])

    t = Table(table_data, colWidths=[30, 230, 40, 80, 80])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2c3e50")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ALIGN", (2, 0), (-1, -1), "RIGHT"),
        ("GRID", (0, 0), (-1, -2), 0.4, colors.grey),
        ("LINEABOVE", (3, -1), (-1, -1), 1.2, colors.black),
        ("FONTNAME", (3, -1), (-1, -1), "Helvetica-Bold"),
    ]))
    t.wrapOn(c, width, height)
    t.drawOn(c, 40, height - 160 - len(table_data) * 18 - 20)

    c.setFont("Helvetica", 7)
    c.drawString(40, 35, "Payment terms: Net 30 · Please reference invoice number in your payment.")


def _generate_hard_pdf(record: dict[str, Any], output_path: Path) -> None:
    """Generate a hard-difficulty invoice: render to image, add noise, convert back to PDF.

    Applies scan-like degradation: slight rotation, gaussian blur,
    speckle noise, and reduced contrast.
    """
    exp = record["expected"]
    idx = int(record["document_id"].split("_")[-1].replace(".pdf", ""))

    # First render a clean PDF to an in-memory buffer
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    width, height = A4
    _hard_invoice_content(c, width, height, exp, idx)
    c.save()
    buf.seek(0)

    # Convert the PDF page to a PIL image using a simple rendering approach
    # We draw the content directly onto a PIL Image instead
    img = _render_hard_invoice_image(exp, idx)

    # Apply scan-like degradation
    img = _apply_scan_effects(img, idx)

    # Save as PDF
    img.save(str(output_path), "PDF", resolution=150)


def _hard_invoice_content(
        c: canvas.Canvas, width: float, height: float,
        exp: dict[str, Any], idx: int,
) -> None:
    """Draw invoice content for hard PDFs (used as base before degradation)."""
    # Minimal, unusual layout — fields scattered
    c.setFont("Helvetica", 10)
    c.drawString(60, height - 40, exp["vendor_name"])

    c.setFont("Helvetica-Bold", 11)
    c.drawString(60, height - 70, f"Invoice # {exp['invoice_number']}")

    c.setFont("Helvetica", 9)
    c.drawString(60, height - 90, f"Date: {exp['invoice_date']}")

    # Line items in basic text form
    y = height - 130
    line_items = _random_line_items(exp["total_amount"], exp["currency"])
    for item in line_items:
        c.drawString(60, y, f"- {item['desc']}  x{item['qty']}  {item['amount']:.2f}")
        y -= 16

    y -= 10
    c.setFont("Helvetica-Bold", 11)
    c.drawString(60, y, f"TOTAL: {exp['currency']} {exp['total_amount']:,.2f}")

    if idx >= 4:
        # Multi-page: add a second page with notes
        c.showPage()
        c.setFont("Helvetica", 9)
        c.drawString(60, height - 60, "Additional notes and terms:")
        c.drawString(60, height - 80, "Payment due within 45 days of invoice date.")
        c.drawString(60, height - 96, "Late fees of 1.5% per month apply.")


def _render_hard_invoice_image(exp: dict[str, Any], idx: int) -> Image.Image:
    """Render invoice content directly to a PIL image for degradation."""
    # A4 at 150 DPI ≈ 1240 x 1754
    img_w, img_h = 1240, 1754
    img = Image.new("RGB", (img_w, img_h), "white")
    draw = ImageDraw.Draw(img)

    # Use default font (always available)
    try:
        font_large = ImageFont.truetype("Helvetica", 28)
        font_normal = ImageFont.truetype("Helvetica", 20)
        font_bold = ImageFont.truetype("Helvetica-Bold", 22)
    except (OSError, IOError):
        font_large = ImageFont.load_default()
        font_normal = font_large
        font_bold = font_large

    # Draw content
    y = 80
    draw.text((100, y), exp["vendor_name"], fill="black", font=font_large)
    y += 60
    draw.text((100, y), f"Invoice # {exp['invoice_number']}", fill="black", font=font_bold)
    y += 40
    draw.text((100, y), f"Date: {exp['invoice_date']}", fill="black", font=font_normal)
    y += 50

    line_items = _random_line_items(exp["total_amount"], exp["currency"])
    for item in line_items:
        draw.text(
            (100, y),
            f"- {item['desc']}   x{item['qty']}   {item['amount']:.2f}",
            fill="black", font=font_normal,
        )
        y += 32

    y += 20
    draw.text(
        (100, y),
        f"TOTAL: {exp['currency']} {exp['total_amount']:,.2f}",
        fill="black", font=font_bold,
    )

    # Add a fake stamp for some documents
    if idx in (2, 4):
        draw.ellipse([700, 600, 1000, 750], outline="red", width=3)
        draw.text((740, 650), "PAID", fill="red", font=font_large)

    # Add handwritten-like note for some
    if idx == 3:
        draw.text((600, 200), "checked - OK", fill="blue", font=font_normal)

    return img


def _apply_scan_effects(img: Image.Image, idx: int) -> Image.Image:
    """Apply scan-like degradation: rotation, blur, noise, contrast reduction."""
    # Slight rotation (different per document)
    angles = [0.8, -1.2, 1.5, -0.6, 2.0]
    angle = angles[idx - 1] if idx <= len(angles) else 0.5
    img = img.rotate(angle, resample=Image.BICUBIC, expand=False, fillcolor="white")

    # Gaussian blur to simulate scan softness
    blur_radius = [0.8, 1.0, 1.2, 0.9, 1.1]
    img = img.filter(ImageFilter.GaussianBlur(radius=blur_radius[min(idx - 1, 4)]))

    # Add speckle noise
    import numpy as np
    arr = np.array(img, dtype=np.float32)
    noise = np.random.RandomState(idx).normal(0, 8, arr.shape)
    arr = np.clip(arr + noise, 0, 255).astype(np.uint8)
    img = Image.fromarray(arr)

    # Reduce contrast slightly
    from PIL import ImageEnhance
    img = ImageEnhance.Contrast(img).enhance(0.85)

    # Slight yellowing to simulate aged paper
    if idx in (1, 3, 5):
        overlay = Image.new("RGB", img.size, (245, 240, 220))
        img = Image.blend(img, overlay, alpha=0.08)

    # Convert to grayscale for some (like a B&W scan)
    if idx in (2, 4):
        img = img.convert("L").convert("RGB")

    return img


def _generate_receipt_pdf(record: dict[str, Any], output_path: Path) -> None:
    """Generate a simple receipt PDF (narrow format, minimal layout)."""
    exp = record["expected"]
    # Receipts are narrow — use a custom small page size
    page_w = 80 * mm
    page_h = 200 * mm
    c = canvas.Canvas(str(output_path), pagesize=(page_w, page_h))

    c.setFont("Helvetica-Bold", 12)
    c.drawCentredString(page_w / 2, page_h - 20, exp["vendor_name"])

    c.setFont("Helvetica", 8)
    c.drawCentredString(page_w / 2, page_h - 34, "123 Main St · Open 7am-11pm")

    # Dashed line
    c.setDash(2, 2)
    c.line(8, page_h - 42, page_w - 8, page_h - 42)
    c.setDash()

    c.setFont("Helvetica", 8)
    c.drawString(10, page_h - 58, f"Date: {exp['invoice_date']}")
    c.drawString(10, page_h - 70, f"Receipt #: {record['document_id'].replace('.pdf', '').upper()}")

    # Random items
    y = page_h - 92
    n_items = random.randint(2, 5)
    items_total = 0.0
    for _ in range(n_items):
        item_price = round(random.uniform(1.50, 25.00), 2)
        items_total += item_price
        c.drawString(10, y, f"Item  {item_price:.2f}")
        y -= 12

    # Tax + total (make total match ground truth)
    tax = round(exp["total_amount"] - items_total, 2)
    y -= 6
    c.setDash(2, 2)
    c.line(8, y + 4, page_w - 8, y + 4)
    c.setDash()
    y -= 6
    c.drawString(10, y, f"Subtotal:  {items_total:.2f}")
    y -= 12
    c.drawString(10, y, f"Tax:       {max(0, tax):.2f}")
    y -= 14
    c.setFont("Helvetica-Bold", 9)
    c.drawString(10, y, f"TOTAL {exp['currency']}  {exp['total_amount']:.2f}")

    y -= 24
    c.setFont("Helvetica", 7)
    c.drawCentredString(page_w / 2, y, "Thank you for your purchase!")

    c.save()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_ITEM_DESCRIPTIONS = [
    "Consulting Services", "Software License", "Hardware Component",
    "Monthly Subscription", "Training Session", "Support Contract",
    "Data Migration", "Cloud Hosting", "API Access Fee", "Maintenance",
    "Design Work", "Integration Setup", "Security Audit", "Report Generation",
    "Shipping & Handling", "Equipment Rental", "Print Services",
]


def _random_line_items(
        target_total: float, currency: str, min_items: int = 2, max_items: int = 5,
) -> list[dict[str, Any]]:
    """Generate random line items that sum to approximately the target total.

    The last item is adjusted so totals match exactly.
    """
    n = random.randint(min_items, max_items)
    descriptions = random.sample(_ITEM_DESCRIPTIONS, min(n, len(_ITEM_DESCRIPTIONS)))

    items: list[dict[str, Any]] = []
    remaining = target_total

    for i in range(n):
        qty = random.randint(1, 5)
        if i < n - 1:
            # Random portion of remaining amount
            portion = random.uniform(0.15, 0.5)
            amount = round(remaining * portion, 2)
        else:
            amount = round(remaining, 2)

        unit_price = round(amount / qty, 2)
        # Recalculate amount from unit_price * qty to avoid rounding drift
        amount = round(unit_price * qty, 2)
        remaining -= amount

        items.append({
            "desc": descriptions[i],
            "qty": qty,
            "unit_price": unit_price,
            "amount": amount,
        })

    # Fix rounding: adjust last item so sum matches target exactly
    current_sum = sum(it["amount"] for it in items)
    diff = round(target_total - current_sum, 2)
    if items and abs(diff) > 0:
        items[-1]["amount"] = round(items[-1]["amount"] + diff, 2)
        items[-1]["unit_price"] = round(items[-1]["amount"] / items[-1]["qty"], 2)

    return items


def _format_amount_eu(val: float) -> str:
    """Format a number in European style: 1.234,56"""
    formatted = f"{val:,.2f}"
    # Swap . and , for European format
    formatted = formatted.replace(",", "X").replace(".", ",").replace("X", ".")
    return formatted


# ---------------------------------------------------------------------------
# Ground truth writer
# ---------------------------------------------------------------------------


def _write_ground_truth(records: list[dict[str, Any]], output_path: Path) -> None:
    """Write records to a JSONL file, stripping internal keys."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        for record in records:
            # Remove internal keys (prefixed with _)
            clean = {k: v for k, v in record.items() if not k.startswith("_")}
            f.write(json.dumps(clean, ensure_ascii=False) + "\n")
    print(f"  Wrote {len(records)} entries to {output_path}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    """Generate the full benchmark dataset."""
    print("Generating benchmark dataset...\n")

    # Generate records
    easy = _easy_records()
    medium = _medium_records()
    hard = _hard_records()
    receipts = _receipt_records()

    # Generate PDFs
    for label, records, generator in [
        ("invoices_easy", easy, _generate_easy_pdf),
        ("invoices_medium", medium, _generate_medium_pdf),
        ("invoices_hard", hard, _generate_hard_pdf),
        ("receipts_ood", receipts, _generate_receipt_pdf),
    ]:
        out_dir = RAW_DIR / label
        out_dir.mkdir(parents=True, exist_ok=True)
        print(f"Generating {label}...")
        for record in records:
            doc_id = record["document_id"]
            pdf_path = out_dir / doc_id
            generator(record, pdf_path)
            print(f"  {pdf_path.relative_to(ROOT)}")

    # Write ground truth JSONL
    print("\nWriting ground truth...")
    _write_ground_truth(easy, GT_DIR / "invoices_easy.jsonl")
    _write_ground_truth(medium, GT_DIR / "invoices_medium.jsonl")
    _write_ground_truth(hard, GT_DIR / "invoices_hard.jsonl")

    print("\nDone. Dataset generated successfully.")
    print(f"  PDFs:         {RAW_DIR}")
    print(f"  Ground truth: {GT_DIR}")


if __name__ == "__main__":
    main()
