# Persisted Qdrant Retrieval Evaluation Report

Date: 2026-05-08

Phase: Phase 5 - Training & Eval, using Phase 6 Qdrant vector indexes.

Source chunking/embedding run:
`data/eval_runs/20260508_162320_streaming_chunking_embedding_qdrant`

Evaluation output:
`data/eval_runs/20260508_162320_streaming_chunking_embedding_qdrant/retrieval_eval`

Scope:
- Read-only evaluation over persisted Qdrant indexes.
- No chunking rebuild.
- No embedding rebuild except query embeddings not already in cache.
- No LLM judge or OpenAI call.
- Top K: 5.
- Benchmark cases evaluated: 91.
- Retrieval rows: 3185.

Safety controls:
- Process pinned to one CPU core with `taskset -c 0`.
- Thread fan-out limited with `OMP_NUM_THREADS=1`, `MKL_NUM_THREADS=1`,
  `OPENBLAS_NUM_THREADS=1`, `NUMEXPR_NUM_THREADS=1`.
- After completion, RAM available was about 9.2 GiB and GPU memory returned to
  about 284 MiB.

Artifacts:
- `retrievals.jsonl`: top-5 retrieved chunks per strategy/case.
- `retrieval_case_metrics.csv`: deterministic metric per strategy/case.
- `retrieval_strategy_summary.csv`: aggregate metric per strategy.
- `retrieval_eval_report.md`: generated compact report.

Strategy summary:

| Strategy | Cases | Qdrant Points | Primary Hit@5 | Primary MRR@5 | Required Source Recall@5 | Line Overlap Recall@5 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| markdown_header_recursive_table | 91 | 6711 | 0.7473 | 0.5544 | 0.2894 | 0.0632 |
| table_as_one_hybrid | 91 | 6529 | 0.7033 | 0.5190 | 0.2839 | 0.0714 |
| semantic_embedding | 91 | 667 | 0.7253 | 0.4346 | 0.2821 | 0.0659 |
| heading_level_table_safe | 91 | 651 | 0.7143 | 0.4608 | 0.2802 | 0.0275 |
| hierarchical_header_recursive | 91 | 3478 | 0.6813 | 0.4956 | 0.2610 | 0.0604 |
| insurance_contract_hybrid_late | 91 | 6860 | 0.7143 | 0.5379 | 0.2555 | 0.0440 |
| markdown_then_semantic | 91 | 1287 | 0.6264 | 0.3940 | 0.2317 | 0.0522 |

Conclusion:

`markdown_header_recursive_table` is the best completed strategy by deterministic
required-source recall and MRR in this run. `table_as_one_hybrid` is close on
required-source recall and has the highest line-overlap recall, but it uses a
large number of chunks.

Important interpretation note:

These are retrieval-only metrics. They measure whether Qdrant returns the
expected source file and line span in top-5 contexts. They do not measure final
answer quality, faithfulness, or citation formatting. LLM judge evaluation should
be a separate run over the best few strategies, not all strategies by default,
to avoid API/rate-limit pressure.
