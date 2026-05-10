# Knowledge Graph: Schema Discovery & Graph Building Pipeline

Tài liệu này chi tiết hóa quy trình 4 giai đoạn để xây dựng Đồ thị tri thức (Knowledge Graph) cho hệ thống InsureVN, từ việc khám phá cấu trúc thực thể đến việc kiểm định chất lượng dữ liệu cuối cùng.

---

## 1. Tổng quan (Overview)

Mục tiêu của pipeline này là chuyển đổi các tài liệu bảo hiểm phi cấu trúc (Markdown/PDF) thành một mạng lưới các thực thể (Entities) và quan hệ (Relationships) có ý nghĩa nghiệp vụ. Quy trình này đảm bảo tính nhất quán (Canonicalization) và độ tin cậy cao của bằng chứng đồ thị phục vụ cho Quad-Retrieval RAG.

![Defining Entities-Relationships](../../asset/Defining%20Entities-Relationships.png)

---

## 2. Quy trình 4 giai đoạn (The 4-Step Pipeline)

### Giai đoạn 1: Discover Schema (Khám phá cấu trúc)
*   **Script:** `scripts/07_knowledge_graph/01_discover_schema.py`
*   **Hành động:** Sử dụng LLM để đọc lướt qua một tập mẫu tài liệu và đề xuất các loại thực thể (Node Labels) và quan hệ (Relationship Types) tiềm năng.
*   **Kết quả:** Danh sách thô các ứng viên thực thể và quan hệ.

### Giai đoạn 2: Clean & Canonicalize Schema (Chuẩn hóa)
*   **Script:** `scripts/07_knowledge_graph/02_canonicalize_schema.py`
*   **Hành động:** Hợp nhất các thực thể trùng lặp (ví dụ: "Cty Bảo hiểm" và "Công ty Bảo hiểm"), chuẩn hóa tên gọi theo chuẩn nghiệp vụ và loại bỏ các quan hệ nhiễu.
*   **Kết quả:** Một Schema đã được làm sạch và thu gọn.

### Giai đoạn 3: Select Schema Contract (Chốt hợp đồng dữ liệu)
*   **Script:** `scripts/07_knowledge_graph/03_select_schema_v1.py`
*   **Hành động:** Xác định Schema Contract chính thức (V1). Đây là bộ khung "cứng" quy định các nhãn node và quan hệ được phép sử dụng trong quá trình trích xuất thực tế.
*   **Kết quả:** `allowed_nodes.csv` và `allowed_relationships.csv` trong `src/services/knowledge_graph/graph_schema/`.

### Giai đoạn 4: Build Knowledge Graph (Xây dựng đồ thị)
*   **Script:** `scripts/07_knowledge_graph/04_build_knowledge_graph.py`
*   **Hành động:** 
    1.  Duyệt qua toàn bộ tài liệu Markdown.
    2.  Trích xuất các thực thể và quan hệ dựa trên Schema Contract.
    3.  Gán định danh ổn định (Stable IDs) dựa trên metadata (Company, Plan...).
    4.  Liên kết với các đoạn văn bản (Qdrant Chunks) để đảm bảo tính truy vết (Lineage).
*   **Kết quả:** File `insurevn_graph.json` phục vụ cho việc nạp vào Neo4j/NetworkX.

---

## 3. Luồng dữ liệu (Data Flow)

### Đầu vào (Inputs):
*   **Policy Documents:** Các file Markdown/TXT đã được xử lý từ PDF.
*   **AI Providers:** Gemini, NVIDIA hoặc OpenRouter để thực hiện trích xuất thông minh.
*   **Qdrant Lineage:** Metadata từ các chunks đã được đánh chỉ số để tạo liên kết ngược.

### Đầu ra (Outputs):
*   **Schema Contract:** Định nghĩa cấu trúc đồ thị.
*   **Graph JSON:** Cơ sở dữ liệu đồ thị dạng file để triển khai nhanh.
*   **Quality Report:** Báo cáo kiểm định chất lượng đồ thị.

---

## 4. Kiểm định chất lượng (Quality Validation)

Quy trình này tích hợp `GraphQualityValidator` để tự động phát hiện:
*   **Orphan Nodes:** Các node mồ côi không có liên kết.
*   **Missing Lineage:** Các thực thể thiếu bằng chứng từ tài liệu gốc.
*   **Low Confidence:** Các quan hệ có độ tin cậy thấp từ LLM.
*   **Invalid Relationships:** Các quan hệ vi phạm Schema Contract.

---

## 5. Các mã nguồn liên quan (Related Source Code)

| Thành phần | Vị trí Source Code |
| :--- | :--- |
| **Scripts thực thi** | `scripts/07_knowledge_graph/` |
| **Logic nghiệp vụ** | `src/services/knowledge_graph/` |
| **Schema định nghĩa** | `src/services/knowledge_graph/graph_schema/` |
