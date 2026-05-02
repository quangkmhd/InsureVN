# VLM Table Extraction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement an end-to-end pipeline using the Oumi framework to prepare dataset, fine-tune (QLoRA), evaluate, and run inference on Qwen2-VL-2B-Instruct to extract tables into Markdown on an 8GB VRAM GPU.

**Architecture:** 
The pipeline starts with a Python data formatting script that parses existing JSON/Image pairs into an Oumi-compatible conversational JSONL format. Then, Oumi YAML recipes are created for Supervised Fine-Tuning (SFT) using 4-bit QLoRA to fit 8GB VRAM, Evaluation (measuring Markdown exactness), and Inference (deploying the tuned LoRA adapter).

**Tech Stack:** Python 3.12, Oumi, Qwen2-VL-2B-Instruct, QLoRA, PyTorch.

---

### Task 1: Create Data Preparation Script

**Files:**
- Create: `scripts/prepare_oumi_vlm_dataset.py`
- Create: `tests/unit/test_prepare_oumi_dataset.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_prepare_oumi_dataset.py
import json
import os
import tempfile
from scripts.prepare_oumi_vlm_dataset import process_dataset

def test_process_dataset():
    with tempfile.TemporaryDirectory() as temp_dir:
        # Mock extracted dir
        extract_dir = os.path.join(temp_dir, "extracted")
        os.makedirs(extract_dir)
        
        # Mock image and json
        img_path = os.path.join(extract_dir, "test.jpg")
        with open(img_path, "wb") as f:
            f.write(b"fake_image")
            
        json_path = os.path.join(extract_dir, "test.json")
        data = {"markdown": "| Col1 | Col2 |\n|---|---|\n| A | B |"}
        with open(json_path, "w") as f:
            json.dump(data, f)
            
        out_file = os.path.join(temp_dir, "output.jsonl")
        
        # Run process
        process_dataset(extract_dir, out_file)
        
        # Verify
        with open(out_file, "r") as f:
            lines = f.readlines()
            
        assert len(lines) == 1
        item = json.loads(lines[0])
        assert len(item["messages"]) == 2
        assert item["messages"][0]["role"] == "user"
        assert item["messages"][1]["role"] == "assistant"
        assert item["messages"][1]["content"] == data["markdown"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/unit/test_prepare_oumi_dataset.py -v`
Expected: FAIL with ModuleNotFoundError or ImportError

- [ ] **Step 3: Write minimal implementation**

```python
# scripts/prepare_oumi_vlm_dataset.py
import os
import json
from pathlib import Path
import random

def process_dataset(input_dir: str, output_file: str):
    """Converts image/json pairs into Oumi JSONL conversational dataset."""
    input_path = Path(input_dir)
    dataset = []
    
    for json_file in input_path.rglob("*.json"):
        # Check if corresponding image exists
        img_extensions = ['.jpg', '.png', '.jpeg']
        img_path = None
        for ext in img_extensions:
            possible_img = json_file.with_suffix(ext)
            if possible_img.exists():
                img_path = possible_img
                break
                
        if not img_path:
            continue
            
        with open(json_file, 'r', encoding='utf-8') as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError:
                continue
                
        markdown_text = data.get("markdown")
        if not markdown_text:
            continue
            
        # Oumi Conversational Format
        record = {
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "image", "content": str(img_path.absolute())},
                        {"type": "text", "content": "Trích xuất toàn bộ dữ liệu bảng trong ảnh này sang định dạng Markdown chuẩn."}
                    ]
                },
                {
                    "role": "assistant",
                    "content": markdown_text
                }
            ]
        }
        dataset.append(record)
        
    # Write JSONL
    with open(output_file, 'w', encoding='utf-8') as f:
        for record in dataset:
            f.write(json.dumps(record, ensure_ascii=False) + '\n')

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="data/health_insurance/health_insurance_extracted", help="Input directory")
    parser.add_argument("--output", default="data/processed/oumi_vlm_train.jsonl", help="Output JSONL file")
    args = parser.parse_args()
    process_dataset(args.input, args.output)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/unit/test_prepare_oumi_dataset.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/prepare_oumi_vlm_dataset.py tests/unit/test_prepare_oumi_dataset.py
git commit -m "feat: add data preparation script for Oumi VLM fine-tuning"
```

---

### Task 2: Create Oumi Fine-Tuning Recipe (QLoRA)

**Files:**
- Create: `configs/oumi/train_qwen2_vl_2b.yaml`

- [ ] **Step 1: Write the Oumi SFT Recipe**

```yaml
# configs/oumi/train_qwen2_vl_2b.yaml
model:
  model_name_or_path: "Qwen/Qwen2-VL-2B-Instruct"
  torch_dtype: "bfloat16"
  trust_remote_code: True
  chat_template: "qwen2-vl"

# QLoRA 4-bit config for 8GB VRAM
quantization:
  q_lora: True
  bits: 4

peft:
  lora_r: 16
  lora_alpha: 32
  lora_dropout: 0.05
  target_modules: ["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"]

data:
  train:
    datasets:
      - dataset_name: "json"
        dataset_path: "data/processed/oumi_vlm_train.jsonl"

training:
  max_steps: 1000
  per_device_train_batch_size: 1
  gradient_accumulation_steps: 4
  learning_rate: 2e-5
  output_dir: "./output/qwen2-vl-table-extractor"
  enable_gradient_checkpointing: True
  logging_steps: 10
  save_steps: 200
  optimizer: "paged_adamw_32bit"
```

- [ ] **Step 2: Commit**

```bash
mkdir -p configs/oumi
git add configs/oumi/train_qwen2_vl_2b.yaml
git commit -m "chore: add Oumi QLoRA fine-tuning config for Qwen2-VL-2B"
```

---

### Task 3: Create Oumi Evaluation Recipe

**Files:**
- Create: `configs/oumi/eval_qwen2_vl_2b.yaml`

- [ ] **Step 1: Write the Oumi Evaluation Recipe**

```yaml
# configs/oumi/eval_qwen2_vl_2b.yaml
model:
  model_name_or_path: "Qwen/Qwen2-VL-2B-Instruct"
  adapter_model_path: "./output/qwen2-vl-table-extractor/checkpoint-1000" # Update path based on best checkpoint
  torch_dtype: "bfloat16"
  trust_remote_code: True
  chat_template: "qwen2-vl"

data:
  test:
    datasets:
      - dataset_name: "json"
        dataset_path: "data/processed/oumi_vlm_test.jsonl" # Can generate this split via script update later

evaluation:
  metrics:
    - name: "rouge"
    - name: "exact_match"
  generation:
    max_new_tokens: 1024
    temperature: 0.0
```

- [ ] **Step 2: Commit**

```bash
git add configs/oumi/eval_qwen2_vl_2b.yaml
git commit -m "chore: add Oumi evaluation config for table extraction"
```

---

### Task 4: Create Inference Script

**Files:**
- Create: `scripts/run_vlm_inference.py`

- [ ] **Step 1: Write the Inference Script using Oumi Python API**

```python
# scripts/run_vlm_inference.py
import argparse
from oumi.inference import NativeInferenceEngine
from oumi.core.configs import InferenceConfig, ModelParams, GenerationParams

def run_inference(image_path: str, model_dir: str, adapter_dir: str = None):
    # Setup model params
    model_params = ModelParams(
        model_name_or_path=model_dir,
        adapter_model_path=adapter_dir,
        torch_dtype="bfloat16",
        trust_remote_code=True,
        chat_template="qwen2-vl"
    )
    
    # Setup inference config
    config = InferenceConfig(
        model=model_params,
        generation=GenerationParams(max_new_tokens=1024, temperature=0.0)
    )
    
    # Initialize engine
    engine = NativeInferenceEngine(config=config)
    
    # Prepare multimodal input
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "image", "content": image_path},
                {"type": "text", "content": "Trích xuất toàn bộ dữ liệu bảng trong ảnh này sang định dạng Markdown chuẩn."}
            ]
        }
    ]
    
    # Generate
    result = engine.infer(messages)
    print("=== EXTRACTED TABLE ===")
    print(result.content)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--image", required=True, help="Path to input image")
    parser.add_argument("--model", default="Qwen/Qwen2-VL-2B-Instruct", help="Base model")
    parser.add_argument("--adapter", default="./output/qwen2-vl-table-extractor/checkpoint-1000", help="LoRA adapter path")
    args = parser.parse_args()
    
    run_inference(args.image, args.model, args.adapter)
```

- [ ] **Step 2: Commit**

```bash
git add scripts/run_vlm_inference.py
git commit -m "feat: add inference script using Oumi engine"
```
