# Luồng Ensemble Retriever hoàn chỉnh (Quad-Retrieval)

> Cấu trúc báo cáo kỹ thuật được áp dụng ngày 2026-05-09. Nội dung gốc lịch sử được giữ ở Mục 10 để truy vết.

## 1. Tóm tắt điều hành

Báo cáo kỹ thuật này ghi lại tài liệu nhật ký công việc `2026-05-09-ensemble-retriever-flow-technical-report.md` của InsureVN. Tài liệu được chuẩn hóa theo định dạng báo cáo kỹ thuật của dự án, đồng thời giữ nguyên nội dung và bằng chứng gốc bên dưới.

## 2. Mục tiêu và phạm vi

Mục tiêu là ghi lại công việc, quy trình, quyết định, benchmark hoặc inventory được mô tả trong file gốc. Phạm vi chuẩn hóa chỉ giới hạn ở tài liệu: không chạy lại benchmark, không thay đổi code triển khai và không thay đổi ý nghĩa của report gốc.

## 3. Bối cảnh

Phân loại: Kiến trúc retrieval ở Core Services; luồng quad-retrieval qua Qdrant, graph, SQLite, evidence merge và reranking.

Báo cáo này thuộc `docs/work_log/`, khu vực dùng cho báo cáo kỹ thuật, báo cáo benchmark, nhật ký quy trình và lịch sử triển khai của InsureVN.

## 4. Triển khai

Chi tiết triển khai, quy trình hoặc phân tích gốc được giữ trong Mục 10. Trong lần chuẩn hóa này, tài liệu được bọc bằng cấu trúc báo cáo kỹ thuật chung để các nhật ký công việc sau này có cùng bố cục về bối cảnh, bằng chứng, xác minh, kết quả, rủi ro và việc tiếp theo.

## 5. Bằng chứng và lệnh đã chạy

Bằng chứng dùng cho lần chuẩn hóa này:

- Tài liệu nguồn hiện có: `docs/work_log/2026-05-09-ensemble-retriever-flow-technical-report.md`
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

- Cập nhật báo cáo này khi triển khai của ensemble retriever, evidence schema hoặc chiến lược reranking thay đổi.
- Bổ sung lệnh verification nếu flow này được xác minh bằng tests hoặc retrieval readiness gates.

## 10. Nội dung gốc được giữ lại

Tài liệu này tổng hợp toàn bộ các hàm `def` trong luồng hoạt động từ Indexing (Đánh chỉ số) đến Retrieval (Truy vấn) và Post-processing (Hậu xử lý).

---

### GIAI ĐOẠN 1: INDEXING & GRAPH BUILDING (Tiền xử lý)

#### 1.1 Text & Vector Indexing
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

#### 1.2 Knowledge Graph Extraction
*Vị trí: `src/services/knowledge_graph/`*
- `schema_discovery.py` -> `discover_schema(...)`: Khám phá cấu trúc thực thể/quan hệ.
- `document_extractor.py` -> `extract(...)`: Trích xuất Knowledge Graph từ các chunks.
- `builder.py` -> `build(...)`: Khởi tạo đồ thị NetworkX/Neo4j.

---

### GIAI ĐOẠN 2: ENSEMBLE RETRIEVAL (Truy vấn song song)

Khi nhận được câu hỏi từ Supervisor, hệ thống kích hoạt 4 trụ cột:

#### 2.1 Pillar 1 & 2: Qdrant (Semantic & Keyword)
*Vị trí: `src/services/qdrant_retriever.py`*
- `retrieve(...)`: Hàm chính thực thi hybrid search.
- `_build_filter(...)`: Áp dụng Hard Filters (Company, Plan...).

#### 2.2 Pillar 3: Graph (Relationship Reasoning)
*Vị trí: `src/services/knowledge_graph/`*
- `retriever.py` -> `retrieve(...)`: Duyệt đồ thị tìm các liên kết logic.
- `document_graph_retriever.py` -> `create_retriever()`: Khởi tạo bộ duyệt đồ thị.

#### 2.3 Pillar 4: SQLite (Structured Facts)
*Vị trí: `src/agents/database_agent.py`*
- `invoke(...)`: LLM gọi SQL Tool để lấy dữ liệu số liệu chính xác (hạn mức, phí...).

---

### GIAI ĐOẠN 3: MERGING & RE-RANKING (Hợp nhất và Xếp hạng)

#### 3.1 Evidence Mapping (Chuẩn hóa dữ liệu)
- `qdrant_evidence.py` -> `from_payload(...)`: Chuẩn hóa kết quả Qdrant.
- `sqlite_evidence.py` -> `from_record(...)`: Chuẩn hóa kết quả SQLite.

#### 3.2 Evidence Merging (Trộn bằng chứng)
*Vị trí: `src/services/evidence_merger.py`*
- `merge(...)`: Khử trùng lặp, kiểm tra xung đột giữa các nguồn.

#### 3.3 Reranking (Tối ưu hóa thứ tự)
- `evidence_merger.py` -> `rerank_evidence(...)`: Sử dụng Cross-Encoder để xếp hạng lại.
- `jina_rerank_cross_encoder.py` -> `score(...)`: Gọi API Rerank bên ngoài.

---

### GIAI ĐOẠN 4: FINAL RESPONSE (Trả về kết quả)

#### 4.1 Citation Formatting (Trích dẫn)
*Vị trí: `src/services/citation_formatter.py`*
- `format_evidence(...)`: Tạo chuỗi citation cho Synthesizer Agent.

#### 4.2 Readiness Check (Kiểm tra trạng thái)
- `retrieval_readiness.py` -> `check_readiness()`: Kiểm tra hệ thống đã sẵn sàng phục vụ chưa.

---

### PHỤ LỤC: CÁC LƯU Ý KỸ THUẬT QUAN TRỌNG

#### A. Xử lý Preamble (Phần mở đầu) trong Chunking
Trong quá trình phát triển, chúng ta phát hiện ra rằng các tài liệu brochure bảo hiểm thường có phần Logo, Slogan và Thông tin pháp lý quan trọng đặt ở đầu trang, **trước cả tiêu đề đầu tiên**. 

- **Vấn đề:** Các thuật toán chia nhỏ theo Heading thông thường sẽ bỏ qua phần này.
- **Giải pháp:** `DocumentChunker` đã được cập nhật để tự động nhận diện và gom phần văn bản này vào một Parent Section đặc biệt gọi là `preamble`.
- **Tầm quan trọng:** Việc này đảm bảo AI không bỏ lỡ các giới hạn trách nhiệm (disclaimers) hoặc thông tin định danh công ty nằm ở đầu file.
