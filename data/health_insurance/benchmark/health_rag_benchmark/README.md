# Health Insurance RAG Benchmark

Generated benchmark inspired by FinanceBench-style JSONL outputs, adapted for Vietnamese health insurance RAG.

## Files

- `health_insurance_rag_benchmark.jsonl`: canonical benchmark cases.
- `health_insurance_rag_benchmark.csv`: spreadsheet-friendly copy.
- `manifest.json`: generation settings and provider-slot summary.

## Schema Highlights

- `question`, `gold_answer`: FinanceBench-like fields for evaluation.
- `case_type`: `single_source_answer` or `multi_source_answer`.
- `expected_sources`: list of grounded sources with `source_path`, `line_start`, `line_end`, `evidence_quote`.
- `scoring`: retrieval, evidence, answer faithfulness, and citation rubric.

## Counts

- Cases: 150
- Multi-source cases: 147
- Single-source cases: 3

For multi-source questions, the target RAG behavior is to return separate answers grouped by provider/source rather than one universal insurance rule.
