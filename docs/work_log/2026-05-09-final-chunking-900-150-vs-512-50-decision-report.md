# 2026-05-09 Final Chunking 900/150 vs 512/50 Decision Report

## Scope

- Phase 5: Training & Eval.
- Benchmark:
  `data/benchmark/health_rag_context_benchmark_v2/health_rag_context_benchmark_v2.jsonl`.
- Cases: 100.
- Retrieval eval: persisted Qdrant, dense retrieval, no LLM judge.
- Branch decision: `feat/hierarchical-table-chunking` was **not merged** and
  was deleted after evaluation.

## Decision

Keep the eval baseline configuration:

- `DEFAULT_CHUNK_SIZE = 900`
- `DEFAULT_CHUNK_OVERLAP = 150`

Do **not** replace the baseline with `512/50`.

Keep `hierarchical_header_recursive` as the preferred benchmark winner. Do
**not** replace it with the combined
`hierarchical_header_recursive_table_aware` approach for the current retrieval
benchmark.

## Evidence

### Top-K=5

| Param | Strategy | Points | MRR@5 | Source recall@5 | Line overlap@5 |
| --- | --- | ---: | ---: | ---: | ---: |
| 900/150 | `hierarchical_header_recursive` | 9,518 | 0.3973 | 0.6200 | 0.2183 |
| 900/150 | `table_as_one_hybrid` | 13,222 | 0.4222 | 0.6000 | 0.1900 |
| pre-512 combined | `hierarchical_header_recursive_table_aware` | 12,105 | 0.3818 | 0.5800 | 0.1817 |
| 512/50 | `hierarchical_header_recursive` | 16,354 | 0.3668 | 0.5300 | 0.1600 |
| 512/50 | `table_as_one_hybrid` | 19,454 | 0.3625 | 0.5400 | 0.1467 |
| 512/50 | `hierarchical_header_recursive_table_aware` | 16,266 | 0.3588 | 0.5300 | 0.1750 |

At top-k=5, `hierarchical_header_recursive` with `900/150` is the best broad
retrieval choice:

- It beats `hierarchical_header_recursive` with `512/50` by `+0.0900`
  source recall and `+0.0583` line overlap.
- It beats the combined table-aware method at `512/50` by `+0.0900`
  source recall and `+0.0433` line overlap.
- It beats the best pre-512 combined table-aware run by `+0.0400`
  source recall and `+0.0366` line overlap.

### Top-K=10

| Param | Strategy | Points | MRR@10 | Source recall@10 | Line overlap@10 |
| --- | --- | ---: | ---: | ---: | ---: |
| 900/150 | `hierarchical_header_recursive` | 9,518 | 0.4126 | 0.7300 | 0.2533 |
| 900/150 | `table_as_one_hybrid` | 13,222 | 0.4373 | 0.7100 | 0.2650 |
| pre-512 combined | `hierarchical_header_recursive_table_aware` | 12,105 | 0.3936 | 0.6700 | 0.2317 |
| 512/50 | `hierarchical_header_recursive` | 16,354 | 0.3881 | 0.7000 | 0.1967 |
| 512/50 | `table_as_one_hybrid` | 19,454 | 0.3812 | 0.6800 | 0.1917 |
| 512/50 | `hierarchical_header_recursive_table_aware` | 16,266 | 0.3721 | 0.6300 | 0.2400 |

At top-k=10, increasing retrieval depth helps smaller chunks, but it does not
change the main decision:

- `hierarchical_header_recursive` with `900/150` still has the best source
  recall among the three method families: `0.7300`.
- `table_as_one_hybrid` with `900/150` has the best MRR and line overlap, but
  its source recall remains below `hierarchical_header_recursive`.
- The combined table-aware method with `512/50` improves table locality, but
  its total source recall is only `0.6300`, below `hierarchical_header_recursive`
  at both `900/150` and `512/50`.

## Why 900/150 Beats 512/50

The benchmark questions were generated from larger source contexts, while
retrieval is scored over final Qdrant chunks. `512/50` fragments evidence more
aggressively:

- `hierarchical_header_recursive` grows from `9,518` points at `900/150` to
  `16,354` points at `512/50`.
- More points means more near-candidates compete for the same top-k budget.
- Multi-context questions need evidence from multiple contexts; smaller chunks
  consume more top-k slots to cover the same answer.
- The embedding model ranks chunk text only. Metadata is stored as payload and
  does not help dense vector ranking.

So `512/50` can improve locality in some cases, but it lowers broad retrieval
recall under raw dense top-k scoring.

## Why Hierarchical Beats The Combined Method

The combined method was intended as:

`hierarchical_header_recursive + table_as_one_hybrid`

But in practice it is not a simple additive merge. It creates a new chunk space:

- Table chunks, row-group chunks, repeated headers, and interpretation chunks
  compete with normal prose chunks.
- The current evaluator retrieves raw chunks. It does not expand by
  `table_group_id`, fetch linked `table_interpretation`, or collapse table
  groups before scoring.
- Benchmark v2 has only 10 table cases out of 100. Table-specific gains cannot
  compensate for lower broad recall across non-table cases.
- The combined method changes chunk boundaries around sections containing
  tables and interpretations, so it does not preserve the exact
  `hierarchical_header_recursive` non-table behavior.

The combined method is useful as a production evidence-lineage idea, but the
current benchmark rewards direct top-k source recall. For that benchmark,
`hierarchical_header_recursive` remains better.

## Final Recommendation

Use this as the current benchmark default:

```python
DEFAULT_CHUNK_SIZE = 900
DEFAULT_CHUNK_OVERLAP = 150
strategy = "hierarchical_header_recursive"
```

Do not adopt `512/50` as the eval default based on the current evidence. Do not
merge the combined table-aware branch into main.

If table-aware chunking is revisited later, evaluate it with a group-aware
retrieval pipeline:

1. Dense prefetch top 20-50.
2. Expand table chunks by `table_group_id`.
3. Attach linked `table_interpretation`.
4. Rerank or collapse evidence groups.
5. Score final evidence groups, not only raw chunks.

## Artifacts

- Baseline top-k=5:
  `data/eval_runs/20260509_context_benchmark_v2_all_chunking_retrieval_eval`
- Baseline top-k=10:
  `data/eval_runs/20260509_context_benchmark_v2_all_chunking_retrieval_eval_top10`
- HHR 512/50 top-k=5:
  `data/eval_runs/20260509_context_benchmark_v2_hhr_512_retrieval_eval`
- HHR 512/50 top-k=10:
  `data/eval_runs/20260509_context_benchmark_v2_hhr_512_retrieval_eval_top10`
- table-as-one 512/50 top-k=5:
  `data/eval_runs/20260509_context_benchmark_v2_table_as_one_512_retrieval_eval_top5`
- table-as-one 512/50 top-k=10:
  `data/eval_runs/20260509_context_benchmark_v2_table_as_one_512_retrieval_eval_top10`
- combined table-aware 512/50 top-k=5:
  `data/eval_runs/20260509_context_benchmark_v2_hhrr_table_aware_512_retrieval_eval`
- combined table-aware 512/50 top-k=10:
  `data/eval_runs/20260509_context_benchmark_v2_hhrr_table_aware_512_retrieval_eval_top10`

## Verification

- Removed worktree:
  `/home/quangnhvn34/dev/me/InsureVN/.worktrees/hierarchical-table-chunking`
- Deleted branch:
  `feat/hierarchical-table-chunking`
- Verified only `main` remains in `git worktree list`.
- Ran top-k=5 retrieval eval for `table_as_one_hybrid` at `512/50` to complete
  the comparison matrix.

Note: retrieval commands emitted the existing torchao compatibility warning for
Torch `2.6.0+cu124` and torchao `0.15.0`; it did not stop evaluation.
