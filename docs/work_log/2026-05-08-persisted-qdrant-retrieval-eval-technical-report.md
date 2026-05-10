# Báo cáo đánh giá retrieval trên Qdrant persisted

> Cấu trúc báo cáo kỹ thuật được áp dụng ngày 2026-05-09. Nội dung gốc lịch sử được giữ ở Mục 10 để truy vết.

## 1. Tóm tắt điều hành

Báo cáo kỹ thuật này ghi lại tài liệu nhật ký công việc `2026-05-08-persisted-qdrant-retrieval-eval-technical-report.md` của InsureVN. Tài liệu được chuẩn hóa theo định dạng báo cáo kỹ thuật của dự án, đồng thời giữ nguyên nội dung và bằng chứng gốc bên dưới.

## 2. Mục tiêu và phạm vi

Mục tiêu là ghi lại công việc, quy trình, quyết định, benchmark hoặc inventory được mô tả trong file gốc. Phạm vi chuẩn hóa chỉ giới hạn ở tài liệu: không chạy lại benchmark, không thay đổi code triển khai và không thay đổi ý nghĩa của report gốc.

## 3. Bối cảnh

Phân loại: Giai đoạn Training & Eval và Ingestion; đánh giá retrieval trên Qdrant persisted.

Báo cáo này thuộc `docs/work_log/`, khu vực dùng cho báo cáo kỹ thuật, báo cáo benchmark, nhật ký quy trình và lịch sử triển khai của InsureVN.

## 4. Triển khai

Chi tiết triển khai, quy trình hoặc phân tích gốc được giữ trong Mục 10. Trong lần chuẩn hóa này, tài liệu được bọc bằng cấu trúc báo cáo kỹ thuật chung để các nhật ký công việc sau này có cùng bố cục về bối cảnh, bằng chứng, xác minh, kết quả, rủi ro và việc tiếp theo.

## 5. Bằng chứng và lệnh đã chạy

Bằng chứng dùng cho lần chuẩn hóa này:

- Tài liệu nguồn hiện có: `docs/work_log/2026-05-08-persisted-qdrant-retrieval-eval-technical-report.md`
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
