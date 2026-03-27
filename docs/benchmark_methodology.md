# Benchmark Methodology

## Objective

Evaluate invoice extraction performance across OCR-first and LLM-based pipelines under increasing document difficulty.

## Compared systems

- Azure Document Intelligence (`prebuilt-invoice`)
- OpenAI GPT-5.4
- Anthropic Claude Sonnet 4.6

## Target fields

Each pipeline extracts the same required fields:

- `invoice_number`
- `invoice_date`
- `vendor_name`
- `total_amount`
- `currency`

## Dataset buckets

### Easy

Clean, digital, structured invoices.

Purpose:

- validate benchmark correctness
- establish baseline quality

### Medium

Documents with layout variation and formatting ambiguity.

Purpose:

- test semantic extraction quality
- expose normalization issues
- compare OCR-first and LLM-based reasoning

### Hard

Degraded or scan-like invoices with little or no machine-readable text.

Purpose:

- stress OCR robustness
- expose catastrophic failure modes in text-dependent pipelines

## Normalization

Before scoring, extracted values are normalized:

- dates -> ISO format where possible
- amounts -> numeric float
- currencies -> uppercase code
- strings -> trimmed

This reduces false negatives caused by representation differences.

## Scoring logic

Each run produces:

- field-level correctness
- document exact match
- HITL flagging
- parse failure detection
- latency
- cost per document

## Why controlled buckets matter

A benchmark based only on random PDFs often produces noisy conclusions.

Controlled difficulty buckets make it possible to observe:

- gradual degradation
- bottleneck shifts
- architecture-dependent failure modes

## Limitations

Current LLM pipelines are text-based, not multimodal.  
This means hard scan-like documents represent an OCR/input failure scenario for LLM extraction.

A future benchmark extension could compare:

- OCR-first
- text-based LLM
- multimodal LLM
