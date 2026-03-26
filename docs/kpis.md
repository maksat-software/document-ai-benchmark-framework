# KPI Definitions

## 1. Field Accuracy

Percentage of correctly extracted fields across all evaluated documents.

Formula:

```text
correct_fields / total_fields
```

Used to understand extraction quality at field level.

---

## 2. Document Exact Match

Percentage of documents where **all required fields** match the ground truth.

Formula:

```text
documents_with_all_fields_correct / total_documents
```

This is more operationally meaningful than field accuracy alone.

---

## 3. HITL Rate

Percentage of documents that should be routed to **human-in-the-loop review**.

Typical reasons:
- missing required fields
- unusable structured output
- normalization failure
- extraction error

Formula:

```text
documents_flagged_for_review / total_documents
```

---

## 4. Parse Failure Rate

Percentage of documents where the pipeline did not produce usable structured output.

Formula:

```text
documents_with_unusable_output / total_documents
```

This is especially important for identifying catastrophic pipeline failure.

---

## 5. Average Latency

Average processing time per document in milliseconds.

Formula:

```text
sum(latency_ms) / total_documents
```

Used to compare practical responsiveness of the evaluated architectures.

---

## 6. Cost per Document

Approximate inference cost per processed document.

This metric is useful for understanding quality / speed / cost trade-offs in production design.

---

## Why these KPIs were chosen

These KPIs together describe:

- extraction quality
- operational reliability
- human review burden
- runtime performance
- cost efficiency

That makes them suitable for production-oriented benchmark interpretation, not just demo-level comparison.
