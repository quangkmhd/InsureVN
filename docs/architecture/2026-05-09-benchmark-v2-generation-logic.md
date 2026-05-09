# Logic Tạo Benchmark RAG V2 (Benchmark V2 Generation)

**Ngày tạo:** 2026-05-09
**Phạm vi:** Mô tả logic tự động tạo tập dữ liệu Ground Truth cho hệ thống đánh giá RAG của InsureVN.
**File nguồn:** `src/eval/context_benchmark_v2.py`

## 1. Tổng Quan
Benchmark V2 là bước tiến từ phương pháp tạo query dựa trên TF-IDF cũ. Nó sử dụng LLM để sinh ra các cặp Câu hỏi/Câu trả lời (Q&A) phức tạp hơn, bám sát thực tế và hỗ trợ đánh giá khả năng suy luận đa tầng.

## 2. Quy Trình Tạo Ground Truth

### Bước 1: Context Sampling (Lấy mẫu ngữ cảnh)
Hệ thống chia tài liệu thành các khối ngữ cảnh lớn (`ContextChunk`) với các tiêu chí:
- **Kích thước mục tiêu:** ~1500 tokens (whitespace-based).
- **Kích thước tối thiểu:** 80 tokens.
- **Bảo toàn bảng biểu:** Không cắt ngang qua bảng Markdown; nếu gặp bảng, khối sẽ được mở rộng để chứa trọn bộ bảng.
- **Metadata:** Lưu trữ `chunk_id`, `provider`, `source_path`, `line_range`.

### Bước 2: Phân Bổ Case (Distribution Planning)
Benchmark được chia thành các loại kịch bản (Case Types) để kiểm tra đa dạng năng lực:
- **`single_context`**: Câu hỏi dựa trên 1 đoạn văn bản duy nhất.
- **`two_context`**: Câu hỏi yêu cầu tổng hợp thông tin từ 2 đoạn văn bản khác nhau.
- **`three_context`**: Câu hỏi yêu cầu tổng hợp thông tin từ 3 đoạn văn bản khác nhau.
- **`table_context`**: Câu hỏi tập trung vào dữ liệu trong các bảng Markdown.

### Bước 3: LLM Synthesis (Sinh dữ liệu bằng LLM)
Sử dụng prompt chuyên biệt ("Expert RAG Benchmark Creator") gửi tới pool LLM slot (Gemini, Ollama, NVIDIA NIM, OpenRouter) để tạo:
- **Question:** Câu hỏi tự nhiên bằng tiếng Việt.
- **Gold Answer:** Câu trả lời chuẩn xác dựa duy nhất trên ngữ cảnh cung cấp.
- **Evidence Quotes:** Các đoạn trích dẫn nguyên văn từ tài liệu gốc (phải khớp từng ký tự).
- **Metadata bổ sung:** `task_type` (coverage, exclusion, claim...) và `risk_level` (low, medium, high).

### Bước 4: Validation & Grounding (Xác thực dữ liệu)
Mọi dữ liệu sinh ra bởi LLM đều được kiểm tra tự động trước khi chấp nhận:
- **Exact Match:** Đảm bảo `evidence_quotes` tồn tại 100% nguyên văn trong các `ContextChunk` đầu vào.
- **Context Coverage:** Với các case đa ngữ cảnh, phải có ít nhất một trích dẫn từ mỗi `chunk_id` tham gia để đảm bảo tính "multi-hop".
- **Source Tracking:** Xác định chính xác dòng bắt đầu (`line_start`) và kết thúc (`line_end`) của từng trích dẫn trong file gốc.

## 3. Thang Điểm Đánh Giá (Scoring Schema)

Benchmark V2 sử dụng thang điểm 10 để chấm điểm khả năng retrieval và trả lời của RAG:

| Tiêu chí | Điểm | Mô tả |
| :--- | :--- | :--- |
| **Retrieval Recall** | 3 | Tìm thấy tất cả các context chunks cần thiết để trả lời. |
| **Answer Faithfulness** | 3 | Câu trả lời trung thành với ngữ cảnh, không bịa đặt (hallucination). |
| **Evidence Integrity** | 2 | Tìm thấy chính xác các đoạn trích dẫn chứa bằng chứng. |
| **Citation Correctness** | 1 | Trích dẫn nguồn (source path/line range) chính xác. |
| **Context Adherence** | 1 | Không sử dụng kiến thức bên ngoài ngữ cảnh được cung cấp. |

---

## 4. Cách Chạy Sinh Benchmark

Để tạo tập dữ liệu benchmark mới, sử dụng lệnh:

```bash
python -m src.eval.context_benchmark_v2
```

Các tham số cấu hình chính nằm trong `ContextBenchmarkV2Config`:
- `input_dir`: Thư mục chứa dữ liệu Markdown bảo hiểm.
- `output_dir`: Thư mục lưu kết quả benchmark (JSONL).
- `max_workers`: Số lượng worker song song để gọi LLM.
- `distribution`: Tỷ lệ các loại case.
