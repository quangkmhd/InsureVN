# 2026-05-09 - Báo cáo đánh giá Context Benchmark V2 cho toàn bộ chunking

> Cấu trúc báo cáo kỹ thuật được áp dụng ngày 2026-05-09. Nội dung gốc lịch sử được giữ ở Mục 10 để truy vết.

## 1. Tóm tắt điều hành

Báo cáo kỹ thuật này ghi lại tài liệu nhật ký công việc `2026-05-09-context-benchmark-v2-all-chunking-eval-technical-report.md` của InsureVN. Tài liệu được chuẩn hóa theo định dạng báo cáo kỹ thuật của dự án, đồng thời giữ nguyên nội dung và bằng chứng gốc bên dưới.

## 2. Mục tiêu và phạm vi

Mục tiêu là ghi lại công việc, quy trình, quyết định, benchmark hoặc inventory được mô tả trong file gốc. Phạm vi chuẩn hóa chỉ giới hạn ở tài liệu: không chạy lại benchmark, không thay đổi code triển khai và không thay đổi ý nghĩa của report gốc.

## 3. Bối cảnh

Phân loại: Giai đoạn Training & Eval; đánh giá Context Benchmark V2 trên các chiến lược chunking.

Báo cáo này thuộc `docs/work_log/`, khu vực dùng cho báo cáo kỹ thuật, báo cáo benchmark, nhật ký quy trình và lịch sử triển khai của InsureVN.

## 4. Triển khai

Chi tiết triển khai, quy trình hoặc phân tích gốc được giữ trong Mục 10. Trong lần chuẩn hóa này, tài liệu được bọc bằng cấu trúc báo cáo kỹ thuật chung để các nhật ký công việc sau này có cùng bố cục về bối cảnh, bằng chứng, xác minh, kết quả, rủi ro và việc tiếp theo.

## 5. Bằng chứng và lệnh đã chạy

Bằng chứng dùng cho lần chuẩn hóa này:

- Tài liệu nguồn hiện có: `docs/work_log/2026-05-09-context-benchmark-v2-all-chunking-eval-technical-report.md`
- Lệnh quét danh sách file: `find docs/work_log -maxdepth 2 -type f -print | sort`
- Lệnh kiểm tra heading: `rg -n '^#{1,3} ' docs/work_log/*.md`
- Kiểm tra template: đã kiểm tra sự tồn tại của `## 1. Tóm tắt điều hành` trong toàn bộ file work log

Bằng chứng, lệnh, đường dẫn, số liệu và hiện vật đầu ra riêng của task gốc vẫn được giữ trong Mục 10.

## 6. Xác minh

Các bước xác minh đã thực hiện cho lần chuẩn hóa tài liệu này:

- Đã xác nhận file nằm trong `docs/work_log/`.
- Đã thêm đầy đủ các mục bắt buộc của báo cáo kỹ thuật.
- Đã giữ nguyên phần nội dung cũ thay vì viết lại metrics hoặc kết luận lịch sử.

Xác minh riêng của task gốc, nếu có, vẫn nằm trong Mục 10.

## 7. Kết quả

Báo cáo hiện đã theo cấu trúc báo cáo kỹ thuật của InsureVN. Các kết quả, số liệu benchmark, quyết định và tham chiếu hiện vật đầu ra gốc vẫn nằm trong Mục 10.

## 8. Rủi ro và giới hạn

- Các lệnh lịch sử và kết quả benchmark không được chạy lại trong lần chuẩn hóa này.
- Bất kỳ đường dẫn, metric hoặc trạng thái nào trong nội dung gốc đều là dữ liệu lịch sử cho tới khi được xác minh lại.
- Không nên xem tài liệu này là một lần chạy đánh giá mới nếu Mục 10 không có bằng chứng xác minh hiện tại.

## 9. Việc tiếp theo

- Giữ báo cáo này đồng bộ với mã nguồn, lệnh và hiện vật đầu ra mà nó tham chiếu.
- Chạy lại bước xác minh riêng của task trước khi dùng metrics lịch sử cho quyết định kỹ thuật mới.

## 10. Nội dung gốc được giữ lại

### Scope

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

### Code Change

`scripts/05_training_eval/run_streaming_chunking_embedding_qdrant.py` now accepts:

- `--benchmark-path`
- `--corpus-dir`

This lets the streaming Qdrant builder run against benchmark v2 directly
instead of always using the older default benchmark.

### Qdrant Build

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

### Retrieval Eval

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

### Ranking

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

### Case-Type Notes

Best line-overlap recall by case type:

| Case type | Best strategy | Line overlap recall@5 | Required source recall@5 |
| --- | --- | ---: | ---: |
| `single_context` | `hierarchical_header_recursive` | 0.4667 | 0.8000 |
| `two_context` | `llm_markdown_optimal` | 0.1333 | 0.4333 |
| `three_context` | `semantic_embedding` | 0.1111 | 0.5667 |
| `table_context` | `table_as_one_hybrid` | 0.2000 | 0.7000 |

### Interpretation

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

### Verification

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
