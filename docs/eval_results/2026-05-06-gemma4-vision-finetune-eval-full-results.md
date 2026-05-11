# 2026-05-06 - Gemma 4 Vision (E2B) Fine-tuning & Evaluation Results

## 1. Tổng quan cấu hình (Configuration Overview)

| Tham số | Giá trị |
| :--- | :--- |
| **Model Gốc** | `unsloth/gemma-4-E2B-it` |
| **Framework** | `unsloth`, `trl`, `peft` |
| **Hardware** | NVIDIA Tesla T4 (Google Colab) |
| **LoRA Rank (r)** | 32 |
| **LoRA Alpha** | 32 |
| **Target Modules** | `all-linear` (Vision + Language layers) |
| **Epochs** | 2 |
| **Total Steps** | 330 |
| **Training Loss** | Khởi đầu: 15.47 -> Kết thúc: ~0.4 - 0.7 |
| **Thời gian train** | 02:07:04 |

## 2. Dữ liệu (Dataset)

*   **Tập huấn luyện (Train)**: 1,314 mẫu từ `oumi_vlm_train.jsonl` (Dữ liệu bảo hiểm sức khỏe Việt Nam).
*   **Tập kiểm tra (Test)**: 146 mẫu từ `oumi_vlm_test.jsonl`.
*   **Định dạng**: JSONL chứa `messages` với `image_path` và `content`.

## 3. Kết quả Benchmark (Full Test Set)

Benchmark được thực hiện trên toàn bộ 146 mẫu test, tập trung vào khả năng trích xuất thông tin dưới dạng Markdown và tính hợp lệ của cấu trúc JSON.

| Metric | Kết quả |
| :--- | :--- |
| **🎯 Avg Markdown Accuracy (ANLS)** | **64.9%** |
| **✅ Valid JSON Ratio** | **80.1%** |
| **ℹ️ Mean ANLS (Full String)** | **52.1%** |

### Chi tiết các mẫu thử nghiệm (Sample Inference)

#### Mẫu 1: Trích xuất Text đơn giản
*   **Assistant**: `{"has_content": true, "content_type": "text", "markdown": "CALL CENTER\n1800 - 58 88 12\nMiễn phí 24/7 toàn quốc", ...}`
*   **Ground Truth**: Tương tự.
*   **Nhận xét**: Model nhận diện tốt các thực thể ngắn và văn bản rõ ràng.

#### Mẫu 3: Trích xuất Bảng (Complex Table)
*   **Assistant**: Trích xuất bảng Markdown chính xác về cấu trúc cột (STT, Nhóm bệnh, Chi tiết, Thời gian chờ).
*   **Ground Truth**: Trích xuất đầy đủ các dòng.
*   **Nhận xét**: Khả năng OCR bảng của Gemma 4 E2B sau khi fine-tune rất ấn tượng, giữ được cấu trúc Markdown table chuẩn.

#### Mẫu 6: Chữ ký (Signature)
*   **Assistant**: `"Hình ảnh là một nét vẽ hoặc ký hiệu..."`
*   **Ground Truth**: `"Hình ảnh hiển thị một chữ ký viết tay."`
*   **Nhận xét**: Model nhận diện được bản chất nhưng mô tả còn hơi máy móc so với ground truth.

## 4. Phân tích lỗi (Error Analysis)

1.  **JSON Validation (19.9% lỗi)**: Một số trường hợp model bị ngắt quãng hoặc không đóng ngoặc nhọn đúng cách khi output quá dài (đặc biệt là với các bảng lớn).
2.  **Mô tả hình ảnh (Image Description)**: Đôi khi mô tả còn sơ sài hơn so với Ground Truth chi tiết.
3.  **Markdown Accuracy**: 64.9% là mức khá tốt cho một model 2B trên dữ liệu tiếng Việt chuyên ngành bảo hiểm, nhưng vẫn còn khoảng trống để cải thiện bằng cách tăng epoch hoặc tinh chỉnh dataset.

## 5. Kết luận

Việc fine-tune Gemma 4 Vision E2B bằng Unsloth mang lại hiệu quả cao về mặt tài nguyên (chạy được trên T4) và cải thiện rõ rệt khả năng trích xuất dữ liệu có cấu trúc từ tài liệu bảo hiểm. Đây là một base model tiềm năng cho module OCR Document Agent trong hệ thống InsureVN.
