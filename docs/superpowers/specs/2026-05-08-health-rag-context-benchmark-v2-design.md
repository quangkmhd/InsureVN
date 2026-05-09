# Health RAG Context Benchmark V2 Design

## Goal

Create a separate benchmark dataset for evaluating InsureVN RAG retrieval and
chunking strategies with LLM-generated Vietnamese question/answer pairs grounded
in large source contexts.

The new dataset does not replace `data/benchmark/health_rag_benchmark`. It writes
to `data/benchmark/health_rag_context_benchmark_v2` so the existing line-level
benchmark can remain available for comparison.

## Inputs

- Source corpus:
  `data/health_insurance/health_insurance_markdowns_interpreted_cleaned`
- File scope: all Markdown files under the corpus, excluding paths containing
  `benchmark`, `test`, or `sample`.
- Context unit: large source chunks approximating one page, using a target of
  1500 whitespace tokens per context chunk.

## Dataset Shape

The generator must produce exactly 100 valid benchmark cases:

| Case type | Count | Contexts per prompt |
| --- | ---: | ---: |
| `single_context` | 30 | 1 |
| `two_context` | 30 | 2 |
| `three_context` | 30 | 3 |
| `table_context` | 10 | at least 1 context containing a Markdown table |

The 10 table cases are a separate group, not overlapping labels on the other
90 cases.

## LLM Generation

Generation uses approach 1 from brainstorming: a dedicated context-benchmark
generator whose output schema stays compatible with the existing RAG eval
loaders.

The LLM execution model is intentionally parallel:

- Load provider slots from the existing eval environment key conventions.
- Use up to 21 slots concurrently by default.
- Assign work across the active slots in round-robin order.
- Do not create deterministic fallback cases.
- Retry failed or invalid LLM calls up to 2 times for the same candidate.
- Write failed candidates to `failed_cases.jsonl`.
- Continue sampling new candidates until each case-type quota is satisfied or
  the maximum candidate-attempt budget is exhausted.

## Output Files

Output directory:
`data/benchmark/health_rag_context_benchmark_v2`

Files:

- `health_rag_context_benchmark_v2.jsonl`: canonical benchmark.
- `health_rag_context_benchmark_v2.csv`: spreadsheet copy.
- `context_chunks.jsonl`: sampled context chunks used by accepted cases.
- `failed_cases.jsonl`: candidates that failed after retries.
- `manifest.json`: run config, counts, provider-slot summary, and timing.
- `README.md`: schema and run summary.

## Case Schema

Each JSONL row follows the existing benchmark loader convention:

- `id`
- `financebench_id`
- `case_type`
- `task_type`
- `risk_level`
- `question`
- `gold_answer`
- `expected_behavior`
- `expected_sources`
- `source_constraints`
- `scoring`
- `generator`

Each `expected_sources` entry preserves:

- `provider`
- `source_path`
- `line_start`
- `line_end`
- `answer`
- `evidence_quote`
- `relationship`
- `chunk_id`
- `context_token_count`
- `contains_table`

## Validation

A generated case is accepted only when:

- `question` and `gold_answer` are non-empty.
- `evidence_quotes` is a non-empty list.
- Every evidence quote appears verbatim after whitespace normalization in one of
  the provided contexts.
- Multi-context cases include evidence from every context chunk in the prompt.
- `table_context` cases include at least one context chunk with a Markdown table.
- Source files referenced by accepted cases exist.

## Testing

Unit tests cover:

- Context chunking by approximate token count with source line metadata.
- Markdown table detection.
- Sampling quotas for 30/30/30/10 case groups.
- Retry behavior with exactly two retries before failure.
- Accepted case serialization in the existing eval-compatible schema.

## Reporting

After a real run, write a work-log report under `docs/work_log` with:

- branch name,
- command used,
- provider-slot count and worker count,
- accepted/failed counts,
- per-case-type distribution,
- output paths,
- verification commands and results.
