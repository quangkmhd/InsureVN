# 2026-05-06 - Báo cáo kỹ thuật Fine-tune & Đánh giá Gemma 4 Vision E2B

## 1. Tóm tắt điều hành

Báo cáo này ghi lại quá trình huấn luyện tinh chỉnh (fine-tuning) và đánh giá mô hình thị giác máy tính **Gemma 4 Vision (E2B)** trên dữ liệu bảo hiểm sức khỏe Việt Nam. Quá trình sử dụng thư viện **Unsloth** để tối ưu hóa hiệu năng trên Google Colab (Tesla T4). Kết quả cho thấy mô hình cải thiện đáng kể khả năng trích xuất văn bản và bảng biểu dưới dạng Markdown/JSON, đạt độ chính xác Markdown trung bình **64.9%**.

## 2. Mục tiêu và phạm vi

- **Mục tiêu**: Tinh chỉnh mô hình Gemma 4 Vision để tối ưu hóa khả năng OCR và trích xuất dữ liệu có cấu trúc (Structured Data Extraction) từ các tài liệu bảo hiểm (PDF converted to images/markdown).
- **Phạm vi**: 
    - Huấn luyện trên 1,314 mẫu dữ liệu thực tế đã được gán nhãn.
    - Đánh giá trên 146 mẫu test độc lập.
    - Tập trung vào các chỉ số: Markdown Accuracy (ANLS), JSON Validation Ratio, và Mean ANLS.

## 3. Bối cảnh

- **Data pipeline phase**: Training & Eval (Phase 5 trong quy trình 6 giai đoạn của InsureVN).
- **System tier**: Intelligent Agents (Cung cấp năng lực cho OCR DocumentAgent).
- **Vấn đề**: Các mô hình OCR truyền thống thường gặp khó khăn với cấu trúc bảng phức tạp và thuật ngữ bảo hiểm tiếng Việt. Việc fine-tune một Vision-Language Model (VLM) nhỏ gọn như Gemma 4 E2B giúp giải quyết bài toán này với chi phí vận hành thấp.

## 4. Triển khai

1.  **Môi trường**: Google Colab với GPU Tesla T4.
2.  **Công cụ**: 
    - `Unsloth`: Tăng tốc độ huấn luyện 2x và giảm mức sử dụng VRAM.
    - `FastVisionModel`: Patching Gemma 4 cho Vision fine-tuning.
    - `LoRA`: Cấu hình r=32, alpha=32 để cập nhật trọng số hiệu quả.
3.  **Quy trình**:
    - Mount Google Drive để lấy dataset và lưu model weights.
    - Chuyển đổi dataset JSONL sang định dạng `messages` tương thích với Unsloth.
    - Huấn luyện trong 2 epochs (330 steps) với gradient accumulation.
    - Lưu model dưới dạng LoRA adapters và GGUF (dự kiến).

## 5. Bằng chứng và lệnh đã chạy

Toàn bộ quá trình được thực thi trong notebook: `train_gemma4_colab.ipynb`.

**Lệnh quan trọng:**
```python
model, processor = FastVisionModel.from_pretrained("unsloth/gemma-4-E2B-it")
model = FastVisionModel.get_peft_model(
    model,
    finetune_vision_layers=True,
    finetune_language_layers=True,
    r=32,
    lora_alpha=32,
    target_modules="all-linear",
)
# Training loop via SFTTrainer
trainer.train()
```

## 6. Xác minh

Xác minh thông qua việc chạy Benchmark trên 146 mẫu test sau khi huấn luyện:
- Kiểm tra tính hợp lệ của JSON output.
- Tính toán Average Normalized Levenshtein Similarity (ANLS) cho trường `markdown`.
- So sánh trực quan Assistant Response với Ground Truth cho 10 mẫu ngẫu nhiên.

## 7. Kết quả

- **Loss**: Giảm từ 15.4 xuống mức ổn định dưới 1.0.
- **Metrics**:
    - **Markdown Accuracy**: 64.9%
    - **JSON Validity**: 80.1%
    - **Mean ANLS**: 52.1%
- **Hiện vật đầu ra**: 
    - Model weights (LoRA): `gemma4-e2b-finetuned-lora/`
    - Báo cáo chi tiết: [2026-05-06-gemma4-vision-finetune-eval-full-results.md](file:///home/quangnhvn34/dev/me/InsureVN/docs/eval_results/2026-05-06-gemma4-vision-finetune-eval-full-results.md)

## 8. Rủi ro và giới hạn

- **Lỗi định dạng JSON**: Khoảng 20% phản hồi không phải là JSON hợp lệ do bị cắt ngang hoặc sai cú pháp khi bảng quá dài.
- **Phụ thuộc GPU**: Việc huấn luyện vẫn yêu cầu GPU có ít nhất 12GB VRAM (T4 là mức tối thiểu).
- **Hạn chế ngôn ngữ**: Vẫn còn một số lỗi chính tả nhỏ trong phần OCR văn bản tiếng Việt phức tạp.

## 9. Việc tiếp theo

1.  **Khắc phục JSON**: Triển khai cơ chế constrained generation hoặc post-processing để đảm bảo JSON luôn hợp lệ.
2.  **Mở rộng Dataset**: Bổ sung thêm các mẫu bảng biểu "nhiễu" cao để tăng độ bền bỉ (robustness).
3.  **Tích hợp Agent**: Kết nối model đã huấn luyện vào `OCR DocumentAgent` trong LangGraph workflow.
4.  **Xuất GGUF**: Chuyển đổi sang định dạng GGUF để chạy offline bằng Ollama hoặc Llama.cpp.
