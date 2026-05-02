import unsloth
from unsloth import FastVisionModel, get_chat_template

import argparse
import json
import os
import time

import torch
from PIL import Image
from transformers import TextStreamer


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def get_gpu_memory_stats() -> dict | None:
    """Lấy thông tin VRAM sử dụng hiện tại."""
    if torch.cuda.is_available():
        allocated = torch.cuda.memory_allocated() / (1024**3)
        reserved = torch.cuda.memory_reserved() / (1024**3)
        max_allocated = torch.cuda.max_memory_allocated() / (1024**3)
        return {
            "allocated_gb": round(allocated, 3),
            "reserved_gb": round(reserved, 3),
            "max_allocated_gb": round(max_allocated, 3),
        }
    return None


def format_user_messages(raw_messages: list[dict]) -> list[dict]:
    """Convert JSONL user message format to Unsloth inference format.

    Input: ``[{"type": "image_path", "content": "..."}, {"type": "text", "content": "..."}]``
    Output: ``[{"type": "image", "image": "..."}, {"type": "text", "text": "..."}]``
    """
    messages: list[dict] = []
    for msg in raw_messages:
        if msg["role"] != "user":
            continue
        new_content: list[dict] = []
        for item in msg["content"]:
            if item["type"] == "image_path":
                new_content.append({"type": "image", "image": item["content"]})
            elif item["type"] == "text":
                new_content.append({"type": "text", "text": item["content"]})
        messages.append({"role": "user", "content": new_content})
    return messages


def run_inference_on_sample(
    model: object,
    processor: object,
    sample: dict,
    sample_idx: int,
    max_new_tokens: int = 1024,
) -> None:
    """Run inference on a single test sample and print results."""
    messages = format_user_messages(sample["messages"])
    if not messages:
        print(f"  ⚠️ Sample {sample_idx}: Không có user message, bỏ qua.")
        return

    # Trích xuất đường dẫn ảnh
    image_path = None
    for item in messages[0]["content"]:
        if item["type"] == "image":
            image_path = item["image"]
            break

    if not image_path or not os.path.exists(image_path):
        print(f"  ❌ Sample {sample_idx}: Không tìm thấy ảnh: {image_path}")
        return

    print(f"\n{'─' * 60}")
    print(f"📸 Sample {sample_idx}: {os.path.basename(image_path)}")
    print(f"   Path: {image_path}")

    image = Image.open(image_path)

    # Apply chat template – theo chuẩn Unsloth notebook
    input_text = processor.apply_chat_template(
        messages, add_generation_prompt=True
    )
    inputs = processor(
        image,
        input_text,
        add_special_tokens=False,
        return_tensors="pt",
    ).to("cuda")

    input_tokens_count = inputs["input_ids"].shape[1]
    print(f"   📏 Input Tokens: {input_tokens_count}")

    # Reset peak memory stats
    if torch.cuda.is_available():
        torch.cuda.reset_peak_memory_stats()

    print("\n   --- 🟢 KẾT QUẢ TỪ MODEL ---")
    text_streamer = TextStreamer(processor, skip_prompt=True)
    start_gen_time = time.time()

    # Gemma 4 recommended inference settings: temperature=1.0, top_p=0.95, top_k=64
    outputs = model.generate(
        **inputs,
        streamer=text_streamer,
        max_new_tokens=max_new_tokens,
        use_cache=True,
        temperature=1.0,
        top_p=0.95,
        top_k=64,
    )

    gen_duration = time.time() - start_gen_time
    print(f"   {'─' * 40}")

    # Thống kê hiệu suất
    if isinstance(outputs, torch.Tensor):
        generated_tokens = outputs.shape[1] - input_tokens_count
    else:
        generated_tokens = 0

    if generated_tokens > 0:
        tokens_per_sec = generated_tokens / gen_duration
        print(f"   📈 Output Tokens: {generated_tokens}")
        print(f"   ⏱️  Generation Time: {gen_duration:.2f}s")
        print(f"   🚀 Speed: {tokens_per_sec:.2f} tokens/s")
    else:
        print(f"   ⏱️  Generation Time: {gen_duration:.2f}s")

    gen_stats = get_gpu_memory_stats()
    if gen_stats:
        print(f"   💾 Peak VRAM: {gen_stats['max_allocated_gb']} GB")

    # Hiển thị Ground Truth
    print("\n   --- 🎯 GROUND TRUTH ---")
    for msg in sample["messages"]:
        if msg["role"] == "assistant":
            ground_truth = msg["content"]
            # Truncate nếu quá dài
            display_text = ground_truth[:500]
            if len(ground_truth) > 500:
                display_text += "\n   ... (truncated)"
            print(f"   {display_text}")
            break


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Evaluate fine-tuned Gemma 4 Vision (E2B) on test samples"
    )
    parser.add_argument(
        "--model_dir",
        default="gemma4-e2b-finetuned-lora",
        help="Directory containing LoRA adapters",
    )
    parser.add_argument(
        "--data_dir",
        default="data/health_insurance/health_insurance_extracted",
        help="Directory containing oumi_vlm_test.jsonl",
    )
    parser.add_argument(
        "--num_samples",
        type=int,
        default=3,
        help="Number of test samples to evaluate",
    )
    parser.add_argument(
        "--max_new_tokens",
        type=int,
        default=1024,
        help="Maximum number of tokens to generate",
    )
    args = parser.parse_args()

    print("=" * 60)
    print("🚀 Evaluation Gemma 4 Vision (E2B) – Unsloth")
    print("=" * 60)

    if not os.path.exists(args.model_dir):
        print(
            f"❌ LỖI: Không tìm thấy thư mục model '{args.model_dir}'.\n"
            "   Vui lòng chạy 02_train_gemma4.py trước."
        )
        return

    # ------------------------------------------------------------------
    # 1. Pre-load memory stats
    # ------------------------------------------------------------------
    print("\n📊 VRAM trước khi load model:")
    pre_stats = get_gpu_memory_stats()
    if pre_stats:
        print(f"   Allocated: {pre_stats['allocated_gb']} GB")
        print(f"   Reserved:  {pre_stats['reserved_gb']} GB")
    else:
        print("   Không tìm thấy GPU CUDA.")

    # ------------------------------------------------------------------
    # 2. Load Model & Processor
    # ------------------------------------------------------------------
    print(f"\n[1/3] ⏳ Đang tải model từ '{args.model_dir}'...")
    start_load_time = time.time()
    model, processor = FastVisionModel.from_pretrained(
        model_name=args.model_dir,
        load_in_4bit=True,
        device_map="cuda",
    )
    load_time = time.time() - start_load_time
    print(f"✅ Đã tải model trong {load_time:.2f}s")

    # BẮT BUỘC: dùng đúng chat template như lúc train
    processor = get_chat_template(processor, "gemma-4")

    # Bật fast inference (x2 speed)
    print("⚡ Bật chế độ Fast Inference...")
    FastVisionModel.for_inference(model)

    post_load_stats = get_gpu_memory_stats()
    if post_load_stats:
        print(f"\n📊 VRAM sau khi load model:")
        print(f"   Allocated: {post_load_stats['allocated_gb']} GB")
        print(f"   Reserved:  {post_load_stats['reserved_gb']} GB")
        if pre_stats:
            model_size = post_load_stats["allocated_gb"] - pre_stats["allocated_gb"]
            print(f"   Model size: ~{model_size:.3f} GB")

    # ------------------------------------------------------------------
    # 3. Load Test Dataset
    # ------------------------------------------------------------------
    print(f"\n[2/3] 📂 Đang tải dữ liệu test...")
    test_file = os.path.join(args.data_dir, "oumi_vlm_test.jsonl")

    if not os.path.exists(test_file):
        print(f"❌ LỖI: Không tìm thấy file: {test_file}")
        return

    test_examples: list[dict] = []
    with open(test_file, "r", encoding="utf-8") as f:
        for line in f:
            test_examples.append(json.loads(line))

    if not test_examples:
        print("⚠️ CẢNH BÁO: Tập test rỗng.")
        return

    print(f"✅ Đã tải {len(test_examples)} mẫu test.")

    # ------------------------------------------------------------------
    # 4. Run Inference
    # ------------------------------------------------------------------
    num_to_eval = min(args.num_samples, len(test_examples))
    print(f"\n[3/3] 🧠 Chạy Inference trên {num_to_eval} sample(s)...")

    for i in range(num_to_eval):
        run_inference_on_sample(
            model=model,
            processor=processor,
            sample=test_examples[i],
            sample_idx=i + 1,
            max_new_tokens=args.max_new_tokens,
        )

    print(f"\n{'=' * 60}")
    print(f"✅ Hoàn thành evaluation {num_to_eval} sample(s).")
    print("=" * 60)


if __name__ == "__main__":
    main()