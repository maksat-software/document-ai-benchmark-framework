# Architecture Notes

## Purpose

This document explains the architectural meaning of the benchmark results.

The benchmark does not compare models in isolation.  
It compares **document AI system designs**.

## Evaluated architectures

### Azure OCR-first
```text
PDF -> Azure Document Intelligence -> normalization -> scoring
```

Strengths:
- Works on image-heavy or degraded documents
- Produces output even under difficult OCR conditions
- Graceful degradation on hard documents

Weaknesses:
- Lower semantic flexibility on medium-complexity layouts
- Sensitive to normalization and representation issues
- Can return plausible but partially incorrect structured output

### OpenAI / Claude text-based LLM extraction
```text
PDF -> local text extraction -> LLM -> normalization -> scoring
```

Strengths:
- Strong semantic extraction on machine-readable documents
- Excellent handling of ambiguous formatting and mixed representations
- High accuracy on easy and medium buckets

Weaknesses:
- Depends completely on upstream text availability
- Catastrophic failure on scan-like/image-only inputs
- No graceful degradation without OCR

## Architectural conclusion

The benchmark supports a hybrid design:

```text
PDF -> OCR -> LLM cleanup/reasoning -> validation -> HITL
```

This combines:
- OCR robustness on difficult inputs
- LLM flexibility on ambiguous extraction
- validation and HITL for operational safety

## Why the hard bucket matters

Hard documents are where production reality begins.

A system that is perfect on clean PDFs but unusable on degraded scans is not production-ready for many document-heavy workflows.

## Recommended production direction

Not implemented in this repository, but logically supported by the findings:

- document-quality routing
- OCR fallback
- confidence-based human review
- multimodal evaluation for scan-heavy PDFs
