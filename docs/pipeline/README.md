# Script Capability Runbooks

Tài liệu trong thư mục này gom các script theo năng lực vận hành của pipeline,
không viết một tài liệu riêng cho từng file. Phạm vi đọc là các source/script
trong `scripts/`; file cache sinh ra bởi Python không được xem là tài liệu vận
hành.

## Nhóm năng lực

1. [Thu thập và tiền xử lý PDF bảo hiểm](pdf_acquisition_and_preprocessing.md)
   - Crawl/download PDF từ website bảo hiểm, lọc tài liệu bảo hiểm sức khỏe,
     phân loại và sắp xếp raw corpus.
2. [Chuyển đổi tài liệu và làm sạch Markdown](document_conversion_and_markdown_cleanup.md)
   - Chuyển PDF sang Markdown bằng Marker/Datalab, diễn giải bảng biểu, làm
     sạch nhiễu ảnh/caption.
3. [Trích xuất ảnh/bảng và ánh xạ JSON](visual_extraction_and_json_mapping.md)
   - Trích cấu trúc tài liệu, crop bảng/ảnh, OCR/VLM sang JSON/Markdown, lọc
     good/trash và map schema về SQLite.
4. [Huấn luyện VLM và đánh giá RAG/retrieval](vlm_training_and_rag_evaluation.md)
   - Chuẩn bị dataset VLM, fine-tune/evaluate/export Gemma/Qwen, sinh benchmark
     RAG, chạy chunking và retrieval evaluation.
5. [Ingest SQLite, Qdrant và Knowledge Graph](sqlite_qdrant_graph_ingestion.md)
   - Nạp dữ liệu có cấu trúc vào SQLite, tạo mapping bảng, index Markdown vào
     Qdrant/Neo4j, seed synthetic benchmark.
6. [Công cụ vận hành, review và debug](operations_and_review_tools.md)
   - Tạo diagram, review UI cho output ảnh/Markdown, kiểm tra Langfuse trace,
     smoke test search tool.

## Tài liệu đã có không tạo lại

Các chủ đề dưới đây đã có tài liệu chuyên sâu ở nơi khác, nên runbook này chỉ
liên kết và mô tả vai trò của chúng:

- Knowledge Graph schema discovery:
  [`../architecture/2026-05-09-knowledge-graph-schema-discovery-pipeline.md`](../architecture/2026-05-09-knowledge-graph-schema-discovery-pipeline.md)
- Benchmark v2:
  [`../architecture/2026-05-09-benchmark-v2-generation-logic-technical-report.md`](../architecture/2026-05-09-benchmark-v2-generation-logic-technical-report.md)
- Chunking/retrieval evaluation reports:
  [`../work_log/2026-05-07-health-chunking-benchmark-end-to-end-process-technical-report.md`](../work_log/2026-05-07-health-chunking-benchmark-end-to-end-process-technical-report.md),
  [`../work_log/2026-05-09-context-benchmark-v2-all-chunking-eval-technical-report.md`](../work_log/2026-05-09-context-benchmark-v2-all-chunking-eval-technical-report.md)
- Marker conversion, table-to-text, JSON classification, table mapping:
  [`../superpowers/specs/2026-04-27-marker-batch-conversion-design.md`](../superpowers/specs/2026-04-27-marker-batch-conversion-design.md),
  [`../superpowers/specs/2026-05-02-table-to-text-conversion-design.md`](../superpowers/specs/2026-05-02-table-to-text-conversion-design.md),
  [`../superpowers/specs/2026-05-01-json-classification-pipeline-design.md`](../superpowers/specs/2026-05-01-json-classification-pipeline-design.md),
  [`../superpowers/plans/2026-05-05-generate-table-mapping-utility.md`](../superpowers/plans/2026-05-05-generate-table-mapping-utility.md)

