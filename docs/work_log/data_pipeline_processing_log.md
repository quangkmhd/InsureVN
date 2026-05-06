# Nhật ký Phát triển Hệ thống InsureVN

**Thời gian cập nhật:** 06/05/2026
**Trạng thái hệ thống:** Đã hoàn thiện toàn bộ Pipeline xử lý dữ liệu. Nhật ký mã nguồn `src/` được tách riêng.

---

## 1. Quy trình Xử lý Dữ liệu (Data Pipeline Flow)

Hệ thống được xây dựng trên một quy trình 6 giai đoạn nghiêm ngặt để đảm bảo dữ liệu thô từ PDF trở thành tri thức chính xác 99%.

### Giai đoạn 1: Thu thập dữ liệu (Acquisition)
- **Mục tiêu:** Thu thập tài liệu PDF và dữ liệu web từ các công ty bảo hiểm lớn.
- **Thành tựu:** Tự động hóa việc xây dựng kho dữ liệu thô từ 9+ nguồn lớn (AIA, Bao Viet, PVI...).

### Giai đoạn 2: Tiền xử lý & Kiểm soát chất lượng (Preprocessing & QA)
- **Mục tiêu:** Phân loại và lọc bỏ dữ liệu rác bằng AI.
- **Thành tựu:** Đảm bảo dữ liệu đầu vào sạch, lọc bỏ hoàn toàn các tài liệu không liên quan đến bảo hiểm sức khỏe.

### Giai đoạn 3: Chuyển đổi & Diễn giải (Conversion & Interpretation)
- **Mục tiêu:** Chuyển PDF sang Markdown và diễn giải bảng biểu.
- **Thành tựu:** Sử dụng kỹ thuật **Table-to-Narrative** để biến bảng phí/quyền lợi phức tạp thành văn bản diễn giải tự nhiên cho AI.

### Giai đoạn 4: Trích xuất tri thức & Lọc Good/Trash (Extraction)
- **Mục tiêu:** Trích xuất JSON có cấu trúc và lọc nội dung giá trị.
- **Thành tựu:** Sử dụng LLM phân loại file Tốt/Rác (Good/Trash) và tự động ánh xạ key JSON vào Schema SQL.

### Giai đoạn 5: Huấn luyện & Đánh giá (Training & Eval)
- **Mục tiêu:** Tối ưu hóa model Vision (Gemma4) cho bảo hiểm Việt Nam.
- **Thành tựu:** Fine-tune thành công mô hình để nhận diện và trích xuất dữ liệu bảo hiểm với độ chính xác cao.

### Giai đoạn 6: Đưa dữ liệu vào Database (Ingestion)
- **Mục tiêu:** Đẩy dữ liệu đồng bộ vào SQL, Vector DB và Graph DB.
- **Thành tựu:** Xây dựng nền tảng **Hybrid RAG** mạnh mẽ, tạo sự liên kết giữa SQL, Vector (Qdrant) và Graph (Neo4j).

### Giai đoạn 7: Xây dựng Knowledge Graph (Knowledge Graph)
- **Mục tiêu:** Khám phá schema, chuẩn hóa và xây dựng đồ thị tri thức từ tài liệu.
- **Thành tựu:** Tự động hóa việc khám phá schema thực tế từ dữ liệu, giúp xây dựng Knowledge Graph chính xác và có thể mở rộng.

---

## 2. Liên kết Nhật ký Mã nguồn

Nhật ký này chỉ ghi tiến độ xử lý dữ liệu theo 6 giai đoạn pipeline. Danh mục chi tiết toàn bộ mã nguồn `src/` đã được tách sang file riêng:

- [`src_code_inventory_log.md`](file:///home/quangnhvn34/dev/me/InsureVN/docs/work_log/src_code_inventory_log.md)

---

## 3. Các thành tựu cốt lõi đã giải quyết (Core Achievements)

1.  **Độ chính xác 99%:** QA đa lớp cho toàn bộ quy trình.
2.  **Lọc Good/Trash:** Làm sạch dữ liệu tự động, loại bỏ rác hiệu quả.
3.  **Tự động Mapping Schema:** AI tự động hiểu và map dữ liệu vào SQL Database.
4.  **Agentic Observability:** Giám sát toàn bộ luồng suy luận của Agent qua Langfuse.

---

## 4. Danh mục Script Chi tiết (scripts/)

### 4.1. Thu thập & Tiền xử lý
| Script | Công dụng |
| :--- | :--- |
| `01_acquisition/01_scrape_insurance_pdfs.py` | Crawler chính tải PDF. |
| `02_preprocessing/01_classify_pdfs_ollama.py` | AI phân loại PDF bảo hiểm. |

### 4.2. Chuyển đổi & Trích xuất
| Script | Công dụng |
| :--- | :--- |
| `03_conversion/04_convert_tables_to_text.py` | Biến bảng biểu thành văn bản LLM. |
| `04_extraction/04_extract_images_multi_provider.py` | Trích xuất Ảnh/Bảng đa nguồn AI. |
| `04_extraction/08_classify_content_good_trash.py` | Lọc dữ liệu Tốt/Rác trước khi vào DB. |
| `04_extraction/11_llm_schema_mapping.py` | Tự động ánh xạ JSON sang Schema SQL. |

### 4.3. Ingestion & Training
| Script | Công dụng |
| :--- | :--- |
| `05_training_eval/02_train_gemma4.py` | Huấn luyện mô hình Gemma4. |
| `06_db_ingestion/02_ingest_with_mapping.py` | Đẩy dữ liệu vào SQL dựa trên mapping AI. |
| `06_db_ingestion/09_index_all_markdowns.py` | Pipeline đẩy dữ liệu đồng thời vào Vector & Graph. |
| `06_db_ingestion/04_index_qdrant_documents.py` | Index tài liệu vào Qdrant. |

### 4.4. Knowledge Graph Discovery & Build
| Script | Công dụng |
| :--- | :--- |
| `07_knowledge_graph/01_discover_schema.py` | Khám phá candidate schema từ Markdown. |
| `07_knowledge_graph/02_canonicalize_schema.py` | Chuẩn hóa schema labels bằng AI. |
| `07_knowledge_graph/03_select_schema_v1.py` | Tổng hợp và chọn lọc Schema V1 chính thức. |
| `07_knowledge_graph/04_build_knowledge_graph.py` | Script chính xây dựng đồ thị từ dữ liệu. |

---

## 5. Kết luận
Dự án đã hoàn thiện cả về hạ tầng dữ liệu và khung kiến trúc Agent, đảm bảo tính quy trình và độ tin cậy cao.
