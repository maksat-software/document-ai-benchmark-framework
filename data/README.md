# Benchmark Dataset

Synthetic invoice and receipt PDFs for evaluating document extraction pipelines.

## Structure

```
data/
  raw/
    invoices_easy/     5 clean, standard-layout invoice PDFs
    invoices_medium/   5 invoices with varied formats, mixed languages
    invoices_hard/     5 scan-degraded invoices with noise and rotation
    receipts_ood/      3 receipt PDFs (out-of-distribution)
  ground_truth/
    invoices_easy.jsonl
    invoices_medium.jsonl
    invoices_hard.jsonl
```

## Difficulty buckets

### invoices_easy

Clean, digital-native PDFs with standard US invoice layout. One page, clear field
placement, no OCR noise. Serves as a **baseline**: any pipeline should score well here.
If a pipeline fails on easy invoices, the issue is in extraction logic, not document quality.

### invoices_medium

Realistic variation: German/European layouts, mixed field labels (Rechnungsnummer,
Rechnungsdatum), different date formats (DD.MM.YYYY, DD/MM/YYYY), European number
formatting (1.234,56), and varied visual layouts. Tests whether a pipeline can handle
**format diversity** without manual rules for each variant.

### invoices_hard

Image-based PDFs with scan-like degradation: slight rotation, Gaussian blur, speckle
noise, reduced contrast, and aged-paper effects. Some include stamps ("PAID") and
handwritten notes. Two documents are multipage. Vendor names include Japanese, Spanish,
Turkish, Russian, and Arabic characters. Tests **robustness under real-world conditions**.

### receipts_ood (out-of-distribution)

Narrow receipt-format PDFs that are structurally different from invoices. These are
**not included in KPI calculation** by default. They exist to test:

- Whether a pipeline incorrectly extracts invoice fields from non-invoice documents
- Error handling when document type doesn't match expectations
- Robustness signals for production deployment readiness

## Why separate difficulty levels?

Aggregating all results into a single accuracy number hides important failure patterns.
Splitting by difficulty lets you answer:

- "Does our pipeline work at all?" (easy)
- "Can it handle real-world variation?" (medium)
- "Is it production-ready for noisy inputs?" (hard)

A pipeline scoring 100% on easy but 40% on hard reveals very different things than
one scoring 70% across the board.

## Ground truth format

Each JSONL line:

```json
{
  "document_id": "invoice_easy_001.pdf",
  "file_path": "data/raw/invoices_easy/invoice_easy_001.pdf",
  "difficulty": "easy",
  "document_type": "invoice",
  "expected": {
    "invoice_number": "INV-2026-0001",
    "invoice_date": "2026-03-11",
    "vendor_name": "Acme Solutions Inc.",
    "total_amount": 9771.69,
    "currency": "USD"
  }
}
```

## Regeneration

```bash
python data/generate_dataset.py
```

Requires: `pip install reportlab Pillow numpy`

The script uses `random.seed(42)` for deterministic output. Re-running produces
identical PDFs and ground truth.

## Assumptions

- All data is synthetic. No real companies, people, or financial data.
- Vendor names are fictional but plausible across multiple countries/languages.
- Amounts and dates are randomized but realistic in range.
- "Hard" difficulty simulates scan artifacts, not adversarial attacks.
- Ground truth dates are always normalized to YYYY-MM-DD regardless of display format.
- Ground truth amounts are always plain floats regardless of display formatting.
