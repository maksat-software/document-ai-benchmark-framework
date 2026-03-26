# Document AI Benchmark Framework

Benchmarking **OCR-first**, **text-based LLM**, and **multimodal LLM** invoice extraction pipelines under controlled
document difficulty.

## What this project is

This repository evaluates how different document AI system designs behave under real-world document conditions.

Compared approaches:

- **Azure Document Intelligence** — OCR-first
- **OpenAI GPT-5.4** — text-based LLM extraction
- **Anthropic Claude Sonnet 4.6** — text-based LLM extraction
- **Anthropic Claude Sonnet 4.6 (multimodal)** — vision-based LLM extraction

The goal is not to compare models in isolation.  
The goal is to understand **where document AI systems actually fail**.

## Why this benchmark matters

Many document AI systems look excellent on clean PDFs and then break in production.

This benchmark was designed to answer:

- How do OCR-first systems behave as document quality declines?
- How do text-based LLM pipelines behave when usable text disappears?
- What changes when multimodal models are introduced?
- What is the real bottleneck: model capability, OCR robustness, or input modality?

## Dataset design

The benchmark uses three controlled difficulty buckets:

- **Easy** — clean, digital, structured invoices
- **Medium** — varied layouts, mixed formatting, normalization ambiguity
- **Hard** — degraded / scan-like invoices with little or no machine-readable text

This makes it possible to observe **degradation patterns**, not just static accuracy numbers.

## Pipelines

### Azure OCR-first

`PDF -> Azure Document Intelligence -> normalization -> scoring`

### OpenAI text-based

`PDF -> local text extraction -> GPT-5.4 -> normalization -> scoring`

### Anthropic text-based

`PDF -> local text extraction -> Claude Sonnet 4.6 -> normalization -> scoring`

### Anthropic multimodal

`PDF -> page rendering -> Claude Sonnet 4.6 (vision) -> normalization -> scoring`

## KPI framework

The benchmark evaluates:

- **Field Accuracy** — percentage of correctly extracted fields
- **Document Exact Match** — percentage of documents where all required fields match
- **HITL Rate** — percentage of documents requiring human review
- **Parse Failure Rate** — percentage of documents where no usable structured output is produced
- **Average Latency (ms)** — average time per processed document
- **Cost per Document** — approximate unit inference cost

## Final Results

| Pipeline                    | Mode           | Easy | Medium | Hard | Avg Latency Profile        | Cost / Doc | Failure Pattern                                            |
|-----------------------------|----------------|-----:|-------:|-----:|----------------------------|-----------:|------------------------------------------------------------|
| Azure Document Intelligence | OCR-first      | 100% |    92% |  48% | ~5.6s, stable              |      $0.01 | Graceful degradation under document noise                  |
| OpenAI GPT-5.4              | Text-based LLM | 100% |   100% |   0% | ~1.4–1.8s on readable docs |      $0.03 | Catastrophic failure when no text is available             |
| Claude Sonnet 4.6           | Text-based LLM | 100% |    96% |   0% | ~1.7–2.1s on readable docs |      $0.03 | Catastrophic failure when no text is available             |
| Claude Sonnet 4.6           | Multimodal LLM |    — |      — |  68% | ~3.9s on hard docs         |      $0.05 | Recovers scan-heavy documents through visual understanding |

## Results & Interpretation

The benchmark reveals four distinct system behaviors.

### 1. OCR-first systems degrade gracefully

Azure Document Intelligence remained perfect on the easy bucket, degraded moderately on medium documents, and still
retained partial extraction capability on hard scan-like documents.

- Easy: 100%
- Medium: 92%
- Hard: 48%

This shows that OCR-first pipelines continue producing structured output even when document quality declines, but
extraction quality degrades with noise, layout variation, and weak OCR signals.

### 2. Text-based LLM pipelines are highly effective on readable documents

GPT-5.4 and Claude Sonnet performed extremely well on machine-readable invoices.

- GPT-5.4: 100% on Easy and Medium
- Claude Sonnet 4.6: 100% on Easy, 96% on Medium

This suggests that LLM-based extraction can outperform OCR-first pipelines on ambiguous but readable documents because
they resolve formatting and semantic ambiguity more effectively.

### 3. Text-based LLM pipelines collapse when text disappears

On hard scan-like documents, both text-based LLM pipelines failed completely.

- GPT-5.4 Hard: 0%
- Claude Hard: 0%

This was not caused by weak reasoning.  
It was caused by missing usable text input.

### 4. Multimodal LLMs recover part of the hard bucket

The Anthropic multimodal pipeline recovered meaningful performance on hard documents:

- Hard: 68% field accuracy
- 20% exact match
- 40% HITL
- 0% parse failure

This shows that multimodal processing can restore viability on scan-heavy documents where text-based LLM pipelines fail
completely.

## Core Interpretation

The real bottleneck is not model choice.

It is:

- input modality
- OCR robustness
- preprocessing quality
- normalization logic

More precisely:

- OCR-first systems degrade gradually
- text-based LLM systems collapse when text is unavailable
- multimodal LLMs recover part of the hard-document failure surface

## Production Implication

The most robust production architecture is not "OCR only" and not "LLM only".

A stronger architecture is:

```text
PDF -> OCR -> LLM reasoning/cleanup -> validation -> HITL
```

This benchmark supports architecture decisions based on **system behavior**, not model hype.

## Key Takeaways

- Clean PDFs hide production problems.
- OCR-first systems degrade; text-based LLM systems collapse without usable text.
- Multimodal LLMs recover scan-heavy workloads and make hybrid architectures compelling.

## What this project demonstrates

- End-to-end AI system evaluation
- KPI-driven benchmarking for document AI
- Controlled failure-mode analysis
- Comparison of OCR-first vs LLM-based extraction architectures
- Production-oriented reasoning rather than model-only benchmarking

## Repository structure

- `docs/architecture.md` — architecture and design interpretation
- `docs/benchmark_methodology.md` — evaluation setup and dataset logic
- `docs/kpis.md` — KPI definitions and scoring rules
- `scripts/generate_benchmark_charts.py` — chart generation script for benchmark results

## Local Setup

### 1. Clone the repository

```bash
git clone https://github.com/maksat-software/document-ai-benchmark-framework.git
cd document-ai-benchmark-framework
```

### 2. Create and activate a virtual environment

```bash
python -m venv .venv
source .venv/bin/activate
```

On Windows:

```bash
.venv\Scripts\activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment variables

Create a `.env` file based on `.env.example`.

Example:

```env
AZURE_DI_ENDPOINT=
AZURE_DI_KEY=
AZURE_DI_MODEL_ID=prebuilt-invoice
AZURE_DI_API_VERSION=2023-07-31

OPENAI_API_KEY=
OPENAI_MODEL=GPT-5.4

ANTHROPIC_API_KEY=
ANTHROPIC_MODEL=claude-sonnet-4-6
```

### 5. Verify dataset structure

Expected benchmark dataset layout:

```text
data/raw/invoices_easy/
data/raw/invoices_medium/
data/raw/invoices_hard/
data/ground_truth/invoices_easy.jsonl
data/ground_truth/invoices_medium.jsonl
data/ground_truth/invoices_hard.jsonl
```

### 6. Run benchmarks

Azure Document Intelligence:

```bash
python -m pipelines.run_benchmark --pipeline azure --ground-truth data/ground_truth/invoices_easy.jsonl
python -m pipelines.run_benchmark --pipeline azure --ground-truth data/ground_truth/invoices_medium.jsonl
python -m pipelines.run_benchmark --pipeline azure --ground-truth data/ground_truth/invoices_hard.jsonl
```

OpenAI GPT-5.4:

```bash
python -m pipelines.run_benchmark --pipeline openai --ground-truth data/ground_truth/invoices_easy.jsonl
python -m pipelines.run_benchmark --pipeline openai --ground-truth data/ground_truth/invoices_medium.jsonl
python -m pipelines.run_benchmark --pipeline openai --ground-truth data/ground_truth/invoices_hard.jsonl
```

Anthropic Claude Sonnet 4.6:

```bash
python -m pipelines.run_benchmark --pipeline anthropic --ground-truth data/ground_truth/invoices_easy.jsonl
python -m pipelines.run_benchmark --pipeline anthropic --ground-truth data/ground_truth/invoices_medium.jsonl
python -m pipelines.run_benchmark --pipeline anthropic --ground-truth data/ground_truth/invoices_hard.jsonl
```

Anthropic Claude Sonnet 4.6 multimodal:

```bash
python -m pipelines.run_benchmark --pipeline anthropic_multimodal --ground-truth data/ground_truth/invoices_hard.jsonl
```

### 7. Locate benchmark outputs

Generated reports are written to:

```text
benchmark/outputs/
```

### 8. Generate charts

```bash
python scripts/generate_benchmark_charts.py
```

Charts will be written to:

```text
benchmark_charts/
```

## Notes

- The repository includes both text-based and multimodal LLM benchmarks.
- Text-based LLM pipelines depend on usable extracted text.
- Multimodal evaluation is currently implemented for the Anthropic path and is especially relevant for hard scan-like
  PDFs.
- For production use, the most promising direction is a hybrid architecture:

```text
PDF -> OCR -> LLM reasoning/cleanup -> validation -> HITL
```
