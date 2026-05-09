# InsureVN - AI Engineering Portfolio Project

> README này được viết cho nhà tuyển dụng và reviewer kỹ thuật. Mục tiêu không phải là hướng dẫn cộng đồng sử dụng thư viện, mà là thể hiện phạm vi công việc, năng lực kỹ thuật và các quyết định engineering tôi đã trực tiếp xây dựng trong dự án.

## Tóm tắt cho nhà tuyển dụng

InsureVN là dự án AI Engineering cho ngành bảo hiểm sức khỏe Việt Nam. Tôi xây hệ thống từ tầng dữ liệu đến agent: thu thập PDF bảo hiểm, chuyển đổi tài liệu không cấu trúc thành dữ liệu có lineage, xây SQLite database, indexing vào Qdrant/Knowledge Graph, thiết kế MCP tools, và phát triển agent có observability.

Điểm chính nhà tuyển dụng có thể đánh giá:

- Năng lực thiết kế hệ thống AI nhiều tầng: data pipeline, retrieval, graph, database, agent orchestration.
- Kinh nghiệm xử lý dữ liệu thực tế: PDF tiếng Việt, bảng biểu bảo hiểm, schema không đồng nhất, OCR noise, mapping JSON sang SQL.
- Kinh nghiệm agentic AI production patterns: MCP server, LangChain/LangGraph, RAG evidence, citation, hard filters, Langfuse tracing.
- Tư duy engineering: source lineage, read-only database tools, cấu hình tập trung, unit/integration/e2e tests, logging và observability.

## Điểm nổi bật cho nhà tuyển dụng

**Vai trò:** AI Engineer / Backend Developer

**Tech stack:** Python, FastAPI, LangChain, LangGraph, Deep Agents, MCP/FastMCP, SQLite, Qdrant, Neo4j, NetworkX, Langfuse, Ollama, Gemini, NVIDIA, OpenRouter, Marker, Datalab, CUDA, pytest, ruff.

- Thiết kế và xây dựng nền tảng AI multi-agent cho bảo hiểm sức khỏe Việt Nam, hỗ trợ policy Q&A, product comparison, claim advisory và claim/payout draft workflows bằng FastAPI, LangChain, LangGraph, Deep Agents và shared evidence foundation.
- Xây dựng pipeline tài liệu end-to-end để thu thập, phân loại, chuyển đổi, trích xuất, đánh giá và ingest PDF bảo hiểm tiếng Việt vào SQLite, Qdrant và Knowledge Graph.
- Tự động hóa thu thập dữ liệu từ 9+ nguồn bảo hiểm như AIA, Bảo Việt, Bảo Minh, BIC, Liberty, PTI, PVI, Generali và Pacific Cross bằng crawler, Firecrawl và deep search workflows.
- Phát triển pipeline xử lý tài liệu bằng LLM/VLM với Marker, Datalab, CUDA và multi-provider LLMs để phân loại PDF bảo hiểm sức khỏe, loại bỏ tài liệu không liên quan, chuyển PDF sang Markdown, trích xuất bảng/ảnh/structured JSON, chuyển bảng phức tạp thành narrative text và ánh xạ output không đồng nhất vào SQLite.
- Thiết kế SQLite database schema có khả năng truy vết nguồn dữ liệu, chuẩn hóa gói bảo hiểm và lưu domain tables; chuẩn hóa dữ liệu từ 6 công ty, 83 PDFs, 644 source tables, 424 plans, 3,766 benefit values, 1,771 premium rows, 7,004 hospitals, 290 glossary terms và 551 claim payout records.
- Xây dựng read-only SQLite MCP server với 21 insurance domain tools và tích hợp với LangChain DatabaseAgent, dedicated LLM configuration, Langfuse tracing và prompt management để truy vấn an toàn các dữ liệu về benefits, premiums, hospitals, waiting periods, claim payouts và exclusions dựa trên evidence.
- Thiết kế Quad-Retrieval RAG architecture kết hợp SQLite structured facts, Qdrant dense vector search, sparse/BM25 keyword search và Knowledge Graph reasoning, kèm shared Evidence layer cho normalization, deduplication, conflict detection, reranking và citation formatting.
- Triển khai retrieval foundation với parent-child chunking, table-aware chunking, bảo toàn legal context, Qdrant dense/sparse indexing, hard filters theo company/plan/document/section và production readiness checks.
- Xây dựng Knowledge Graph và GraphRAG services cho schema discovery, LLM graph extraction, NetworkX diagnostics, Neo4j import/query, graph traversal và graph quality validation, giúp giảm rủi ro trộn dữ liệu giữa các công ty có ngôn ngữ hợp đồng bảo hiểm tương tự nhau.
- Xây dựng AI-assisted graph schema discovery pipeline để quét tài liệu bảo hiểm, đề xuất candidate nodes, relationships và properties, sau đó lọc, gộp và canonicalize thành domain-specific Knowledge Graph schema với 42 node types, 68 relationship types, 127 node properties và 27 relationship properties.
- Xây dựng retrieval evaluation workflows để chọn chiến lược chunking phù hợp nhất cho tài liệu bảo hiểm tiếng Việt, so sánh 9 strategies trên 150 QA cases và 1,350 metric rows; best full benchmark đạt 40.67% Primary Hit@5, 26.71% MRR@5 và 26.61% Required Source Recall@5.
- Chạy persisted Qdrant evaluation trên 91 cases, với strategy tốt nhất đạt 74.73% Primary Hit@5 và 55.44% MRR@5; đồng thời xây context-level RAG benchmarks, streaming chunking/embedding ingestion trên 86 expected-source files và LLM chunking comparison với 172/172 file-strategy rows hoàn tất, 0 failures.
- Xây dựng AI judge evaluation pipeline cho 1,350 strategy-case pairs, hoàn tất 1,350/1,350 evaluations với 0 failures sau retry timeout/rate-limit.
- Triển khai FastAPI runtime, health checks, lifecycle logging, structured JSON logs, typed configuration cho LLM providers/Qdrant/Neo4j/Langfuse, và Langfuse observability cho agent execution, MCP tool calls, HTTP tracing, service duration, error metadata và prompt versioning.
- Duy trì codebase gồm 76 source files, 71 Python scripts, 64 documentation files và 48 test files, có unit, integration và e2e test structure.

## Vai trò của tôi trong dự án

Tôi đóng vai trò owner/AI engineer chính của dự án:

- Thiết kế kiến trúc tổng thể cho một hệ thống multi-agent insurance assistant.
- Xây pipeline 6 giai đoạn để biến PDF bảo hiểm thành tri thức có thể truy vấn.
- Thiết kế SQLite schema theo hướng audit được, có source lineage từ database về JSON/PDF gốc.
- Xây SQLite MCP server để agent truy vấn dữ liệu bằng tool an toàn thay vì gọi database trực tiếp.
- Xây DatabaseAgent và các service nền cho retrieval, evidence merging, citation và observability.
- Thiết kế kiến trúc Quad-Retrieval RAG kết hợp SQLite, Qdrant, BM25/sparse search và Knowledge Graph.
- Chuẩn bị pipeline fine-tuning/evaluation cho VLM xử lý bảng biểu bảo hiểm tiếng Việt.

## Bài toán kỹ thuật

Tài liệu bảo hiểm sức khỏe ở Việt Nam có nhiều đặc điểm khó cho AI:

- Dữ liệu nằm trong PDF, bảng biểu, ảnh scan, brochure và điều khoản pháp lý dài.
- Cùng một khái niệm bảo hiểm nhưng mỗi công ty đặt tên gói, quyền lợi và cột bảng khác nhau.
- Câu trả lời phải chính xác về số tiền, thời gian chờ, điều khoản loại trừ và nguồn trích dẫn.
- RAG thuần vector dễ lẫn dữ liệu giữa các công ty vì ngôn ngữ hợp đồng bảo hiểm rất giống nhau.

Cách tôi giải quyết là tách rõ dữ liệu có cấu trúc và không cấu trúc:

- SQLite giữ facts chính xác: quyền lợi, phí, bệnh viện, thời gian chờ, tỷ lệ chi trả.
- Qdrant giữ văn bản/chunk phục vụ semantic search và keyword search.
- Knowledge Graph giữ quan hệ giữa công ty, sản phẩm, gói, quyền lợi, điều khoản.
- Evidence layer hợp nhất kết quả, khử trùng lặp, phát hiện xung đột và format citation.

## Kết quả định lượng hiện có

| Hạng mục                            | Kết quả |
| ------------------------------------- | --------: |
| Công ty bảo hiểm đã chuẩn hóa  |         6 |
| PDF gốc trong SQLite lineage         |        83 |
| JSON/source tables đã trích xuất  |       644 |
| Gói bảo hiểm đã normalize        |       424 |
| Hạng mục quyền lợi                |     1,236 |
| Giá trị quyền lợi theo từng plan |     3,766 |
| Dòng phí bảo hiểm                 |     1,771 |
| Bệnh viện/phòng khám              |     7,004 |
| Thuật ngữ bảo hiểm                |       290 |
| Tỷ lệ chi trả claim                |       551 |
| Test files hiện có                    |        48 |

Nguồn số liệu database: [docs/database/sqlite_database_schema_specification.md](docs/database/sqlite_database_schema_specification.md). Số lượng test files lấy từ inventory hiện tại của repository.

## Kiến trúc hệ thống

![InsureVN architecture](asset/insurevn-Architecture.png)

### Data pipeline 6 giai đoạn

1. Acquisition: crawler và Firecrawl scripts thu thập PDF từ các công ty bảo hiểm.
2. Preprocessing & QA: phân loại PDF, lọc tài liệu không liên quan, tổ chức thư mục dữ liệu.
3. Conversion & Interpretation: chuyển PDF sang Markdown, xử lý bảng biểu bằng Marker/Datalab và table-to-narrative.
4. Extraction: dùng Vision LLM/OCR để trích xuất Markdown + JSON, lọc Good/Trash, phân loại schema.
5. Training & Eval: chuẩn bị dataset và scripts fine-tune/evaluate Gemma 4 Vision cho bảng biểu bảo hiểm.
6. Ingestion: map JSON không đồng nhất vào SQLite, index Markdown vào Qdrant và Knowledge Graph.

Tài liệu liên quan: [docs/work_log/data_pipeline_processing_log.md](docs/work_log/data_pipeline_processing_log.md).

### Retrieval và evidence system

Tôi thiết kế retrieval theo hướng evidence-first thay vì chỉ gọi LLM trả lời:

- Dense vector search trên Qdrant cho câu hỏi ngữ nghĩa.
- Sparse/BM25-style search cho mã sản phẩm, tên bệnh, thuật ngữ và con số cụ thể.
- SQLite structured facts cho phí, hạn mức, bệnh viện, waiting periods và claim payouts.
- Knowledge Graph cho quan hệ nhiều bước giữa công ty, gói, quyền lợi và điều khoản.
- EvidenceMerger hợp nhất bằng chứng, rerank, phát hiện xung đột và chuẩn hóa citation.

Tài liệu liên quan: [docs/architecture/2026-05-04-quad-retrieval-rag-architecture.md](docs/architecture/2026-05-04-quad-retrieval-rag-architecture.md) và [docs/work_log/ensemble_retriever_log.md](docs/work_log/ensemble_retriever_log.md).

### Agent và MCP

Phần agent hiện tập trung vào structured data specialist:

- `DatabaseAgent` nhận câu hỏi tự nhiên và gọi SQLite MCP tools qua LangChain.
- SQLite MCP server expose domain tools như `search_benefits`, `compare_benefits`, `get_premium_quotes`, `search_hospitals`, `search_waiting_periods`, `search_claim_payouts`.
- MCP server enforce read-only queries và SQL parameterization để giảm rủi ro tool misuse.
- Langfuse được tích hợp để trace agent execution, tool calls, prompt versioning và metadata theo session.

Tài liệu liên quan:

- [docs/database/database_agent.md](docs/database/database_agent.md)
- [docs/database/mcp_insurevn_db_reference.md](docs/database/mcp_insurevn_db_reference.md)
- [docs/observability/langfuse_integration.md](docs/observability/langfuse_integration.md)

## Công nghệ sử dụng

| Nhóm              | Công nghệ                                  |
| ------------------ | -------------------------------------------- |
| Language           | Python 3.12                                  |
| API                | FastAPI                                      |
| Agent framework    | LangChain, LangGraph, Deep Agents            |
| LLM/VLM            | Gemini, Gemma 4, Ollama-compatible providers |
| Vector retrieval   | Qdrant, dense/sparse retrieval, reranking    |
| Structured storage | SQLite                                       |
| Graph retrieval    | NetworkX/Neo4j-oriented services             |
| Agent tools        | MCP, FastMCP, langchain-mcp-adapters         |
| Observability      | Langfuse, structured JSON logging            |
| Quality            | pytest, pytest-asyncio, ruff, pyright        |

## Những phần nên xem khi review kỹ thuật

| Mục cần đánh giá    | File/thư mục                                                    |
| ------------------------ | ----------------------------------------------------------------- |
| FastAPI entrypoint       | [src/main.py](src/main.py)                                           |
| DatabaseAgent            | [src/agents/database_agent.py](src/agents/database_agent.py)         |
| SQLite MCP server        | [src/mcp_servers/sqlite/server.py](src/mcp_servers/sqlite/server.py) |
| MCP client binding       | [src/tools/mcp_client.py](src/tools/mcp_client.py)                   |
| Qdrant retrieval         | [src/services/qdrant_retriever.py](src/services/qdrant_retriever.py) |
| Document chunking        | [src/services/document_chunker.py](src/services/document_chunker.py) |
| Evidence merging         | [src/services/evidence_merger.py](src/services/evidence_merger.py)   |
| Knowledge Graph services | [src/services/knowledge_graph/](src/services/knowledge_graph/)       |
| Data acquisition scripts | [scripts/01_acquisition/](scripts/01_acquisition/)                   |
| Extraction scripts       | [scripts/04_extraction/](scripts/04_extraction/)                     |
| Training/eval scripts    | [scripts/05_training_eval/](scripts/05_training_eval/)               |
| DB ingestion/indexing    | [scripts/06_db_ingestion/](scripts/06_db_ingestion/)                 |
| Tests                    | [tests/](tests/)                                                     |

## Engineering decisions đáng chú ý

- Source lineage là bắt buộc: mọi row domain trong SQLite có thể truy ngược về `source_table_id`, JSON gốc và PDF.
- Long/narrow schema được dùng cho benefit/premium values để so sánh plan cross-company dễ hơn.
- Agent không truy cập database trực tiếp; agent dùng MCP tools có domain boundary rõ ràng.
- Read-only database policy được enforce trong MCP server cho raw query tools.
- Hard filters theo company/plan/document được ưu tiên trong RAG để tránh trộn dữ liệu giữa các công ty.
- Table-heavy chunking giữ header bảng và context để retrieval không làm mất nghĩa của từng dòng.
- Observability được đặt ở cả tầng agent và MCP tool để debug được reasoning path lẫn tool result.

## Trạng thái hiện tại

Đã hoàn thành hoặc có implementation đáng review:

- Data pipeline từ PDF/Markdown/JSON đến SQLite, Qdrant và Knowledge Graph services.
- SQLite schema, ingestion mapping và domain tables cho bảo hiểm sức khỏe.
- SQLite MCP server với các tool phục vụ truy vấn bảo hiểm.
- DatabaseAgent tích hợp LangChain, MCP và Langfuse.
- Retrieval foundation: document chunking, Qdrant retriever, evidence objects, merger, citation formatter.
- Test suite gồm unit, integration và e2e structure.

Đang tiếp tục phát triển:

- Orchestrator bằng LangGraph để route giữa DatabaseAgent, PolicyAgent, ClaimAgent và FraudAgent.
- PolicyAgent RAG trả lời điều khoản có citation đầy đủ.
- ClaimAgent cho eligibility, payout calculation và human-in-the-loop review.
- Eval harness với benchmark intents và Langfuse scoring.
- Production deployment hardening.

## Review nhanh trong local

Các lệnh dưới đây dành cho reviewer kỹ thuật muốn kiểm tra codebase:

```bash
pip install -e ".[dev]"
pytest
ruff check src tests
ruff format --check src tests
```

Health API:

```bash
uvicorn src.main:app --reload
curl http://localhost:8000/health
```

## Tài liệu chuyên sâu

- [Multi-agent platform design](docs/architecture/2026-05-03-multi-agent-platform-design.md)
- [Quad-retrieval RAG architecture](docs/architecture/2026-05-04-quad-retrieval-rag-architecture.md)
- [SQLite schema specification](docs/database/sqlite_database_schema_specification.md)
- [Database MCP reference](docs/database/mcp_insurevn_db_reference.md)
- [Langfuse integration](docs/observability/langfuse_integration.md)
- [Data pipeline work log](docs/work_log/data_pipeline_processing_log.md)
