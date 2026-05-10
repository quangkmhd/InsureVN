# Báo cáo thay thế chiến lược chunking mặc định bằng hierarchical_header_recursive

> Cấu trúc báo cáo kỹ thuật được áp dụng ngày 2026-05-09. Nội dung gốc lịch sử được giữ ở Mục 10 để truy vết.

## 1. Tóm tắt điều hành

Báo cáo kỹ thuật này ghi lại tài liệu nhật ký công việc `2026-05-09-hierarchical-default-chunking-indexing-run-technical-report.md` của InsureVN. Tài liệu được chuẩn hóa theo định dạng báo cáo kỹ thuật của dự án, đồng thời giữ nguyên nội dung và bằng chứng gốc bên dưới.

## 2. Mục tiêu và phạm vi

Mục tiêu là ghi lại công việc, quy trình, quyết định, benchmark hoặc inventory được mô tả trong file gốc. Phạm vi chuẩn hóa chỉ giới hạn ở tài liệu: không chạy lại benchmark, không thay đổi code triển khai và không thay đổi ý nghĩa của report gốc.

## 3. Bối cảnh

Phân loại: Giai đoạn Ingestion và Core Services; report chạy default hierarchical chunking và indexing.

Báo cáo này thuộc `docs/work_log/`, khu vực dùng cho báo cáo kỹ thuật, báo cáo benchmark, nhật ký quy trình và lịch sử triển khai của InsureVN.

## 4. Triển khai

Chi tiết triển khai, quy trình hoặc phân tích gốc được giữ trong Mục 10. Trong lần chuẩn hóa này, tài liệu được bọc bằng cấu trúc báo cáo kỹ thuật chung để các nhật ký công việc sau này có cùng bố cục về bối cảnh, bằng chứng, xác minh, kết quả, rủi ro và việc tiếp theo.

## 5. Bằng chứng và lệnh đã chạy

Bằng chứng dùng cho lần chuẩn hóa này:

- Tài liệu nguồn hiện có: `docs/work_log/2026-05-09-hierarchical-default-chunking-indexing-run-technical-report.md`
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

**Ngày:** 09/05/2026
**Phạm vi:** Phase 5 Training & Eval, Phase 6 Ingestion

### Kết quả chính

- Chuyển chiến lược chunking mặc định của eval/streaming/indexing sang `hierarchical_header_recursive`, chiến lược đứng đầu báo cáo đánh giá ngày 09/05/2026.
- Cập nhật `/home/quangnhvn34/dev/me/InsureVN/.env` để `RAG_CHUNKING_STRATEGY=hierarchical_header_recursive`.
- Bổ sung metadata lineage cho chunk: `chunking_strategy`, `header_hierarchy`, `header_path`, `header_level`, `section_heading`, `header_1..header_6` khi có, cùng các metadata Qdrant bắt buộc.
- Thêm bước báo cáo chất lượng metadata trước indexing để phát hiện trường thiếu, rỗng, invalid hoặc null.
- Safe eval wrapper mặc định chạy `hierarchical_header_recursive` nhưng vẫn nhận `--strategies` để đánh giá các strategy active khác khi cần.

### Metadata QA

Dry-run trên thư mục:

`/home/quangnhvn34/dev/me/InsureVN/data/health_insurance/health_insurance_markdowns_interpreted_cleaned`

Kết quả:

- `document_count`: 107
- `chunk_count`: 9933
- `missing_required_counts`: `{}`
- `empty_required_counts`: `{}`
- `invalid_required_counts`: `{}`
- `optional_null_counts`: `{}`
- `required_metadata_valid`: `true`

Artifact:

- `file:///tmp/insurevn_hierarchical_metadata_dry_run_v2.json`
- `file:///tmp/insurevn_hierarchical_qdrant_chunks_v2.json`

### Trạng thái chạy BM25 + Vector + Graph

Pipeline full được chạy bằng `.env` của dự án và override strategy sang `hierarchical_header_recursive` tại thời điểm chạy. Sau đó `.env` đã được cập nhật để các lần chạy tiếp theo dùng trực tiếp `hierarchical_header_recursive`.

- Qdrant hybrid BM25 + vector đã tạo collection và index được 64 points trước khi dừng vì Gemini embedding quota: `429 RESOURCE_EXHAUSTED`, limit 100 requests/phút cho `gemini-embedding-2`.
- Graph extraction chưa hoàn tất vì `.env` không cấu hình `KG_EXTRACTION_LLM_PROVIDER`/`KG_EXTRACTION_LLM_MODEL`; default rơi về `ollama` + `gemma4:31b-cloud` và Ollama trả `ResponseError`/`401 unauthorized`.
- Neo4j và Qdrant local đều reachable, nhưng full run chưa thể hoàn tất nếu chưa đổi quota embedding hoặc cấu hình lại KG extraction model khả dụng.

Logs:

- `file:///tmp/insurevn_hierarchical_qdrant_v2.log`
- `file:///tmp/insurevn_hierarchical_index.log`

### Verification

- `python -m ruff format --check ...`: 11 files already formatted.
- `python -m ruff check ...`: All checks passed.
- `python -m pytest tests/unit/test_eval_strategy_embeddings.py tests/unit/test_document_chunker.py tests/unit/test_config.py tests/unit/test_health_markdown_rag_indexer.py tests/unit/test_streaming_qdrant_chunking.py tests/unit/test_safe_chunking_eval_wrapper.py tests/unit/test_benchmark_health_chunking.py -q`: 58 passed.
- Dry-run sau khi cập nhật `.env`, không truyền `--chunking-strategy`: 107 tài liệu, 9933 chunks, `required_metadata_valid=true`, `invalid_required_counts={}`.
