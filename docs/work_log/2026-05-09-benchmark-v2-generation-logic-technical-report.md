# Logic Tạo Benchmark RAG V2 (Benchmark V2 Generation)

> Cấu trúc báo cáo kỹ thuật được áp dụng ngày 2026-05-09. Nội dung gốc lịch sử được giữ ở Mục 10 để truy vết.

## 1. Tóm tắt điều hành

Báo cáo kỹ thuật này ghi lại tài liệu nhật ký công việc `2026-05-09-benchmark-v2-generation-logic-technical-report.md` của InsureVN. Tài liệu được chuẩn hóa theo định dạng báo cáo kỹ thuật của dự án, đồng thời giữ nguyên nội dung và bằng chứng gốc bên dưới.

## 2. Mục tiêu và phạm vi

Mục tiêu là ghi lại công việc, quy trình, quyết định, benchmark hoặc inventory được mô tả trong file gốc. Phạm vi chuẩn hóa chỉ giới hạn ở tài liệu: không chạy lại benchmark, không thay đổi code triển khai và không thay đổi ý nghĩa của report gốc.

## 3. Bối cảnh

Phân loại: Giai đoạn Training & Eval; tài liệu logic sinh Benchmark V2 và scoring schema.

Báo cáo này thuộc `docs/work_log/`, khu vực dùng cho báo cáo kỹ thuật, báo cáo benchmark, nhật ký quy trình và lịch sử triển khai của InsureVN.

## 4. Triển khai

Chi tiết triển khai, quy trình hoặc phân tích gốc được giữ trong Mục 10. Trong lần chuẩn hóa này, tài liệu được bọc bằng cấu trúc báo cáo kỹ thuật chung để các nhật ký công việc sau này có cùng bố cục về bối cảnh, bằng chứng, xác minh, kết quả, rủi ro và việc tiếp theo.

## 5. Bằng chứng và lệnh đã chạy

Bằng chứng dùng cho lần chuẩn hóa này:

- Tài liệu nguồn hiện có: `docs/work_log/2026-05-09-benchmark-v2-generation-logic-technical-report.md`
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

- Giữ báo cáo này đồng bộ với mã nguồn, lệnh và hiện vật đầu ra mà nó tham chiếu.
- Chạy lại bước xác minh riêng của task trước khi dùng metrics lịch sử cho quyết định kỹ thuật mới.

## 10. Nội dung gốc được giữ lại

**Ngày tạo:** 2026-05-09
**Phạm vi:** Mô tả logic tự động tạo tập dữ liệu Ground Truth cho hệ thống đánh giá RAG của InsureVN.
**File nguồn:** `src/eval/context_benchmark_v2.py`

### 1. Tổng Quan
Benchmark V2 là bước tiến từ phương pháp tạo query dựa trên TF-IDF cũ. Nó sử dụng LLM để sinh ra các cặp Câu hỏi/Câu trả lời (Q&A) phức tạp hơn, bám sát thực tế và hỗ trợ đánh giá khả năng suy luận đa tầng.

### 2. Quy Trình Tạo Ground Truth

#### Bước 1: Context Sampling (Lấy mẫu ngữ cảnh)
Hệ thống chia tài liệu thành các khối ngữ cảnh lớn (`ContextChunk`) với các tiêu chí:
- **Kích thước mục tiêu:** ~1500 tokens (whitespace-based).
- **Kích thước tối thiểu:** 80 tokens.
- **Bảo toàn bảng biểu:** Không cắt ngang qua bảng Markdown; nếu gặp bảng, khối sẽ được mở rộng để chứa trọn bộ bảng.
- **Metadata:** Lưu trữ `chunk_id`, `provider`, `source_path`, `line_range`.

#### Bước 2: Phân Bổ Case (Distribution Planning)
Benchmark được chia thành các loại kịch bản (Case Types) để kiểm tra đa dạng năng lực:
- **`single_context`**: Câu hỏi dựa trên 1 đoạn văn bản duy nhất.
- **`two_context`**: Câu hỏi yêu cầu tổng hợp thông tin từ 2 đoạn văn bản khác nhau.
- **`three_context`**: Câu hỏi yêu cầu tổng hợp thông tin từ 3 đoạn văn bản khác nhau.
- **`table_context`**: Câu hỏi tập trung vào dữ liệu trong các bảng Markdown.

#### Bước 3: LLM Synthesis (Sinh dữ liệu bằng LLM)
Sử dụng prompt chuyên biệt ("Expert RAG Benchmark Creator") gửi tới pool LLM slot (Gemini, Ollama, NVIDIA NIM, OpenRouter) để tạo:
- **Question:** Câu hỏi tự nhiên bằng tiếng Việt.
- **Gold Answer:** Câu trả lời chuẩn xác dựa duy nhất trên ngữ cảnh cung cấp.
- **Evidence Quotes:** Các đoạn trích dẫn nguyên văn từ tài liệu gốc (phải khớp từng ký tự).
- **Metadata bổ sung:** `task_type` (coverage, exclusion, claim...) và `risk_level` (low, medium, high).

#### Bước 4: Validation & Grounding (Xác thực dữ liệu)
Mọi dữ liệu sinh ra bởi LLM đều được kiểm tra tự động trước khi chấp nhận:
- **Exact Match:** Đảm bảo `evidence_quotes` tồn tại 100% nguyên văn trong các `ContextChunk` đầu vào.
- **Context Coverage:** Với các case đa ngữ cảnh, phải có ít nhất một trích dẫn từ mỗi `chunk_id` tham gia để đảm bảo tính "multi-hop".
- **Source Tracking:** Xác định chính xác dòng bắt đầu (`line_start`) và kết thúc (`line_end`) của từng trích dẫn trong file gốc.

### 3. Thang Điểm Đánh Giá (Scoring Schema)

Benchmark V2 sử dụng thang điểm 10 để chấm điểm khả năng retrieval và trả lời của RAG:

| Tiêu chí | Điểm | Mô tả |
| :--- | :--- | :--- |
| **Retrieval Recall** | 3 | Tìm thấy tất cả các context chunks cần thiết để trả lời. |
| **Answer Faithfulness** | 3 | Câu trả lời trung thành với ngữ cảnh, không bịa đặt (hallucination). |
| **Evidence Integrity** | 2 | Tìm thấy chính xác các đoạn trích dẫn chứa bằng chứng. |
| **Citation Correctness** | 1 | Trích dẫn nguồn (source path/line range) chính xác. |
| **Context Adherence** | 1 | Không sử dụng kiến thức bên ngoài ngữ cảnh được cung cấp. |

---

### 4. Cách Chạy Sinh Benchmark

Để tạo tập dữ liệu benchmark mới, sử dụng lệnh:

```bash
python -m src.eval.context_benchmark_v2
```

Các tham số cấu hình chính nằm trong `ContextBenchmarkV2Config`:
- `input_dir`: Thư mục chứa dữ liệu Markdown bảo hiểm.
- `output_dir`: Thư mục lưu kết quả benchmark (JSONL).
- `max_workers`: Số lượng worker song song để gọi LLM.
- `distribution`: Tỷ lệ các loại case.
