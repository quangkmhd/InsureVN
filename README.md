# InsureVN - AI Engineering Portfolio Project

> README này được viết cho nhà tuyển dụng và reviewer kỹ thuật. Mục tiêu không phải là hướng dẫn cộng đồng sử dụng thư viện, mà là thể hiện phạm vi công việc, năng lực kỹ thuật và các quyết định engineering tôi đã trực tiếp xây dựng trong dự án.

## Tóm tắt cho nhà tuyển dụng

InsureVN là dự án AI Engineering cho ngành bảo hiểm sức khỏe Việt Nam. Tôi xây hệ thống từ tầng dữ liệu đến agent: thu thập PDF bảo hiểm, chuyển đổi tài liệu không cấu trúc thành dữ liệu có lineage, xây SQLite database, indexing vào Qdrant/Knowledge Graph, thiết kế MCP tools, và phát triển agent có observability.

Điểm chính nhà tuyển dụng có thể đánh giá:

- Năng lực thiết kế hệ thống AI nhiều tầng: data pipeline, retrieval, graph, database, agent orchestration.
- Kinh nghiệm xử lý dữ liệu thực tế: PDF tiếng Việt, bảng biểu bảo hiểm, schema không đồng nhất, OCR noise, mapping JSON sang SQL.
- Kinh nghiệm agentic AI production patterns: MCP server, LangChain/LangGraph, RAG evidence, citation, hard filters, Langfuse tracing.
- Tư duy engineering: source lineage, read-only database tools, cấu hình tập trung, unit/integration/e2e tests, logging và observability.

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
| Test modules                          |        45 |

Nguồn số liệu: [docs/database/sqlite_database_schema_specification.md](docs/database/sqlite_database_schema_specification.md)

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
