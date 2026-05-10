# Nhật ký Mã nguồn `src/` - InsureVN

> Cấu trúc báo cáo kỹ thuật được áp dụng ngày 2026-05-09. Nội dung gốc lịch sử được giữ ở Mục 10 để truy vết.

## 1. Tóm tắt điều hành

Báo cáo kỹ thuật này ghi lại tài liệu nhật ký công việc `2026-05-09-src-code-inventory-technical-report.md` của InsureVN. Tài liệu được chuẩn hóa theo định dạng báo cáo kỹ thuật của dự án, đồng thời giữ nguyên nội dung và bằng chứng gốc bên dưới.

## 2. Mục tiêu và phạm vi

Mục tiêu là ghi lại công việc, quy trình, quyết định, benchmark hoặc inventory được mô tả trong file gốc. Phạm vi chuẩn hóa chỉ giới hạn ở tài liệu: không chạy lại benchmark, không thay đổi code triển khai và không thay đổi ý nghĩa của report gốc.

## 3. Bối cảnh

Phân loại: Kiến trúc hệ thống lõi và inventory mã nguồn trên infrastructure, services và intelligent agents.

Báo cáo này thuộc `docs/work_log/`, khu vực dùng cho báo cáo kỹ thuật, báo cáo benchmark, nhật ký quy trình và lịch sử triển khai của InsureVN.

## 4. Triển khai

Chi tiết triển khai, quy trình hoặc phân tích gốc được giữ trong Mục 10. Trong lần chuẩn hóa này, tài liệu được bọc bằng cấu trúc báo cáo kỹ thuật chung để các nhật ký công việc sau này có cùng bố cục về bối cảnh, bằng chứng, xác minh, kết quả, rủi ro và việc tiếp theo.

## 5. Bằng chứng và lệnh đã chạy

Bằng chứng dùng cho lần chuẩn hóa này:

- Tài liệu nguồn hiện có: `docs/work_log/2026-05-09-src-code-inventory-technical-report.md`
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

- Cập nhật báo cáo này khi thêm module, agent, service hoặc MCP tool mới trong `src/`.
- Link tới tài liệu kiến trúc hoặc ADR nếu có quyết định làm thay đổi ranh giới hệ thống.

## 10. Nội dung gốc được giữ lại

**Thời gian cập nhật:** 06/05/2026
**Phạm vi:** Toàn bộ mã nguồn runtime trong `src/`, bao gồm API, cấu hình, MCP, RAG, Evidence, Knowledge Graph và Agent layer.
**Liên kết pipeline:** [`2026-05-09-data-pipeline-processing-technical-report.md`](file:///home/quangnhvn34/dev/me/InsureVN/docs/work_log/2026-05-09-data-pipeline-processing-technical-report.md)

---

### 1. Tổng quan Kiến trúc `src/`

Sau khi dữ liệu được xử lý qua 6 giai đoạn pipeline, các thành phần trong `src/` vận hành theo 3 tầng kiến trúc:

#### Tier 1: Infrastructure & Tools
- **FastAPI Bootstrap:** `src/main.py` khởi tạo ứng dụng, lifecycle logging, middleware trace HTTP request và route health check.
- **Configuration Layer:** `src/core/config.py` gom toàn bộ cấu hình SQLite, Langfuse, DatabaseAgent, Search, RAG/Qdrant, Neo4j và Knowledge Graph theo biến môi trường đã ép kiểu rõ ràng.
- **Database Access:** `src/core/database.py` quản lý kết nối SQLite thường/read-only; `src/models/schema.sql` định nghĩa schema 3 tầng: Source Lineage, Plan Normalization, Domain Tables, cộng Synthetic Foundation.
- **MCP SQLite Server:** `src/mcp_servers/sqlite/server.py` xuất bản các tool truy vấn domain như công ty, tài liệu, gói, phí, quyền lợi, bệnh viện, thời gian chờ, bồi thường, thuật ngữ và loại trừ.
- **Search Tool:** `src/tools/search_tool.py` tích hợp Tavily Search cho thông tin web cần dữ liệu sống; `src/tools/mcp_client.py` bind MCP SQLite tools vào LangChain.
- **Logging & Observability Base:** `src/core/logger.py` tạo JSON logs, file rotation và mirror log record vào Langfuse span.

#### Tier 2: Core Services
- **Chunking logic:** `src/services/document_chunker.py` xử lý Markdown thành parent sections và child chunks có payload Qdrant đầy đủ citation metadata.
- **Hybrid Retrieval:** `src/services/qdrant_retriever.py`, `qdrant_collection_manager.py`, `qdrant_vector_store.py` triển khai retrieval dense + BM25/hybrid trên Qdrant, hard filters và readiness gate cho production.
- **Evidence Management:** `src/services/sqlite_evidence.py`, `qdrant_evidence.py`, `knowledge_graph/graph_evidence.py` chuẩn hóa dữ liệu từ SQL/Vector/Graph về `Evidence`; `evidence_merger.py` deduplicate, phát hiện conflict và rerank bằng cross-encoder.
- **Reranking:** `src/services/jina_rerank_cross_encoder.py` đóng gói Jina rerank API thành LangChain `BaseCrossEncoder`.
- **Citation:** `src/services/citation_formatter.py` chuẩn hóa citation tối thiểu từ evidence metadata để truy ngược nguồn.
- **Service Observability:** `src/services/observability.py` cung cấp decorator `service_observe` để trace input/output summary, duration, error metadata và metadata bổ sung trong Langfuse.
- **Knowledge Graph Services:** `src/services/knowledge_graph/` bao phủ schema discovery, schema runtime v1, LLM graph extraction, NetworkX diagnostics, Neo4j import/query, GraphRAG traversal, quality validation và JSON serialization.

#### Tier 3: Intelligent Agents
- **DatabaseAgent:** `src/agents/database_agent.py` tạo LangChain agent có model cấu hình riêng, load prompt production từ Langfuse, fallback prompt nội bộ, bind SQLite MCP tools và trace execution qua Langfuse callback.
- **Orchestrator:** Planned. Điều phối luồng làm việc giữa các Agent chuyên biệt.

---

### 2. Danh mục Code Chi tiết

**Quy mô hiện tại:** `src/` có 8.736 dòng Python/SQL chính, gồm API runtime, cấu hình, MCP server, evidence models, RAG services, Knowledge Graph services và DatabaseAgent.

#### 2.1. Entry Point & API Runtime
| File | Vai trò | Kiến trúc |
| :--- | :--- | :--- |
| [`src/main.py`](file:///home/quangnhvn34/dev/me/InsureVN/src/main.py) | FastAPI application factory, lifecycle logging, Langfuse HTTP trace middleware và đăng ký router. | Tier 1 - API Runtime |
| [`src/api/routes/health.py`](file:///home/quangnhvn34/dev/me/InsureVN/src/api/routes/health.py) | Endpoint `/health` trả trạng thái, tên project, version và Python runtime. | Tier 1 - API Runtime |
| [`src/api/__init__.py`](file:///home/quangnhvn34/dev/me/InsureVN/src/api/__init__.py) | Package marker cho API modules. | Tier 1 - API Runtime |

#### 2.2. Core Configuration, Logging & Utilities
| File | Vai trò | Kiến trúc |
| :--- | :--- | :--- |
| [`src/core/config.py`](file:///home/quangnhvn34/dev/me/InsureVN/src/core/config.py) | Typed settings registry cho SQLite, Langfuse, LLM, DatabaseAgent, Search, Qdrant/RAG, rerank, Neo4j và schema discovery providers. | Tier 1 - Configuration |
| [`src/core/database.py`](file:///home/quangnhvn34/dev/me/InsureVN/src/core/database.py) | SQLite connection helper, read-only URI mode và SQL file execution. | Tier 1 - Database |
| [`src/core/logger.py`](file:///home/quangnhvn34/dev/me/InsureVN/src/core/logger.py) | JSON formatter, rotating file handler và Langfuse log handler. | Tier 1 - Observability |
| [`src/core/vietnamese_text.py`](file:///home/quangnhvn34/dev/me/InsureVN/src/core/vietnamese_text.py) | Vietnamese transliteration và deterministic slug generation cho ID/schema. | Tier 2 - Shared Utility |
| [`src/core/__init__.py`](file:///home/quangnhvn34/dev/me/InsureVN/src/core/__init__.py) | Package marker cho core modules. | Tier 1 - Configuration |
| [`src/__init__.py`](file:///home/quangnhvn34/dev/me/InsureVN/src/__init__.py) | Package marker cho root source package. | Project Structure |

#### 2.3. Data Models & SQLite Schema
| File | Vai trò | Phase/Tier |
| :--- | :--- | :--- |
| [`src/models/evidence.py`](file:///home/quangnhvn34/dev/me/InsureVN/src/models/evidence.py) | Pydantic contract chung cho `Evidence`, `Citation`, retrieval plan, hard filters, benchmark case và enum workflow/risk/source. | Tier 2 - Evidence Contract |
| [`src/models/schema.sql`](file:///home/quangnhvn34/dev/me/InsureVN/src/models/schema.sql) | SQLite schema chính: companies, documents, source_tables, plan_types, benefits, premiums, hospitals, glossary, waiting periods, claim payouts, short-term premiums và synthetic benchmark foundation. | Phase 6 - Ingestion |
| [`src/models/__init__.py`](file:///home/quangnhvn34/dev/me/InsureVN/src/models/__init__.py) | Package marker cho model/schema modules. | Project Structure |

#### 2.4. Tools & MCP Infrastructure
| File | Vai trò | Phase/Tier |
| :--- | :--- | :--- |
| [`src/tools/mcp_client.py`](file:///home/quangnhvn34/dev/me/InsureVN/src/tools/mcp_client.py) | Khởi chạy SQLite MCP server qua stdio và trả LangChain tools cho agents. | Tier 1 - MCP Tools |
| [`src/tools/search_tool.py`](file:///home/quangnhvn34/dev/me/InsureVN/src/tools/search_tool.py) | Tavily web search tool có Langfuse observation và Search-specific config. | Tier 1 - Search Tool |
| [`src/tools/__init__.py`](file:///home/quangnhvn34/dev/me/InsureVN/src/tools/__init__.py) | Package marker cho tools. | Project Structure |
| [`src/mcp_servers/sqlite/server.py`](file:///home/quangnhvn34/dev/me/InsureVN/src/mcp_servers/sqlite/server.py) | FastMCP server `insurevn-db`; enforce SELECT-only SQL; log/trace tool calls; expose 21 SQLite domain tools. | Tier 1 - MCP Server |
| [`src/mcp_servers/sqlite/__init__.py`](file:///home/quangnhvn34/dev/me/InsureVN/src/mcp_servers/sqlite/__init__.py) | Package marker cho SQLite MCP server. | Project Structure |
| [`src/mcp_servers/__init__.py`](file:///home/quangnhvn34/dev/me/InsureVN/src/mcp_servers/__init__.py) | Package marker cho MCP servers. | Project Structure |

**SQLite MCP tool coverage:** `list_tables`, `get_schema`, `execute_query`, `database_summary`, `list_companies`, `list_documents`, `list_source_tables`, `list_benefit_categories`, `search_plans`, `list_plans`, `get_premium_quotes`, `search_benefits`, `search_hospitals`, `search_waiting_periods`, `search_claim_payouts`, `search_glossary_terms`, `get_benefit_matrix`, `get_short_term_premiums`, `get_raw_source`, `compare_benefits`, `search_exclusions`.

#### 2.5. RAG, Evidence & Observability Services
| File | Vai trò | Phase/Tier |
| :--- | :--- | :--- |
| [`src/services/document_chunker.py`](file:///home/quangnhvn34/dev/me/InsureVN/src/services/document_chunker.py) | Parse Markdown, giữ parent sections, sinh child chunks, detect interpreted tables/table-heavy sections và validate Qdrant payload citation fields. | Phase 3/6 - Conversion to Vector Ingestion |
| [`src/services/qdrant_collection_manager.py`](file:///home/quangnhvn34/dev/me/InsureVN/src/services/qdrant_collection_manager.py) | Tạo Qdrant collection hybrid dense+sparse, payload indexes và readiness report. | Phase 6 - Vector DB |
| [`src/services/qdrant_vector_store.py`](file:///home/quangnhvn34/dev/me/InsureVN/src/services/qdrant_vector_store.py) | Factory cho LangChain `QdrantVectorStore` với named dense/sparse vectors. | Phase 6 - Vector DB |
| [`src/services/qdrant_retriever.py`](file:///home/quangnhvn34/dev/me/InsureVN/src/services/qdrant_retriever.py) | Google GenAI embeddings, FastEmbed sparse retrieval, chunk indexing, hybrid search, hard filters, deletion và production readiness guard. | Tier 2 - Hybrid Retrieval |
| [`src/services/qdrant_evidence.py`](file:///home/quangnhvn34/dev/me/InsureVN/src/services/qdrant_evidence.py) | Map Qdrant payload/score thành shared `Evidence(source_type=qdrant_chunk)`. | Tier 2 - Evidence Adapter |
| [`src/services/sqlite_evidence.py`](file:///home/quangnhvn34/dev/me/InsureVN/src/services/sqlite_evidence.py) | Map MCP SQL rows và synthetic/user profile rows thành shared `Evidence`. | Tier 2 - Evidence Adapter |
| [`src/services/evidence_merger.py`](file:///home/quangnhvn34/dev/me/InsureVN/src/services/evidence_merger.py) | Deduplicate evidence, phát hiện conflict theo `source_id`, top-k slicing và optional cross-encoder rerank. | Tier 2 - Evidence Fusion |
| [`src/services/jina_rerank_cross_encoder.py`](file:///home/quangnhvn34/dev/me/InsureVN/src/services/jina_rerank_cross_encoder.py) | Adapter Jina rerank API thành LangChain cross-encoder, parse scores và attach usage metadata. | Tier 2 - Reranking |
| [`src/services/citation_formatter.py`](file:///home/quangnhvn34/dev/me/InsureVN/src/services/citation_formatter.py) | Validate citation metadata và trả `Citation` có company/document/source/page lineage. | Tier 2 - Citation |
| [`src/services/retrieval_readiness.py`](file:///home/quangnhvn34/dev/me/InsureVN/src/services/retrieval_readiness.py) | Production readiness report cho dense vector, sparse vector, payload indexes và degraded dense-only mode. | Tier 2 - Quality Gate |
| [`src/services/observability.py`](file:///home/quangnhvn34/dev/me/InsureVN/src/services/observability.py) | Shared Langfuse decorator cho service operations, sanitized input/output summaries, duration/error metadata và context metadata. | Tier 2 - Observability |
| [`src/services/__init__.py`](file:///home/quangnhvn34/dev/me/InsureVN/src/services/__init__.py) | Package marker cho services. | Project Structure |

#### 2.6. Knowledge Graph Runtime & GraphRAG
| File | Vai trò | Phase/Tier |
| :--- | :--- | :--- |
| [`src/services/knowledge_graph/schema.py`](file:///home/quangnhvn34/dev/me/InsureVN/src/services/knowledge_graph/schema.py) | Runtime schema constants, Neo4j uniqueness constraints và stable graph IDs cho company/document/plan/chunk. | Phase 6 - Graph DB |
| [`src/services/knowledge_graph/builder.py`](file:///home/quangnhvn34/dev/me/InsureVN/src/services/knowledge_graph/builder.py) | Build NetworkX diagnostic graph từ LangChain GraphDocument, filter allowed nodes/relationships và log entity/relationship counts. | Phase 4/6 - Graph Build |
| [`src/services/knowledge_graph/document_extractor.py`](file:///home/quangnhvn34/dev/me/InsureVN/src/services/knowledge_graph/document_extractor.py) | LangChain LLMGraphTransformer extraction từ Markdown chunks, schema-constrained prompt, retry/fallback và lineage enrichment. | Phase 4 - Knowledge Extraction |
| [`src/services/knowledge_graph/graph_document_adapter.py`](file:///home/quangnhvn34/dev/me/InsureVN/src/services/knowledge_graph/graph_document_adapter.py) | Adapter mỏng từ source document + chunk payloads sang LangChain graph documents. | Phase 4 - Knowledge Extraction |
| [`src/services/knowledge_graph/document_graph_retriever.py`](file:///home/quangnhvn34/dev/me/InsureVN/src/services/knowledge_graph/document_graph_retriever.py) | Factory cho LangChain `GraphRetriever` với Eager traversal trên vector store metadata edges. | Tier 2 - GraphRAG |
| [`src/services/knowledge_graph/retriever.py`](file:///home/quangnhvn34/dev/me/InsureVN/src/services/knowledge_graph/retriever.py) | N-hop NetworkX path retriever và explainable path representation. | Tier 2 - Graph Retrieval |
| [`src/services/knowledge_graph/neo4j_graph_retriever.py`](file:///home/quangnhvn34/dev/me/InsureVN/src/services/knowledge_graph/neo4j_graph_retriever.py) | Read-only Neo4j path query theo start entities, relationship types và max hops. | Tier 2 - Graph Retrieval |
| [`src/services/knowledge_graph/neo4j_cypher_qa.py`](file:///home/quangnhvn34/dev/me/InsureVN/src/services/knowledge_graph/neo4j_cypher_qa.py) | LangChain GraphCypherQAChain wrapper với prompt chỉ sinh read-only Cypher và QA dựa trên graph context. | Tier 2 - Graph QA |
| [`src/services/knowledge_graph/neo4j_store.py`](file:///home/quangnhvn34/dev/me/InsureVN/src/services/knowledge_graph/neo4j_store.py) | Neo4jGraph wrapper tạo uniqueness constraints và import LangChain GraphDocument có source linkage. | Phase 6 - Graph DB |
| [`src/services/knowledge_graph/quality.py`](file:///home/quangnhvn34/dev/me/InsureVN/src/services/knowledge_graph/quality.py) | Validate graph quality: orphan nodes, missing lineage, dangling chunks, low confidence edges và invalid relationships. | Phase 2/6 - QA Gate |
| [`src/services/knowledge_graph/graph_evidence.py`](file:///home/quangnhvn34/dev/me/InsureVN/src/services/knowledge_graph/graph_evidence.py) | Convert graph paths thành `Evidence(source_type=graph_triple)` với edge lineage và confidence từ relationship path. | Tier 2 - Evidence Adapter |
| [`src/services/knowledge_graph/evidence_adapter.py`](file:///home/quangnhvn34/dev/me/InsureVN/src/services/knowledge_graph/evidence_adapter.py) | Compatibility export `GraphEvidenceAdapter = GraphEvidenceMapper`. | Tier 2 - Compatibility |
| [`src/services/knowledge_graph/serializer.py`](file:///home/quangnhvn34/dev/me/InsureVN/src/services/knowledge_graph/serializer.py) | Persist/load NetworkX graph JSON bằng node-link format. | Phase 6 - Graph Storage |
| [`src/services/knowledge_graph/__init__.py`](file:///home/quangnhvn34/dev/me/InsureVN/src/services/knowledge_graph/__init__.py) | Public exports cho Knowledge Graph services. | Project Structure |

#### 2.7. Knowledge Graph Schema Discovery & Runtime Schema Assets
| File | Vai trò | Phase/Tier |
| :--- | :--- | :--- |
| [`src/services/knowledge_graph/schema_discovery.py`](file:///home/quangnhvn34/dev/me/InsureVN/src/services/knowledge_graph/schema_discovery.py) | AI-assisted schema discovery: chunk Markdown, checkpoint JSONL, concurrent runner, aggregate proposals, canonicalize labels, filter stable concepts và build final schema v1 contracts/CSVs. | Phase 4 - Schema Extraction |
| [`src/services/knowledge_graph/schema_discovery_clients.py`](file:///home/quangnhvn34/dev/me/InsureVN/src/services/knowledge_graph/schema_discovery_clients.py) | HTTP clients cho Ollama, OpenRouter, NVIDIA và Gemini; Pydantic validation, JSON extraction và canonicalization prompts. | Phase 4 - Schema Extraction |
| [`src/services/knowledge_graph/graph_schema/health_insurance_v1.py`](file:///home/quangnhvn34/dev/me/InsureVN/src/services/knowledge_graph/graph_schema/health_insurance_v1.py) | Runtime schema loader/cache cho health insurance KG v1 từ CSV assets. | Phase 6 - Graph Schema |
| [`src/services/knowledge_graph/graph_schema/__init__.py`](file:///home/quangnhvn34/dev/me/InsureVN/src/services/knowledge_graph/graph_schema/__init__.py) | Public exports cho graph schema contract. | Project Structure |
| [`src/services/knowledge_graph/graph_schema/allowed_nodes.csv`](file:///home/quangnhvn34/dev/me/InsureVN/src/services/knowledge_graph/graph_schema/allowed_nodes.csv) | Danh sách node labels được phép cho extraction/runtime schema. | Phase 6 - Graph Schema Asset |
| [`src/services/knowledge_graph/graph_schema/allowed_relationships.csv`](file:///home/quangnhvn34/dev/me/InsureVN/src/services/knowledge_graph/graph_schema/allowed_relationships.csv) | Danh sách relationship types được phép cho extraction/runtime schema. | Phase 6 - Graph Schema Asset |
| [`src/services/knowledge_graph/graph_schema/node_properties.csv`](file:///home/quangnhvn34/dev/me/InsureVN/src/services/knowledge_graph/graph_schema/node_properties.csv) | Danh sách property names hợp lệ cho node schema. | Phase 6 - Graph Schema Asset |
| [`src/services/knowledge_graph/graph_schema/relationship_properties.csv`](file:///home/quangnhvn34/dev/me/InsureVN/src/services/knowledge_graph/graph_schema/relationship_properties.csv) | Danh sách property names hợp lệ cho relationship schema. | Phase 6 - Graph Schema Asset |

#### 2.8. Intelligent Agent Layer
| File | Vai trò | Phase/Tier |
| :--- | :--- | :--- |
| [`src/agents/database_agent.py`](file:///home/quangnhvn34/dev/me/InsureVN/src/agents/database_agent.py) | DatabaseAgent dùng LangChain `create_agent`, dedicated database LLM config, Langfuse prompt management/callbacks và SQLite MCP tools để trả lời câu hỏi có cấu trúc. | Tier 3 - Intelligent Agent |
| [`src/agents/__init__.py`](file:///home/quangnhvn34/dev/me/InsureVN/src/agents/__init__.py) | Package marker cho agents. | Project Structure |

---

### 3. Thành tựu trong `src/`

#### Hybrid Evidence Foundation
- Toàn bộ SQL, Vector và Graph retrieval đã dùng chung contract `Evidence`, giúp các agent sau này có thể merge/rerank/cite nguồn đồng nhất.
- Qdrant retrieval có cơ chế production gate để tránh vô tình dùng dense-only degraded mode trong môi trường cần hybrid retrieval.
- SQLite MCP server giới hạn `execute_query` ở SELECT/WITH/EXPLAIN QUERY PLAN, giảm rủi ro ghi/xóa dữ liệu khi agent truy vấn.

#### Knowledge Graph v1 Runtime
- Schema discovery đã hỗ trợ nhiều provider AI, checkpoint resumable, canonicalization theo batch và xuất final schema v1.
- Runtime graph schema dùng CSV assets để ràng buộc LangChain LLMGraphTransformer, giúp extraction không trôi khỏi domain bảo hiểm sức khỏe Việt Nam.
- Neo4j import, read-only path retrieval và Cypher QA đã tách thành các service riêng, thuận lợi cho GraphRAG và kiểm thử độc lập.

---

### 4. Kết luận

Mã nguồn trong `src/` hiện đã có nền tảng runtime cho API, Agent, MCP, Hybrid RAG, Evidence Fusion, Observability và Knowledge Graph. File này là nhật ký riêng cho kiến trúc/mã nguồn, tách khỏi nhật ký xử lý dữ liệu pipeline.
