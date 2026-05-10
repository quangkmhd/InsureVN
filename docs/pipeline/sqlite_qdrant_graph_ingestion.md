# Ingest SQLite, Qdrant Và Knowledge Graph

## Mục tiêu

Nhóm script này biến output đã xử lý thành evidence foundation ba nguồn:
SQLite cho facts có cấu trúc, Qdrant cho text/chunk retrieval, và Neo4j/graph
JSON cho quan hệ entity. Đây là phase 6 trong
[`../work_log/2026-05-09-data-pipeline-processing-technical-report.md`](../work_log/2026-05-09-data-pipeline-processing-technical-report.md).

## Năng lực chính

### Nạp dữ liệu có cấu trúc vào SQLite

- [`../../scripts/06_db_ingestion/02_ingest_with_mapping.py`](../../scripts/06_db_ingestion/02_ingest_with_mapping.py)
  đọc `schema_mapping_results/schema_mapping.json`, nạp documents/source tables
  và các bảng domain vào SQLite theo `src/models/schema.sql`, đồng thời xuất
  review CSV.

Tài liệu database liên quan:
[`../database/sqlite_database_schema_specification.md`](../database/sqlite_database_schema_specification.md),
[`../database/mcp_insurevn_db_reference.md`](../database/mcp_insurevn_db_reference.md),
[`../database/database_agent.md`](../database/database_agent.md).

### Tạo mapping từ Markdown table sang SQLite source table

- [`../../scripts/06_db_ingestion/07_generate_table_mapping.py`](../../scripts/06_db_ingestion/07_generate_table_mapping.py)
  tạo `table_mapping.json` để nối Markdown table với `source_table_id` trong
  SQLite.
- [`../../scripts/06_db_ingestion/08_verify_mapping_logic.py`](../../scripts/06_db_ingestion/08_verify_mapping_logic.py)
  smoke-test logic mapping cho một tài liệu AIA.

Tài liệu kế hoạch đã có:
[`../superpowers/plans/2026-05-05-generate-table-mapping-utility.md`](../superpowers/plans/2026-05-05-generate-table-mapping-utility.md).

### Index Markdown vào Qdrant

- [`../../scripts/06_db_ingestion/04_index_qdrant_documents.py`](../../scripts/06_db_ingestion/04_index_qdrant_documents.py)
  index một hoặc nhiều Markdown document vào Qdrant, hỗ trợ metadata JSON,
  table mapping, chunk export, dry-run và recreate collection.
- [`../../scripts/06_db_ingestion/09_index_all_markdowns.py`](../../scripts/06_db_ingestion/09_index_all_markdowns.py)
  bulk index corpus Markdown sạch vào Qdrant, Neo4j và graph JSON, có option
  skip từng backend và chọn chunking strategy.

### Knowledge Graph schema và graph build

- [`../../scripts/07_knowledge_graph/01_discover_schema.py`](../../scripts/07_knowledge_graph/01_discover_schema.py)
  discover candidate entity/relationship schema từ Markdown/TXT.
- [`../../scripts/07_knowledge_graph/02_canonicalize_schema.py`](../../scripts/07_knowledge_graph/02_canonicalize_schema.py)
  canonicalize label/schema được discover.
- [`../../scripts/07_knowledge_graph/03_select_schema_v1.py`](../../scripts/07_knowledge_graph/03_select_schema_v1.py)
  chọn schema contract v1 và property CSV.
- [`../../scripts/07_knowledge_graph/04_build_knowledge_graph.py`](../../scripts/07_knowledge_graph/04_build_knowledge_graph.py)
  build graph theo schema contract.
- [`../../scripts/07_knowledge_graph/schema_discovery`](../../scripts/07_knowledge_graph/schema_discovery)
  chứa engine, provider clients, prompt/JSON parsing và aggregator cho schema
  discovery, gồm `__init__.py`, `discovery.py` và `discovery_clients.py`.
- [`../../scripts/07_knowledge_graph/Defining Entities-Relationships.svg`](../../scripts/07_knowledge_graph/Defining%20Entities-Relationships.svg)
  và
  [`../../scripts/07_knowledge_graph/Defining Entities-Relationships.png`](../../scripts/07_knowledge_graph/Defining%20Entities-Relationships.png)
  mô tả vòng đời entity/relationship.

Tài liệu KG đã có nên không tạo lại:
[`../architecture/2026-05-09-knowledge-graph-schema-discovery-pipeline.md`](../architecture/2026-05-09-knowledge-graph-schema-discovery-pipeline.md)
và
[`../work_log/2026-05-08-knowledge-graph-construction-technical-report.md`](../work_log/2026-05-08-knowledge-graph-construction-technical-report.md).

### Seed synthetic benchmark

- [`../../scripts/06_db_ingestion/seed_synthetic_benchmark.py`](../../scripts/06_db_ingestion/seed_synthetic_benchmark.py)
  seed `synthetic_users` và `synthetic_benchmark_cases` vào SQLite để test agent
  và retrieval flows bằng dữ liệu giả lập.

## Luồng chạy đề xuất

1. Nạp SQLite từ schema mapping:

```bash
python scripts/06_db_ingestion/02_ingest_with_mapping.py --dry-run
python scripts/06_db_ingestion/02_ingest_with_mapping.py
```

2. Sinh mapping Markdown table:

```bash
python scripts/06_db_ingestion/07_generate_table_mapping.py
python scripts/06_db_ingestion/08_verify_mapping_logic.py
```

3. Index một tài liệu vào Qdrant để smoke-test:

```bash
python scripts/06_db_ingestion/04_index_qdrant_documents.py \
  --document path/to/cleaned_document.md \
  --dry-run
```

4. Bulk index toàn corpus:

```bash
python scripts/06_db_ingestion/09_index_all_markdowns.py --dry-run
python scripts/06_db_ingestion/09_index_all_markdowns.py --recreate-qdrant
```

5. Nếu cần build KG schema riêng:

```bash
python scripts/07_knowledge_graph/01_discover_schema.py
python scripts/07_knowledge_graph/02_canonicalize_schema.py
python scripts/07_knowledge_graph/03_select_schema_v1.py
python scripts/07_knowledge_graph/04_build_knowledge_graph.py
```

6. Seed dữ liệu giả lập:

```bash
python scripts/06_db_ingestion/seed_synthetic_benchmark.py
```

## Output quan trọng

- SQLite domain tables và `source_tables`.
- `schema_mapping_results/db_review/*.csv`.
- `data/health_insurance/health_insurance_markdowns/table_mapping.json`.
- Qdrant collections/chunk export JSON.
- Neo4j graph data hoặc graph JSON.
- Synthetic users/cases trong SQLite.

## Lưu ý vận hành

- SQLite, Qdrant và Knowledge Graph là tri-canonical evidence foundation. Khi
  có conflict giữa ba nguồn, workflow agent phải flag để human review thay vì
  tự chọn một nguồn.
- Chạy dry-run trước khi recreate Qdrant hoặc clear/nạp lại SQLite.
- Giữ `source_table_id`, source path, company, document, page/section và graph
  path trong metadata để employee review truy vết được.
