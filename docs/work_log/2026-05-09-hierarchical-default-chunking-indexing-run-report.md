# Báo cáo thay thế chiến lược chunking mặc định bằng hierarchical_header_recursive

**Ngày:** 09/05/2026
**Phạm vi:** Phase 5 Training & Eval, Phase 6 Ingestion

## Kết quả chính

- Chuyển chiến lược chunking mặc định của eval/streaming/indexing sang `hierarchical_header_recursive`, chiến lược đứng đầu báo cáo đánh giá ngày 09/05/2026.
- Cập nhật `/home/quangnhvn34/dev/me/InsureVN/.env` để `RAG_CHUNKING_STRATEGY=hierarchical_header_recursive`.
- Bổ sung metadata lineage cho chunk: `chunking_strategy`, `header_hierarchy`, `header_path`, `header_level`, `section_heading`, `header_1..header_6` khi có, cùng các metadata Qdrant bắt buộc.
- Thêm bước báo cáo chất lượng metadata trước indexing để phát hiện trường thiếu, rỗng, invalid hoặc null.
- Safe eval wrapper mặc định chạy `hierarchical_header_recursive` nhưng vẫn nhận `--strategies` để đánh giá các strategy active khác khi cần.

## Metadata QA

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

## Trạng thái chạy BM25 + Vector + Graph

Pipeline full được chạy bằng `.env` của dự án và override strategy sang `hierarchical_header_recursive` tại thời điểm chạy. Sau đó `.env` đã được cập nhật để các lần chạy tiếp theo dùng trực tiếp `hierarchical_header_recursive`.

- Qdrant hybrid BM25 + vector đã tạo collection và index được 64 points trước khi dừng vì Gemini embedding quota: `429 RESOURCE_EXHAUSTED`, limit 100 requests/phút cho `gemini-embedding-2`.
- Graph extraction chưa hoàn tất vì `.env` không cấu hình `KG_EXTRACTION_LLM_PROVIDER`/`KG_EXTRACTION_LLM_MODEL`; default rơi về `ollama` + `gemma4:31b-cloud` và Ollama trả `ResponseError`/`401 unauthorized`.
- Neo4j và Qdrant local đều reachable, nhưng full run chưa thể hoàn tất nếu chưa đổi quota embedding hoặc cấu hình lại KG extraction model khả dụng.

Logs:

- `file:///tmp/insurevn_hierarchical_qdrant_v2.log`
- `file:///tmp/insurevn_hierarchical_index.log`

## Verification

- `python -m ruff format --check ...`: 11 files already formatted.
- `python -m ruff check ...`: All checks passed.
- `python -m pytest tests/unit/test_eval_strategy_embeddings.py tests/unit/test_document_chunker.py tests/unit/test_config.py tests/unit/test_health_markdown_rag_indexer.py tests/unit/test_streaming_qdrant_chunking.py tests/unit/test_safe_chunking_eval_wrapper.py tests/unit/test_benchmark_health_chunking.py -q`: 58 passed.
- Dry-run sau khi cập nhật `.env`, không truyền `--chunking-strategy`: 107 tài liệu, 9933 chunks, `required_metadata_valid=true`, `invalid_required_counts={}`.
