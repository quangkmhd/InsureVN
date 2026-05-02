# Implementation Plan: Document AI Pipeline (Marker + Qwen2-VL 2B)

## Overview
Build a high-precision, two-stage document parsing pipeline optimized for consumer hardware (NVIDIA RTX 4060 8GB). The system leverages `Marker-pdf` for initial structural CPU parsing and a quantized, fine-tuned `Qwen2-VL-2B-Instruct` model for multimodal, GPU-accelerated refinement of complex Vietnamese insurance tables.

## Requirements
- Parse complex Vietnamese insurance PDFs (policies, tables, benefit schedules) with 99%+ accuracy for financial figures.
- Run entirely within an 8GB VRAM constraint (RTX 4060).
- Generate a "Table Correction" dataset mapping noisy Markdown to gold-standard Markdown.
- Fine-tune Qwen2-VL using Unsloth + QLoRA (4-bit quantization).
- Output fully structured JSON/Markdown data.

## Architecture Changes
- New module: `scripts/data_engine/marker_extractor.py` — Extract table coordinates and crop images.
- New module: `scripts/data_engine/generate_gold_standard.py` — Orchestrate GPT-4o/Claude to generate perfect target Markdown.
- New module: `scripts/data_engine/format_dataset.py` — Format data for Unsloth.
- New module: `scripts/finetune/qwen2vl_qlora.py` — Handle the Unsloth QLoRA fine-tuning process.
- New module: `src/eval/metrics.py` — Calculate TEDS and CER metrics.
- New module: `src/pipeline/document_parser.py` — End-to-end integrated pipeline class.

## Implementation Steps

### Phase 1: Data Engine (Sprint 1)
1. **Create Table Cropper & Noisy Markdown Generator** (`scripts/data_engine/marker_extractor.py`)
   - **Action:** Run Marker on `data/health_insurance_pdfs`, extract table coordinates (via Surya), output cropped images, and save the generated "noisy" Markdown.
   - **Why:** Generates the input side of our training data.
2. **Generate Gold Standard Target Data** (`scripts/data_engine/generate_gold_standard.py`)
   - **Action:** Pass the cropped table images to an advanced API (GPT-4o/Claude 3.5) to generate perfect Markdown representations.
   - **Why:** We need high-quality ground truth to teach Qwen2-VL how to correct the noisy Markdown.
3. **Format Dataset for Unsloth** (`scripts/data_engine/format_dataset.py`)
   - **Action:** Combine image crops, noisy Markdown, and gold-standard Markdown into a conversational JSONL format compatible with Qwen2-VL/Unsloth.

### Phase 2: Fine-Tuning Qwen2-VL 2B (Sprint 2)
4. **Setup Unsloth QLoRA Training Script** (`scripts/finetune/qwen2vl_qlora.py`)
   - **Action:** Implement 4-bit AWQ/GPTQ loading for `Qwen2-VL-2B-Instruct` using Unsloth. Configure QLoRA adapters targeting attention and MLP layers.
   - **Risk:** High — VRAM management is critical. Must configure gradient checkpointing and `batch_size=1` with accumulation.
5. **Execute and Export Fine-Tuned Model** (`scripts/finetune/export_model.py`)
   - **Action:** Merge the LoRA adapters with the base model and export to an optimized inference format.

### Phase 3: Evaluation (Sprint 3)
6. **Implement Evaluation Metrics** (`src/eval/metrics.py`)
   - **Action:** Write functions to calculate TEDS (comparing HTML/Markdown tree structures) and CER (focusing on numbers, dates, and currency fields).
7. **Run Validation Benchmark** (`scripts/eval/run_benchmark.py`)
   - **Action:** Run a held-out test set through the fine-tuned model and generate a detailed report of TEDS and CER scores.

### Phase 4: System Integration (Sprint 4)
8. **Build the E2E Hybrid Pipeline** (`src/pipeline/document_parser.py`)
   - **Action:** Create a class orchestrating: `PDF -> Marker -> Crop Tables -> Qwen2-VL Refinement -> Reconstruct Document -> Output JSON/Markdown`.

## Testing Strategy
- **Unit tests:** `tests/test_metrics.py` and `tests/test_marker_extractor.py`.
- **Integration tests:** Process a 1-page PDF through the E2E pipeline and verify output schema.
- **E2E tests:** Process 10 complex multi-page Vietnamese insurance policies, ensuring VRAM usage remains strictly under 8GB.
