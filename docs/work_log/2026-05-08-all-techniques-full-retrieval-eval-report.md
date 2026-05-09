# 2026-05-08 All Techniques Full Retrieval Eval Report

## Scope

- Phase 5: Training & Eval - deterministic retrieval evaluation for all chunking techniques.
- Phase 6: Ingestion validation - verify already-built Qdrant indexes can retrieve benchmark evidence.
- Benchmark: full `data/benchmark/health_rag_benchmark` set, 150 cases.
- Retrieval depth: top-k = 5.
- LLM calls: none. This run embeds benchmark questions and searches persisted local Qdrant indexes.

## Source Runs

- Non-LLM chunking indexes: `data/eval_runs/20260508_164948_all_expected_sources_streaming_chunking_embedding_qdrant`
- LLM chunking indexes: `data/eval_runs/20260508_192809_llm_chunking_all_expected_cached_parallel_fixed`
- Eval output: `data/eval_runs/20260508_195146_all_techniques_full_retrieval_eval`

## Ranking

| Rank | Strategy | Cases | Qdrant points | Primary hit@5 | MRR@5 | Required source recall@5 | Line overlap recall@5 |
| ---: | :--- | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | `markdown_header_recursive_table` | 150 | 16,358 | 0.4067 | 0.2671 | 0.2661 | 0.0817 |
| 2 | `table_as_one_hybrid` | 150 | 15,129 | 0.4067 | 0.2634 | 0.2533 | 0.0833 |
| 3 | `insurance_contract_hybrid_late` | 150 | 17,566 | 0.3800 | 0.2534 | 0.2056 | 0.0300 |
| 4 | `hierarchical_header_recursive` | 150 | 11,673 | 0.3600 | 0.2300 | 0.2494 | 0.0550 |
| 5 | `llm_markdown_optimal` | 150 | 6,315 | 0.3467 | 0.2270 | 0.2661 | 0.0850 |
| 6 | `llamaindex_markdown_element` | 150 | 3,850 | 0.3133 | 0.2062 | 0.2400 | 0.0617 |
| 7 | `heading_level_table_safe` | 150 | 3,816 | 0.3067 | 0.1960 | 0.2344 | 0.0583 |
| 8 | `semantic_embedding` | 150 | 2,232 | 0.2733 | 0.1749 | 0.2161 | 0.1133 |
| 9 | `markdown_then_semantic` | 150 | 6,759 | 0.2600 | 0.2047 | 0.1917 | 0.0733 |

## Interpretation

- Best overall by primary-hit and MRR: `markdown_header_recursive_table`.
- `table_as_one_hybrid` ties primary hit@5 with the best strategy, but has slightly lower MRR and required-source recall.
- `llm_markdown_optimal` has fewer points than most large deterministic strategies and ties the best required-source recall@5, but primary hit@5 is lower.
- `semantic_embedding` has the best line-overlap recall@5, but much lower primary hit@5 and MRR.
- The LLM chunking strategies completed successfully, but many chunks were deterministic fallback chunks due provider rate limits/timeouts during chunking. Retrieval eval itself did not call LLMs.

## Artifacts

- Combined summary CSV: `data/eval_runs/20260508_195146_all_techniques_full_retrieval_eval/combined_strategy_summary.csv`
- Non-LLM eval summary: `data/eval_runs/20260508_195146_all_techniques_full_retrieval_eval/non_llm_retrieval_eval/retrieval_strategy_summary.csv`
- LLM eval summary: `data/eval_runs/20260508_195146_all_techniques_full_retrieval_eval/llm_retrieval_eval/retrieval_strategy_summary.csv`
- Non-LLM case metrics: `data/eval_runs/20260508_195146_all_techniques_full_retrieval_eval/non_llm_retrieval_eval/retrieval_case_metrics.csv`
- LLM case metrics: `data/eval_runs/20260508_195146_all_techniques_full_retrieval_eval/llm_retrieval_eval/retrieval_case_metrics.csv`

## Verification

- Strategy summaries: 9/9 completed, 0 failed.
- Case metric rows: 1,050 non-LLM rows + 300 LLM rows = 1,350 rows.
- Retrieval rows: each strategy evaluated 150 cases at top-k 5, producing 750 retrieval rows per strategy.
