# Complete Ensemble Retriever Flow (Quad-Retrieval)

Tài liệu này tổng hợp toàn bộ các hàm `def` trong luồng hoạt động từ Indexing (Đánh chỉ số) đến Retrieval (Truy vấn) và Post-processing (Hậu xử lý).

---

## GIAI ĐOẠN 1: INDEXING & GRAPH BUILDING (Tiền xử lý)

### 1.1 Text & Vector Indexing
*Vị trí: `src/services/`*
- `document_chunker.py` -> `chunk_markdown(...)`: 
    - **Phân cấp Cha-Con**: Tách Markdown thành `ParentSection` (theo Header) và `ChildChunk` (đoạn nhỏ) để giữ ngữ cảnh.
    - **Xử lý Bảng biểu (Table-Heavy)**: Tách bảng theo từng dòng, lặp lại tiêu đề cột (Column Headers) trong mỗi chunk để AI hiểu ngữ cảnh bảng.
    - **Preamble Handling**: Tự động nhận diện và gom văn bản trước tiêu đề đầu tiên vào mục `preamble`.
    - **ID định danh**: Tạo ID duy nhất (Slugified) dựa trên nội dung và vị trí để đảm bảo tính ổn định (Idempotency).
- `qdrant_retriever.py` -> `index_chunks(...)`:
    - **Hybrid Search Indexing**: Đẩy đồng thời **Dense Vector** (Semantic search qua Google GenAI/FastEmbed) và **Sparse Vector** (Keyword search qua BM25).
    - **Normalization**: Chuẩn hóa tiếng Việt sang không dấu (`normalize_vietnamese_text`) để tăng độ chính xác cho tìm kiếm từ khóa.
    - **Payload Enrichment**: Đính kèm đầy đủ metadata (Company, Plan, Section Type, Lineage) phục vụ lọc dữ liệu cứng (Hard Filters).

### 1.2 Knowledge Graph Extraction
*Vị trí: `src/services/knowledge_graph/`*
- `schema_discovery.py` -> `discover_schema(...)`: Khám phá cấu trúc thực thể/quan hệ.
- `document_extractor.py` -> `extract(...)`: Trích xuất Knowledge Graph từ các chunks.
- `builder.py` -> `build(...)`: Khởi tạo đồ thị NetworkX/Neo4j.

---

## GIAI ĐOẠN 2: ENSEMBLE RETRIEVAL (Truy vấn song song)

Khi nhận được câu hỏi từ Supervisor, hệ thống kích hoạt 4 trụ cột:

### 2.1 Pillar 1 & 2: Qdrant (Semantic & Keyword)
*Vị trí: `src/services/qdrant_retriever.py`*
- `retrieve(...)`: Hàm chính thực thi hybrid search.
- `_build_filter(...)`: Áp dụng Hard Filters (Company, Plan...).

### 2.2 Pillar 3: Graph (Relationship Reasoning)
*Vị trí: `src/services/knowledge_graph/`*
- `retriever.py` -> `retrieve(...)`: Duyệt đồ thị tìm các liên kết logic.
- `document_graph_retriever.py` -> `create_retriever()`: Khởi tạo bộ duyệt đồ thị.

### 2.3 Pillar 4: SQLite (Structured Facts)
*Vị trí: `src/agents/database_agent.py`*
- `invoke(...)`: LLM gọi SQL Tool để lấy dữ liệu số liệu chính xác (hạn mức, phí...).

---

## GIAI ĐOẠN 3: MERGING & RE-RANKING (Hợp nhất và Xếp hạng)

### 3.1 Evidence Mapping (Chuẩn hóa dữ liệu)
- `qdrant_evidence.py` -> `from_payload(...)`: Chuẩn hóa kết quả Qdrant.
- `sqlite_evidence.py` -> `from_record(...)`: Chuẩn hóa kết quả SQLite.

### 3.2 Evidence Merging (Trộn bằng chứng)
*Vị trí: `src/services/evidence_merger.py`*
- `merge(...)`: Khử trùng lặp, kiểm tra xung đột giữa các nguồn.

### 3.3 Reranking (Tối ưu hóa thứ tự)
- `evidence_merger.py` -> `rerank_evidence(...)`: Sử dụng Cross-Encoder để xếp hạng lại.
- `jina_rerank_cross_encoder.py` -> `score(...)`: Gọi API Rerank bên ngoài.

---

## GIAI ĐOẠN 4: FINAL RESPONSE (Trả về kết quả)

### 4.1 Citation Formatting (Trích dẫn)
*Vị trí: `src/services/citation_formatter.py`*
- `format_evidence(...)`: Tạo chuỗi citation cho Synthesizer Agent.

### 4.2 Readiness Check (Kiểm tra trạng thái)
- `retrieval_readiness.py` -> `check_readiness()`: Kiểm tra hệ thống đã sẵn sàng phục vụ chưa.

---

## PHỤ LỤC: CÁC LƯU Ý KỸ THUẬT QUAN TRỌNG

### A. Xử lý Preamble (Phần mở đầu) trong Chunking
Trong quá trình phát triển, chúng ta phát hiện ra rằng các tài liệu brochure bảo hiểm thường có phần Logo, Slogan và Thông tin pháp lý quan trọng đặt ở đầu trang, **trước cả tiêu đề đầu tiên**. 

- **Vấn đề:** Các thuật toán chia nhỏ theo Heading thông thường sẽ bỏ qua phần này.
- **Giải pháp:** `DocumentChunker` đã được cập nhật để tự động nhận diện và gom phần văn bản này vào một Parent Section đặc biệt gọi là `preamble`.
- **Tầm quan trọng:** Việc này đảm bảo AI không bỏ lỡ các giới hạn trách nhiệm (disclaimers) hoặc thông tin định danh công ty nằm ở đầu file.
