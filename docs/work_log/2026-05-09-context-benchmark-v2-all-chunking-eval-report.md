# 2026-05-09 Context Benchmark V2 All Chunking Eval Report

## Scope

- Phase 5: Training & Eval.
- Benchmark:
  `data/benchmark/health_rag_context_benchmark_v2/health_rag_context_benchmark_v2.jsonl`.
- Cases: 100.
- Source selection: all expected sources from the benchmark.
- Unique source files indexed: 42.
- Strategies evaluated: 9.
- Retrieval depth: top-k = 5.
- LLM judge: not used. This is deterministic retrieval evaluation over
  persisted local Qdrant indexes.

## Code Change

`scripts/05_training_eval/run_streaming_chunking_embedding_qdrant.py` now accepts:

- `--benchmark-path`
- `--corpus-dir`

This lets the streaming Qdrant builder run against benchmark v2 directly
instead of always using the older default benchmark.

## Qdrant Build

Run directory:

- `data/eval_runs/20260509_context_benchmark_v2_all_chunking_qdrant`

Command shape:

```bash
python scripts/05_training_eval/run_streaming_chunking_embedding_qdrant.py \
  --benchmark-path data/benchmark/health_rag_context_benchmark_v2/health_rag_context_benchmark_v2.jsonl \
  --corpus-dir data/health_insurance/health_insurance_markdowns_interpreted_cleaned \
  --output-dir data/eval_runs/20260509_context_benchmark_v2_all_chunking_qdrant/out \
  --qdrant-work-dir data/eval_runs/20260509_context_benchmark_v2_all_chunking_qdrant/qdrant \
  --embedding-cache-path data/eval_runs/20260509_context_benchmark_v2_all_chunking_qdrant/embedding_cache.sqlite \
  --strategies semantic_embedding,heading_level_table_safe,markdown_header_recursive_table,insurance_contract_hybrid_late,markdown_then_semantic,table_as_one_hybrid,hierarchical_header_recursive,llm_markdown_optimal,llamaindex_markdown_element \
  --source-selection expected \
  --limit-documents 0 \
  --embedding-batch-size 2 \
  --markdown-element-llm-timeout-seconds 15 \
  --markdown-element-llm-max-slot-attempts 4 \
  --markdown-element-num-workers 0 \
  --keep-qdrant \
  --resource-sample-seconds 5
```

Build result:

| Strategy | Status | Files | Qdrant points | Build seconds |
| --- | --- | ---: | ---: | ---: |
| `semantic_embedding` | completed | 42 | 1,920 | 142.780 |
| `heading_level_table_safe` | completed | 42 | 3,101 | 39.915 |
| `markdown_header_recursive_table` | completed | 42 | 13,964 | 158.016 |
| `insurance_contract_hybrid_late` | completed | 42 | 15,006 | 171.072 |
| `markdown_then_semantic` | completed | 42 | 5,336 | 111.595 |
| `table_as_one_hybrid` | completed | 42 | 13,222 | 206.464 |
| `hierarchical_header_recursive` | completed | 42 | 9,518 | 307.826 |
| `llm_markdown_optimal` | completed | 42 | 5,012 | 472.004 |
| `llamaindex_markdown_element` | completed | 42 | 3,124 | 131.243 |

LLM chunking cache/fallback:

| Strategy | Files | Cache hits | Fallback chunks | Total chunks |
| --- | ---: | ---: | ---: | ---: |
| `llm_markdown_optimal` | 42 | 38 | 4,033 | 5,012 |
| `llamaindex_markdown_element` | 42 | 38 | 2,785 | 3,124 |

All 378 file-strategy rows completed, with 0 failed file rows.

## Retrieval Eval

Output directory:

- `data/eval_runs/20260509_context_benchmark_v2_all_chunking_retrieval_eval`

Command:

```bash
python scripts/05_training_eval/run_persisted_qdrant_retrieval_eval.py \
  --source-run-dir data/eval_runs/20260509_context_benchmark_v2_all_chunking_qdrant \
  --output-dir data/eval_runs/20260509_context_benchmark_v2_all_chunking_retrieval_eval \
  --top-k 5 \
  --embedding-batch-size 2
```

Artifacts:

- `retrieval_strategy_summary.csv`
- `retrieval_case_metrics.csv`
- `retrieval_case_type_summary.csv`
- `retrievals.jsonl`
- `retrieval_eval_report.md`
- `manifest.json`

Verification counts:

| Metric | Value |
| --- | ---: |
| Benchmark cases | 100 |
| Strategy summaries | 9 |
| Completed strategies | 9 |
| Case metric rows | 900 |
| Retrieval rows | 4,500 |

## Ranking

| Rank | Strategy | Primary hit@5 | MRR@5 | Required source recall@5 | Line overlap recall@5 |
| ---: | --- | ---: | ---: | ---: | ---: |
| 1 | `hierarchical_header_recursive` | 0.6200 | 0.3973 | 0.6200 | 0.2183 |
| 2 | `table_as_one_hybrid` | 0.6000 | 0.4222 | 0.6000 | 0.1900 |
| 3 | `markdown_then_semantic` | 0.5700 | 0.4148 | 0.5700 | 0.1050 |
| 4 | `markdown_header_recursive_table` | 0.5300 | 0.3602 | 0.5300 | 0.1350 |
| 5 | `semantic_embedding` | 0.5300 | 0.3365 | 0.5300 | 0.1183 |
| 6 | `llm_markdown_optimal` | 0.5100 | 0.3362 | 0.5100 | 0.1800 |
| 7 | `heading_level_table_safe` | 0.4800 | 0.3240 | 0.4800 | 0.1600 |
| 8 | `llamaindex_markdown_element` | 0.4600 | 0.3133 | 0.4600 | 0.1400 |
| 9 | `insurance_contract_hybrid_late` | 0.4500 | 0.3030 | 0.4500 | 0.0383 |

## Case-Type Notes

Best line-overlap recall by case type:

| Case type | Best strategy | Line overlap recall@5 | Required source recall@5 |
| --- | --- | ---: | ---: |
| `single_context` | `hierarchical_header_recursive` | 0.4667 | 0.8000 |
| `two_context` | `llm_markdown_optimal` | 0.1333 | 0.4333 |
| `three_context` | `semantic_embedding` | 0.1111 | 0.5667 |
| `table_context` | `table_as_one_hybrid` | 0.2000 | 0.7000 |

## Interpretation

- Default pick for this benchmark: `hierarchical_header_recursive`. It has the
  best required-source recall@5 and the best line-overlap recall@5 overall.
- If ranking position matters more than exact line overlap, `table_as_one_hybrid`
  is competitive and has the best MRR@5.
- `llm_markdown_optimal` is strongest among the LLM chunkers on line-overlap
  recall, but it is still behind `hierarchical_header_recursive` overall and had
  many fallback chunks in this run.
- `insurance_contract_hybrid_late` produced the most Qdrant points but the worst
  line-overlap recall on this benchmark, so it is not a good default for this
  v2 dataset without further tuning.

## Verification

Commands run:

```bash
pytest tests/unit/test_streaming_qdrant_cli.py \
  tests/unit/test_streaming_qdrant_chunking.py \
  tests/unit/test_persisted_qdrant_retrieval_eval.py \
  tests/unit/test_context_benchmark_v2.py \
  tests/unit/test_eval_llm_provider_slots.py -q
```

Result: 34 passed, 6 torchao deprecation warnings.

```bash
ruff check \
  scripts/05_training_eval/run_streaming_chunking_embedding_qdrant.py \
  tests/unit/test_streaming_qdrant_cli.py \
  src/eval/context_benchmark_v2.py \
  scripts/05_training_eval/06_generate_health_rag_context_benchmark_v2.py \
  tests/unit/test_context_benchmark_v2.py
```

Result: all checks passed.

Artifact sanity check:

```json
{
  "qdrant_strategy_rows": 9,
  "qdrant_completed_strategies": 9,
  "qdrant_file_rows": 378,
  "qdrant_failed_file_rows": 0,
  "retrieval_benchmark_cases": 100,
  "retrieval_summary_rows": 9,
  "retrieval_completed_strategies": 9,
  "retrieval_case_metric_rows": 900,
  "retrieval_rows": 4500
}
```
