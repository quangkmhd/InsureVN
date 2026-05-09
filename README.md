<p align="center">
  <a href="README.md"><b>Tiếng Việt</b></a> | <a href="docs/README.en.md">English</a>
</p>

<p align="center">
  <img src="asset/insurevn_logo.png" width="150" alt="InsureVN Logo"/>
</p>

<h1 align="center">InsureVN: Hybrid Full-Agent Swarm Platform</h1>

<p align="center">
  <b>Nền tảng Multi-Agent Swarm tối ưu hóa quy trình bảo hiểm Việt Nam dựa trên bằng chứng tri thức minh bạch</b>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.12.3-3776AB?style=flat&logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/Backend-FastAPI-009688?style=flat&logo=fastapi&logoColor=white" alt="FastAPI">
  <img src="https://img.shields.io/badge/Framework-LangGraph-orange?style=flat&logo=langchain&logoColor=white" alt="LangGraph">
  <img src="https://img.shields.io/badge/License-MIT-yellow?style=flat" alt="License">
  <br>
  <img src="https://img.shields.io/badge/Agents-9-blueviolet" alt="Agents">
  <img src="https://img.shields.io/badge/Retrieval-Quad_Engine-red" alt="Retrieval">
  <img src="https://img.shields.io/badge/Graph-Neo4j-008CC1?logo=neo4j&logoColor=white" alt="Graph">
  <img src="https://img.shields.io/badge/Observability-Langfuse-black" alt="Langfuse">
</p>

<p align="center">
  <a href="#-tính-năng-cốt-lõi">Tính năng</a>  · 
  <a href="#-kiến-trúc-hệ-thống">Kiến trúc</a>  · 
  <a href="#-quy-trình-dữ-liệu">Data Pipeline</a>  · 
  <a href="#-chunking-mastery">Chunking</a>  · 
  <a href="#-production-infrastructure">Infrastructure</a>  · 
  <a href="#-roadmap">Roadmap</a>  · 
  <a href="CHANGELOG.md">Changelog</a>
</p>

---

### 📢 Tin tức mới (Latest News)

- **[09/05/2026]** 📊 **Optimization Decision**: Sau khi đánh giá 9 chiến lược, hệ thống chính thức áp dụng `hierarchical_header_recursive` với cấu hình `900/150` tokens để đạt recall cao nhất.
- **[08/05/2026]** 🗄️ **Data Scale Milestone**: Hoàn tất nạp dữ liệu từ 83 tài liệu gốc, trích xuất **7,004 bệnh viện**, **3,766 quyền lợi** và **1,771 biểu phí** vào SQLite qua FastMCP.
- **[07/05/2026]** ⚖️ **LLM-as-a-Judge**: Hoàn thành chấm điểm tự động cho 1,350 trường hợp truy xuất bằng pool LLM đa nguồn (Gemini, NVIDIA, Ollama).
- **[06/05/2026]** 🎯 **Automated Ground Truth**: Triển khai quy trình tạo tập dữ liệu kiểm thử tự động dựa trên cấu trúc tài liệu (H1/H2) và Keyword Extraction.
- **[05/05/2026]** 🕸️ **KG Automation**: Tự động hóa việc khám phá (Discover) và chuẩn hóa (Canonicalize) Schema cho Knowledge Graph từ dữ liệu Markdown.
- **[04/05/2026]** 🧠 **Gemma4 Fine-tuned**: Huấn luyện thành công mô hình Vision-Language (VLM) chuyên biệt cho việc trích xuất bảng biểu bảo hiểm Việt Nam.
- **[03/05/2026]** 🏗️ **Quad-Retrieval**: Phê duyệt thiết kế kiến trúc 4 tầng (Vector + BM25 + Graph + SQL) nhằm triệt tiêu hoàn toàn Hallucination.

<details>
<summary>Tin tức cũ hơn</summary>

- **2026-05-02** 📑 **Table-to-Text & MCP Integration**: Tích hợp công cụ chuyển đổi bảng biểu sang văn bản tự sự và kết nối Database Agent với SQLite MCP Server.
- **2026-05-01** 🏷️ **JSON Classification Pipeline**: Hoàn thiện quy trình phân loại và trích xuất dữ liệu có cấu trúc từ tài liệu bảo hiểm.
- **2026-04-28** 📄 **Document AI Pipeline**: Khởi động chiến lược xây dựng pipeline xử lý tài liệu bảo hiểm thông minh (PDF-to-AI-ready).

</details>

---

## 💡 Tầm nhìn & Sứ mệnh (Vision)

> **"Thứ khó nhất không phải là Prompt, mà là Production Infrastructure."**

InsureVN không phải là một chatbot RAG đơn thuần, mà là một **Nền tảng Tác vụ thông minh (Agent Swarm Platform)** với hạ tầng tri thức tri-canonical, nơi mọi câu trả lời của AI đều có thể truy vết ngược lại tài liệu gốc với độ chính xác tuyệt đối.

---

## ✨ Tính năng cốt lõi

### 🌟 Tính năng nổi bật (Core Features)

- **✅ Hệ thống Quad-Retrieval Engine**: Kết hợp Vector (Qdrant), BM25, Graph (NetworkX) và SQL (SQLite) để triệt tiêu Hallucination. [Xem thiết kế](docs/architecture/2026-05-04-quad-retrieval-rag-architecture.md)
- **✅ [Pipeline 6 giai đoạn](docs/work_log/work_history.md)**: Quy trình xử lý dữ liệu bảo hiểm tự động từ PDF thô sang tri thức có cấu trúc.
- **✅ Benchmark V2 & Evaluation**: Hệ thống đánh giá chunking và retrieval tự động với bộ chỉ số chính xác cao.
- **🚧 Hybrid Agent Swarm (In Dev)**: Hệ thống đa tác vụ (Supervisor, Policy, Claim, Advisor...) đang được tích hợp qua LangGraph.
- **✅ Observability**: Giám sát toàn bộ luồng suy luận và hiệu suất hệ thống qua Langfuse.
- **✅ Document Extraction**: Công nghệ Table-to-Narrative giúp AI hiểu 100% các bảng biểu bảo hiểm phức tạp.

---

## 🏗️ Kiến trúc Hệ thống (System Architecture)

Dự án áp dụng mô hình **Hybrid Full Agent Swarm**, được điều phối bởi LangGraph để đảm bảo tính tin cậy cao nhất qua Quad-Retrieval Engine.

<p align="center">
  <img src="asset/insurevn-Architecture.png" alt="InsureVN Architecture Diagram" width="800px" />
</p>

### Quy trình 4 tầng truy vấn (Quad-Retrieval)

| Phương thức             | Công nghệ | Vai trò trong InsureVN                                                       |
| :------------------------- | :---------- | :---------------------------------------------------------------------------- |
| **Vector Search**    | Qdrant      | Tìm kiếm ngữ nghĩa, hiểu ngữ cảnh câu hỏi của người dùng.        |
| **Keyword Search**   | BM25        | Trích xuất chính xác tên bệnh, thuốc và các thuật ngữ pháp lý.   |
| **Graph Retrieval**  | Neo4j       | Suy luận quan hệ đa tầng (Entity-Relationship) giữa các điều khoản.  |
| **Structured Query** | SQLite      | Truy xuất con số chính xác về phí, hạn mức và danh mục bệnh viện. |
| **Search Agent**     | Tavily      | Tìm kiếm thông tin thị trường thời gian thực (Optional Tool).      |

### 📚 Cơ sở hạ tầng Tri thức (Tri-Canonical Knowledge Base)

Hệ thống duy trì sự nhất quán tri thức qua 3 kênh lưu trữ chuyên biệt:
- **SQLite (Structured Facts):** Lưu trữ 100% các con số "cứng" (**7,004 bệnh viện**, **3,766 quyền lợi**, **1,771 biểu phí**). Truy vấn qua **FastMCP Server** với [15+ công cụ nghiệp vụ](docs/database/mcp_insurevn_db_reference.md). [Chi tiết Schema](docs/database/sqlite_database_schema_specification.md).
- **Qdrant (Document Context):** Lưu trữ hàng chục ngàn đoạn văn bản (chunks) từ **83 tài liệu bảo hiểm** gốc, hỗ trợ tìm kiếm Hybrid (Dense + Sparse).
- **Knowledge Graph (NetworkX/Neo4j):** Bản đồ hóa các mối liên kết thực thể (Entity-Relationship) giữa Công ty → Gói bảo hiểm → Điều khoản loại trừ.

---

## ⚙️ Quy trình xử lý dữ liệu (Data Pipeline)

| Giai đoạn                | Hành động                                       | Kết quả đầu ra                                             |
| :------------------------- | :------------------------------------------------- | :------------------------------------------------------------- |
| **1. Acquisition**   | Crawl/Scrape PDF từ các hãng bảo hiểm.        | Kho PDF thô (Raw PDF).                                        |
| **2. Preprocessing** | Phân loại, lọc nhiễu và làm sạch dữ liệu. | Dữ liệu được tổ chức theo thư mục chuẩn.             |
| **3. Conversion**    | PDF -> Markdown & Narrative Table.                 | Bảng biểu phức tạp được chuyển sang văn bản tự sự. |
| **4. Extraction**    | Trích xuất Schema.                               | Dữ liệu JSON/SQL có cấu trúc.                             |
| **5. Graph Build**   | Chuẩn hóa thực thể (Canonicalization).         | Đồ thị tri thức Neo4j                                      |
| **6. Ingestion**     | Indexing vào Vector & Graph DB.                   | Hệ thống sẵn sàng truy vấn (Ready for RAG).               |

---

## 🧩 Chunking Mastery

### So sánh & Đánh giá (Evaluation)

Chúng tôi sử dụng hệ thống đánh giá tự động chuyên sâu để so sánh các chiến lược chunking, tập trung vào khả năng truy xuất bằng chứng (Evidence Retrieval).

- **Chiến lược tối ưu:** `hierarchical_header_recursive` (Phân tách theo cấp bậc tiêu đề và đệ quy) được xác định là phương pháp hiệu quả nhất cho các văn bản bảo hiểm phức tạp.
- **Cấu hình chuẩn:** Kích thước chunk **900 tokens** với độ chồng lấp (overlap) **150 tokens** mang lại recall tốt nhất trên tập dữ liệu thực tế.
- **Bộ chỉ số đánh giá:**
  - **Retrieval:** Hit@5 (Primary), MRR@5, Required Source Recall và Line Overlap Recall.
  - **Quality:** Redundancy ratio, Mid-sentence cut ratio, Table/Heading integrity.

> [!TIP]
> Xem chi tiết báo cáo đánh giá mới nhất (Benchmark V2) tại: `docs/work_log/2026-05-09-context-benchmark-v2-all-chunking-eval-report.md`

### Tự động tạo Ground Truth (Benchmark V2)

InsureVN triển khai quy trình tạo tập dữ liệu kiểm thử tự động V2 (Benchmark V2) sử dụng LLM để thay thế phương pháp TF-IDF cũ, giúp đánh giá RAG chuyên sâu hơn:

1. **Context Sampling:** Tự động lấy mẫu các khối văn bản lớn (~1500 tokens) từ corpus, đảm bảo bao phủ đầy đủ các kịch bản (single-context, multi-context, table-context).
2. **LLM Synthesis:** Sử dụng pool LLM slot (Gemini, Ollama, NVIDIA...) để tự động hóa việc tạo câu hỏi (Question), câu trả lời vàng (Gold Answer) và trích dẫn (Evidence Quotes).
3. **Multi-Context Reasoning:** Tự động ghép nối 2-3 ngữ cảnh từ cùng một tài liệu để tạo ra các câu hỏi so sánh và tổng hợp, kiểm tra khả năng suy luận phức tạp của Agent.
4. **Evidence Grounding:** Đối soát và lưu trữ chính xác `chunk_id`, `line_range` và copy nguyên văn trích dẫn để đảm bảo tính minh bạch của bằng chứng.
5. **10-Point Scoring Schema:** Đánh giá chi tiết dựa trên 5 tiêu chí: Retrieval Recall (3), Answer Faithfulness (3), Evidence Integrity (2), Citation Correctness (1) và Context Adherence (1).

> [!NOTE]
> Xem chi tiết logic tạo benchmark tại: [Benchmark V2 Generation Logic](docs/architecture/2026-05-09-benchmark-v2-generation-logic.md)

### 📚 Cơ sở khoa học (Scientific Foundation)

Kiến trúc của InsureVN được xây dựng dựa trên các nghiên cứu hàng đầu về RAG và Chunking:
- **Adaptive Chunking (LREC 2026):** [Optimizing Chunking-Method Selection for RAG](https://arxiv.org/pdf/2603.25333).
- **LightRAG Pattern:** Sử dụng Dual-level Graph Retrieval để tăng cường tính liên kết của tri thức.
- **NVIDIA Research:** [Finding the Best Chunking Strategy for Accurate AI Responses](https://developer.nvidia.com/blog/finding-the-best-chunking-strategy-for-accurate-ai-responses/).

---

## 🏗️ Production Infrastructure

Dự án đối mặt với thách thức lớn nhất: **Maintenance Nightmare** (Sự thay đổi chóng mặt của AI Stack). Chúng tôi giải quyết bằng một hạ tầng vững chắc:

- **Observability & Monitoring:** Tích hợp **Langfuse** để theo dõi Telemetry, Latency, Throughput và Cost Tracking cho từng yêu cầu.
- **Human-in-the-loop:** Cơ chế **Human Approval** cho các luồng rủi ro cao (Bồi thường/Chi trả).
- **Quality Gates:** Hệ thống **Eval & Guardrails** tự động kiểm tra tính an toàn và trung thực của câu trả lời trước khi gửi tới người dùng.
- **Reliability:** Triển khai cơ chế **Retries**, **Queue** xử lý bất đồng bộ và **Caching** để giảm thiểu chi phí API.
- **DevOps:** Quy trình **CI/CD** tự động, quản lý **Secrets** nghiêm ngặt và kiến trúc sẵn sàng cho việc **Scaling**.

---

## 🤖 Đội ngũ Agent Swarm

| Agent                 | Nhiệm vụ chính (Trạng thái thiết kế)                                                               |
| :-------------------- | :------------------------------------------------------------------------------ |
| **Supervisor**  | Phân loại ý định, đánh giá rủi ro và điều hướng luồng. (Design ✅) |
| **Policy**      | Chuyên gia phân tích văn bản điều khoản pháp lý. (Design ✅) |
| **Comparison**  | Chuyên gia so sánh sản phẩm và tư vấn cá nhân hóa. (Design ✅) |
| **Claim**       | Xử lý nghiệp vụ bồi thường và dự thảo phản hồi. (Design ✅) |
| **Validation**  | "Thẩm phán" thực hiện kiểm chứng chéo (Blind Review). (Design ✅) |
| **Calculation** | Thực hiện tính toán số học xác định (Deterministic). (Design ✅) |
| **Verifier**    | Kiểm soát an toàn, tuân thủ và độ đầy đủ của trích dẫn. (Design ✅) |

> [!NOTE]
> Các Agent trên hiện đang trong quá trình tích hợp vào luồng LangGraph. Xem chi tiết tại [Platform Design](docs/architecture/2026-05-03-multi-agent-platform-design.md).

---

## 🗺 Roadmap & Trạng thái phát triển

Dự án được triển khai theo 8 giai đoạn (Phases) chiến lược, từ hạ tầng dữ liệu đến Swarm tự trị:

### ✅ Giai đoạn nền tảng (Completed)
- **[Phase 00: Project Bootstrap](docs/blueprints/phase_00_project_bootstrap_and_api_foundation.md)**: Khởi tạo FastAPI, cấu hình Pydantic Settings và hạ tầng logging.
- **[Phase 01: Evidence Foundation](docs/blueprints/phase_01_evidence_foundation.md)**: Xây dựng hệ thống Merger, Citation lineage và chuẩn hóa Evidence model.
- **[Phase 02: Qdrant Document Retrieval](docs/blueprints/phase_02_qdrant_document_retrieval.md)**: Triển khai Vector Search, BM25 Hybrid và Evaluation hệ thống chunking.
- **[Phase 06: Evaluation Harness (Part 1)](docs/blueprints/phase_06_synthetic_dataset_eval_harness.md)**: Hoàn thành Benchmark V2 cho Retrieval và Chunking.

### 🚧 Giai đoạn triển khai (Ongoing)
- **[Phase 03: Knowledge Graph Foundation](docs/blueprints/phase_03_knowledge_graph_foundation.md)**: Tích hợp NetworkX/Neo4j để xử lý quan hệ đa tầng.
- **[Phase 04: Supervisor Routing Graph](docs/blueprints/phase_04_supervisor_routing_graph.md)**: Xây dựng LangGraph Supervisor để phân loại ý định (Intent) và rủi ro (Risk).
- **[Phase 06: Evaluation Harness (Part 2)](docs/blueprints/phase_06_synthetic_dataset_eval_harness.md)**: Mở rộng đánh giá E2E cho luồng suy luận của Agent Swarm.

### 🎯 Giai đoạn nâng cao (Planned)
- **[Phase 05: Specialist Workflows](docs/blueprints/phase_05_specialist_workflows.md)**: Triển khai logic nghiệp vụ cho PolicyAgent, ClaimAgent và AdvisorAgent.
- **[Phase 07: HITL Operational Review](docs/blueprints/phase_07_hitl_operational_review.md)**: Tích hợp cổng phê duyệt của con người (Human-in-the-loop) cho các quyết định bồi thường.
- **Deep Agents Integration**: Nâng cấp khả năng tự trị và xử lý tác vụ dài hơi (long-running) cho các specialist.

---

## 📁 Cấu trúc dự án (Project Structure)

<details>
<summary><b>Click để xem chi tiết cấu trúc thư mục</b></summary>

```text
InsureVN/
├── src/                    # Mã nguồn lõi
│   ├── agents/             # Logic điều phối các Agent
│   ├── services/           # Dịch vụ xử lý (Retrieval, Evidence, Graph)
│   ├── tools/              # Các công cụ bổ trợ (Search, MCP)
│   └── models/             # Định nghĩa Schema dữ liệu
├── scripts/                # Data Pipeline & Evaluation scripts
├── docs/                   # Tài liệu thiết kế, ADR & Work Logs
├── tests/                  # Hệ thống kiểm thử (Unit, Integration, E2E)
├── database/               # File cơ sở dữ liệu local (SQLite)
├── data/                   # Dữ liệu bảo hiểm (Raw, Processed)
└── asset/                  # Hình ảnh kiến trúc và tài sản dự án
```

</details>

---

<p align="center">
  Cảm ơn bạn đã ghé thăm <b>InsureVN</b> ✨
</p>
