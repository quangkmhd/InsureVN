# 2026-05-08 - Báo cáo đánh giá retrieval đầy đủ cho toàn bộ kỹ thuật

> Cấu trúc báo cáo kỹ thuật được áp dụng ngày 2026-05-09. Nội dung gốc lịch sử được giữ ở Mục 10 để truy vết.

## 1. Tóm tắt điều hành

Báo cáo kỹ thuật này ghi lại tài liệu nhật ký công việc `2026-05-08-all-techniques-full-retrieval-eval-technical-report.md` của InsureVN. Tài liệu được chuẩn hóa theo định dạng báo cáo kỹ thuật của dự án, đồng thời giữ nguyên nội dung và bằng chứng gốc bên dưới.

## 2. Mục tiêu và phạm vi

Mục tiêu là ghi lại công việc, quy trình, quyết định, benchmark hoặc inventory được mô tả trong file gốc. Phạm vi chuẩn hóa chỉ giới hạn ở tài liệu: không chạy lại benchmark, không thay đổi code triển khai và không thay đổi ý nghĩa của report gốc.

## 3. Bối cảnh

Phân loại: Giai đoạn Training & Eval; đánh giá retrieval trên nhiều kỹ thuật chunking.

Báo cáo này thuộc `docs/work_log/`, khu vực dùng cho báo cáo kỹ thuật, báo cáo benchmark, nhật ký quy trình và lịch sử triển khai của InsureVN.

## 4. Triển khai

Chi tiết triển khai, quy trình hoặc phân tích gốc được giữ trong Mục 10. Trong lần chuẩn hóa này, tài liệu được bọc bằng cấu trúc báo cáo kỹ thuật chung để các nhật ký công việc sau này có cùng bố cục về bối cảnh, bằng chứng, xác minh, kết quả, rủi ro và việc tiếp theo.

## 5. Bằng chứng và lệnh đã chạy

Bằng chứng dùng cho lần chuẩn hóa này:

- Tài liệu nguồn hiện có: `docs/work_log/2026-05-08-all-techniques-full-retrieval-eval-technical-report.md`
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

- Phase 5: Training & Eval - deterministic retrieval evaluation for all chunking techniques.
- Phase 6: Ingestion validation - verify already-built Qdrant indexes can retrieve benchmark evidence.
- Benchmark: full `data/benchmark/health_rag_benchmark` set, 150 cases.
- Retrieval depth: top-k = 5.
- LLM calls: none. This run embeds benchmark questions and searches persisted local Qdrant indexes.

### Source Runs

- Non-LLM chunking indexes: `data/eval_runs/20260508_164948_all_expected_sources_streaming_chunking_embedding_qdrant`
- LLM chunking indexes: `data/eval_runs/20260508_192809_llm_chunking_all_expected_cached_parallel_fixed`
- Eval output: `data/eval_runs/20260508_195146_all_techniques_full_retrieval_eval`

### Ranking

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

### Interpretation

- Best overall by primary-hit and MRR: `markdown_header_recursive_table`.
- `table_as_one_hybrid` ties primary hit@5 with the best strategy, but has slightly lower MRR and required-source recall.
- `llm_markdown_optimal` has fewer points than most large deterministic strategies and ties the best required-source recall@5, but primary hit@5 is lower.
- `semantic_embedding` has the best line-overlap recall@5, but much lower primary hit@5 and MRR.
- The LLM chunking strategies completed successfully, but many chunks were deterministic fallback chunks due provider rate limits/timeouts during chunking. Retrieval eval itself did not call LLMs.

### Artifacts

- Combined summary CSV: `data/eval_runs/20260508_195146_all_techniques_full_retrieval_eval/combined_strategy_summary.csv`
- Non-LLM eval summary: `data/eval_runs/20260508_195146_all_techniques_full_retrieval_eval/non_llm_retrieval_eval/retrieval_strategy_summary.csv`
- LLM eval summary: `data/eval_runs/20260508_195146_all_techniques_full_retrieval_eval/llm_retrieval_eval/retrieval_strategy_summary.csv`
- Non-LLM case metrics: `data/eval_runs/20260508_195146_all_techniques_full_retrieval_eval/non_llm_retrieval_eval/retrieval_case_metrics.csv`
- LLM case metrics: `data/eval_runs/20260508_195146_all_techniques_full_retrieval_eval/llm_retrieval_eval/retrieval_case_metrics.csv`

### Verification

- Strategy summaries: 9/9 completed, 0 failed.
- Case metric rows: 1,050 non-LLM rows + 300 LLM rows = 1,350 rows.
- Retrieval rows: each strategy evaluated 150 cases at top-k 5, producing 750 retrieval rows per strategy.
