```textmate
python -m pipelines.run_benchmark --pipeline azure
Loaded 5 documents from data/ground_truth/invoices_easy.jsonl

Running Azure Document Intelligence pipeline...
  [azure] invoice_easy_001.pdf
  [azure] invoice_easy_002.pdf
  [azure] invoice_easy_003.pdf
  [azure] invoice_easy_004.pdf
  [azure] invoice_easy_005.pdf

============================================================
  Benchmark Results: azure
============================================================
  Documents evaluated:      5
  Overall field accuracy:   100.00%
  Document exact match:     100.00%
  HITL rate:                0.00%
  Parse failure rate:       0.00%
  Avg latency (ms):         5600.8
  Cost per document:        $0.0100

  Per-field accuracy:
    invoice_number            100.00%
    invoice_date              100.00%
    vendor_name               100.00%
    total_amount              100.00%
    currency                  100.00%
============================================================

  Report saved to: benchmark/outputs/azure_20260326_230519.json
```

---

```textmate
python -m pipelines.run_benchmark --pipeline azure --ground-truth data/ground_truth/invoices_medium.jsonl
Loaded 5 documents from data/ground_truth/invoices_medium.jsonl

Running Azure Document Intelligence pipeline...
  [azure] invoice_medium_001.pdf
  [azure] invoice_medium_002.pdf
  [azure] invoice_medium_003.pdf
  [azure] invoice_medium_004.pdf
  [azure] invoice_medium_005.pdf

============================================================
  Benchmark Results: azure
============================================================
  Documents evaluated:      5
  Overall field accuracy:   92.00%
  Document exact match:     60.00%
  HITL rate:                0.00%
  Parse failure rate:       0.00%
  Avg latency (ms):         5613.4
  Cost per document:        $0.0100

  Per-field accuracy:
    invoice_number            100.00%
    invoice_date              100.00%
    vendor_name               100.00%
    total_amount              100.00%
    currency                  60.00%
============================================================

  Report saved to: benchmark/outputs/azure_20260326_230711.json
```

---

```textmate
python -m pipelines.run_benchmark --pipeline azure --ground-truth data/ground_truth/invoices_hard.jsonl
Loaded 5 documents from data/ground_truth/invoices_hard.jsonl

Running Azure Document Intelligence pipeline...
  [azure] invoice_hard_001.pdf
  [azure] invoice_hard_002.pdf
  [azure] invoice_hard_003.pdf
  [azure] invoice_hard_004.pdf
  [azure] invoice_hard_005.pdf

============================================================
  Benchmark Results: azure
============================================================
  Documents evaluated:      5
  Overall field accuracy:   48.00%
  Document exact match:     0.00%
  HITL rate:                60.00%
  Parse failure rate:       0.00%
  Avg latency (ms):         5683.4
  Cost per document:        $0.0100

  Per-field accuracy:
    invoice_number            20.00%
    invoice_date              80.00%
    vendor_name               0.00%
    total_amount              60.00%
    currency                  80.00%
============================================================

  Report saved to: benchmark/outputs/azure_20260326_230823.json
```

---

```textmate
python -m pipelines.run_benchmark --pipeline openai --ground-truth data/ground_truth/invoices_easy.jsonl
Loaded 5 documents from data/ground_truth/invoices_easy.jsonl

Running OpenAI pipeline...
  [openai] invoice_easy_001.pdf
  [openai] invoice_easy_002.pdf
  [openai] invoice_easy_003.pdf
  [openai] invoice_easy_004.pdf
  [openai] invoice_easy_005.pdf

============================================================
  Benchmark Results: openai
============================================================
  Documents evaluated:      5
  Overall field accuracy:   100.00%
  Document exact match:     100.00%
  HITL rate:                0.00%
  Parse failure rate:       0.00%
  Avg latency (ms):         1807.4
  Cost per document:        $0.0300

  Per-field accuracy:
    invoice_number            100.00%
    invoice_date              100.00%
    vendor_name               100.00%
    total_amount              100.00%
    currency                  100.00%
============================================================

  Report saved to: benchmark/outputs/openai_20260327_001342.json
```

---

```textmate
python -m pipelines.run_benchmark --pipeline openai --ground-truth data/ground_truth/invoices_medium.jsonl
Loaded 5 documents from data/ground_truth/invoices_medium.jsonl

Running OpenAI pipeline...
  [openai] invoice_medium_001.pdf
  [openai] invoice_medium_002.pdf
  [openai] invoice_medium_003.pdf
  [openai] invoice_medium_004.pdf
  [openai] invoice_medium_005.pdf

============================================================
  Benchmark Results: openai
============================================================
  Documents evaluated:      5
  Overall field accuracy:   100.00%
  Document exact match:     100.00%
  HITL rate:                0.00%
  Parse failure rate:       0.00%
  Avg latency (ms):         1397.2
  Cost per document:        $0.0300

  Per-field accuracy:
    invoice_number            100.00%
    invoice_date              100.00%
    vendor_name               100.00%
    total_amount              100.00%
    currency                  100.00%
============================================================

  Report saved to: benchmark/outputs/openai_20260327_001723.json
```

---

```textmate
python -m pipelines.run_benchmark --pipeline openai --ground-truth data/ground_truth/invoices_hard.jsonl
Loaded 5 documents from data/ground_truth/invoices_hard.jsonl

Running OpenAI pipeline...
  [openai] invoice_hard_001.pdf
  [openai] invoice_hard_002.pdf
  [openai] invoice_hard_003.pdf
  [openai] invoice_hard_004.pdf
  [openai] invoice_hard_005.pdf

============================================================
  Benchmark Results: openai
============================================================
  Documents evaluated:      5
  Overall field accuracy:   0.00%
  Document exact match:     0.00%
  HITL rate:                100.00%
  Parse failure rate:       100.00%
  Avg latency (ms):         0.0
  Cost per document:        $0.0300

  Per-field accuracy:
    invoice_number            0.00%
    invoice_date              0.00%
    vendor_name               0.00%
    total_amount              0.00%
    currency                  0.00%
============================================================

  Report saved to: benchmark/outputs/openai_20260327_001748.json
```

---

```textmate
python -m pipelines.run_benchmark --pipeline anthropic --ground-truth data/ground_truth/invoices_easy.jsonl
Loaded 5 documents from data/ground_truth/invoices_easy.jsonl

Running Anthropic pipeline...
  [anthropic] invoice_easy_001.pdf
  [anthropic] invoice_easy_002.pdf
  [anthropic] invoice_easy_003.pdf
  [anthropic] invoice_easy_004.pdf
  [anthropic] invoice_easy_005.pdf

============================================================
  Benchmark Results: anthropic
============================================================
  Documents evaluated:      5
  Overall field accuracy:   100.00%
  Document exact match:     100.00%
  HITL rate:                0.00%
  Parse failure rate:       0.00%
  Avg latency (ms):         2101.8
  Cost per document:        $0.0300

  Per-field accuracy:
    invoice_number            100.00%
    invoice_date              100.00%
    vendor_name               100.00%
    total_amount              100.00%
    currency                  100.00%
============================================================

  Report saved to: benchmark/outputs/anthropic_20260327_003741.json
```

---

```textmate
python -m pipelines.run_benchmark --pipeline anthropic --ground-truth data/ground_truth/invoices_medium.jsonl 
Loaded 5 documents from data/ground_truth/invoices_medium.jsonl

Running Anthropic pipeline...
  [anthropic] invoice_medium_001.pdf
  [anthropic] invoice_medium_002.pdf
  [anthropic] invoice_medium_003.pdf
  [anthropic] invoice_medium_004.pdf
  [anthropic] invoice_medium_005.pdf

============================================================
  Benchmark Results: anthropic
============================================================
  Documents evaluated:      5
  Overall field accuracy:   96.00%
  Document exact match:     80.00%
  HITL rate:                0.00%
  Parse failure rate:       0.00%
  Avg latency (ms):         1747.4
  Cost per document:        $0.0300

  Per-field accuracy:
    invoice_number            80.00%
    invoice_date              100.00%
    vendor_name               100.00%
    total_amount              100.00%
    currency                  100.00%
============================================================

  Report saved to: benchmark/outputs/anthropic_20260327_004005.json
```

---

```textmate
python -m pipelines.run_benchmark --pipeline anthropic --ground-truth data/ground_truth/invoices_hard.jsonl  
Loaded 5 documents from data/ground_truth/invoices_hard.jsonl

Running Anthropic pipeline...
  [anthropic] invoice_hard_001.pdf
  [anthropic] invoice_hard_002.pdf
  [anthropic] invoice_hard_003.pdf
  [anthropic] invoice_hard_004.pdf
  [anthropic] invoice_hard_005.pdf

============================================================
  Benchmark Results: anthropic
============================================================
  Documents evaluated:      5
  Overall field accuracy:   0.00%
  Document exact match:     0.00%
  HITL rate:                100.00%
  Parse failure rate:       100.00%
  Avg latency (ms):         0.0
  Cost per document:        $0.0300

  Per-field accuracy:
    invoice_number            0.00%
    invoice_date              0.00%
    vendor_name               0.00%
    total_amount              0.00%
    currency                  0.00%
============================================================

  Report saved to: benchmark/outputs/anthropic_20260327_004012.json
```

```textmate
python -m pipelines.run_benchmark --pipeline anthropic_multimodal --ground-truth data/ground_truth/invoices_hard.jsonl
Loaded 5 documents from data/ground_truth/invoices_hard.jsonl

Running Anthropic multimodal pipeline...
  [anthropic_multimodal] invoice_hard_001.pdf
  [anthropic_multimodal] invoice_hard_002.pdf
  [anthropic_multimodal] invoice_hard_003.pdf
  [anthropic_multimodal] invoice_hard_004.pdf
  [anthropic_multimodal] invoice_hard_005.pdf

============================================================
  Benchmark Results: anthropic_multimodal
============================================================
  Documents evaluated:      5
  Overall field accuracy:   68.00%
  Document exact match:     20.00%
  HITL rate:                40.00%
  Parse failure rate:       0.00%
  Avg latency (ms):         3892.2
  Cost per document:        $0.0500

  Per-field accuracy:
    invoice_number            60.00%
    invoice_date              60.00%
    vendor_name               20.00%
    total_amount              100.00%
    currency                  100.00%
============================================================

  Report saved to: benchmark/outputs/anthropic_multimodal_20260327_014511.json
```