# Design Spec: Optimized Document AI Pipeline for Insurance (InsureVN)

**Date:** 2026-04-28
**Status:** Approved
**Priority:** Accuracy > Cost > Latency
**Target Hardware:** NVIDIA RTX 4060 (8GB VRAM)

## 1. Objective
Build a high-precision document parsing pipeline to extract structured JSON/Markdown data from complex Vietnamese insurance PDFs (policies, tables, benefit schedules), minimizing manual correction and ensuring 99%+ accuracy for financial figures.

## 2. System Architecture: Hybrid Refiner Pipeline

The system uses a two-stage process to balance speed and extreme accuracy on consumer-grade hardware.

### Phase 1: Structural Parsing (CPU-heavy)
- **Tool:** `Marker-pdf` (based on Surya and OCR engines).
- **Process:** Convert entire PDF to Markdown to handle standard text paragraphs efficiently.
- **Output:** Clean text for standard paragraphs, but potentially corrupted Markdown for complex insurance tables (merged cells, multi-line headers).

### Phase 2: Multimodal Table Refinement (GPU-heavy)
- **Model:** `Qwen2-VL-2B-Instruct` (Quantized to 4-bit AWQ/GPTQ).
- **Process:** 
    1. Identify table coordinates using Marker's internal metadata (Surya output).
    2. Crop high-resolution image patches of identified table areas.
    3. Input the crop + the corrupted Markdown snippet from Phase 1 into Qwen2-VL.
    4. Model outputs the "Gold Standard" corrected Markdown by visually cross-referencing the image.

## 3. Model Optimization (RTX 4060 8GB Compatibility)

| Technique | Implementation | VRAM Usage |
| :--- | :--- | :--- |
| **Quantization** | 4-bit AWQ | ~1.8GB for weights |
| **Inference Framework**| `Unsloth` / `vLLM` | Optimized memory tiling |
| **Context Management** | Image-only prompt focus | Leaves ~5-6GB for KV Cache/Images |

## 4. Fine-tuning Strategy (Table Correction)

### 4.1. Training Setup
- **Framework:** `Unsloth` + `QLoRA`.
- **Target:** Vietnamese insurance table structures (benefit schedules, premium tables).
- **Goal:** Correct character errors in numbers and structural errors in Markdown tables.

### 4.2. Dataset (InsureVN Domain)
- **Source:** Existing PDFs in `data/health_insurance_pdfs`.
- **Method:** 
    - Use SOTA models (GPT-4o) to generate Ground Truth for 500+ tables.
    - Use Marker to generate "noisy" inputs.
    - Train on the mapping: `(Image + Noisy MD) -> Corrected MD`.

## 5. Evaluation Metrics

- **TEDS (Table Extraction Discrete Score):** Measures structural similarity of the table tree.
- **CER (Character Error Rate):** Calculated specifically for currency and date fields.
- **Visual Verification:** Accuracy of detecting checked/unchecked boxes (if needed in future).

## 6. Implementation Roadmap (Priority: Data & Fine-tune First)
1.  **Sprint 1 (Data Engine):** Xây dựng tập dữ liệu "Table Correction" (500+ mẫu) từ các PDF bảo hiểm hiện có. Tạo cặp dữ liệu (Ảnh crop + MD lỗi từ Marker) và MD chuẩn (Gold Standard).
2.  **Sprint 2 (Fine-tuning):** Sử dụng Unsloth + QLoRA để fine-tune Qwen2-VL 2B trên RTX 4060. Mục tiêu: Model học được cách sửa lỗi bảng tiếng Việt và hiểu cấu trúc bảo hiểm.
3.  **Sprint 3 (Evaluation):** Đánh giá model sau fine-tune bằng chỉ số TEDS và CER. Đảm bảo đạt độ chính xác yêu cầu trước khi tích hợp vào pipeline.
4.  **Sprint 4 (System Integration):** Hoàn thiện pipeline tự động: PDF -> Marker -> Table Cropper -> Fine-tuned Qwen2-VL -> Final Structured JSON.
