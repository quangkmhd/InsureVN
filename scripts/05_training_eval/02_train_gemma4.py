import argparse
import json
import os

os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True"

import unsloth
from unsloth import FastVisionModel, get_chat_template
from unsloth.trainer import UnslothVisionDataCollator

import torch
from datasets import Dataset
from trl import SFTConfig, SFTTrainer


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def load_jsonl_as_unsloth_dataset(jsonl_path: str) -> list[dict]:
    """Load JSONL file and convert to Unsloth vision conversation format.

    Converts our JSONL schema (image_path / text) into the format
    expected by Unsloth's ``UnslothVisionDataCollator``:
    ``{"type": "image", "image": path}`` and ``{"type": "text", "text": ...}``.
    """
    converted: list[dict] = []
    with open(jsonl_path, "r", encoding="utf-8") as f:
        for line in f:
            data = json.loads(line)
            formatted_messages: list[dict] = []
            for msg in data["messages"]:
                if msg["role"] == "user":
                    new_content: list[dict] = []
                    for item in msg["content"]:
                        if item["type"] == "image_path":
                            # image TRƯỚC text – đúng chuẩn Gemma 4
                            new_content.append(
                                {"type": "image", "image": item["content"]}
                            )
                        elif item["type"] == "text":
                            new_content.append(
                                {"type": "text", "text": item["content"]}
                            )
                    formatted_messages.append(
                        {"role": "user", "content": new_content}
                    )
                elif msg["role"] == "assistant":
                    assistant_text = msg["content"]
                    if isinstance(assistant_text, str):
                        formatted_messages.append(
                            {
                                "role": "assistant",
                                "content": [
                                    {"type": "text", "text": assistant_text}
                                ],
                            }
                        )
                    else:
                        formatted_messages.append(msg)
            converted.append({"messages": formatted_messages})
    return converted


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Fine-tune Gemma 4 Vision (E2B) with Unsloth LoRA"
    )
    parser.add_argument(
        "--data_dir",
        default="data/health_insurance/health_insurance_extracted",
        help="Directory containing oumi_vlm_train.jsonl",
    )
    parser.add_argument(
        "--output_dir",
        default="outputs_gemma4_finetuned",
        help="Directory for training checkpoints",
    )
    parser.add_argument(
        "--save_dir",
        default="gemma4-e2b-finetuned-lora",
        help="Directory to save final LoRA adapters",
    )
    parser.add_argument(
        "--gguf_dir",
        default="",
        help="If set, export merged model to GGUF in this directory",
    )
    parser.add_argument(
        "--gguf_method",
        default="q4_k_m",
        choices=["q4_k_m", "q8_0", "f16"],
        help="GGUF quantization method",
    )
    parser.add_argument(
        "--merged_dir",
        default="",
        help="If set, save merged float16 model to this directory (for vLLM)",
    )
    parser.add_argument(
        "--num_epochs",
        type=int,
        default=2,
        help="Number of training epochs",
    )
    args = parser.parse_args()

    print("=" * 60)
    print("🦥 Fine-tune Gemma 4 Vision (E2B) – Unsloth LoRA")
    print("=" * 60)

    # ------------------------------------------------------------------
    # 1. Load Model & Processor
    # ------------------------------------------------------------------
    print("\n[1/7] Loading model and processor...")
    model, processor = FastVisionModel.from_pretrained(
        "unsloth/gemma-4-E2B-it",
        load_in_4bit=True,                       # 4-bit quantization cho 8GB VRAM
        use_gradient_checkpointing="unsloth",    # Giảm VRAM, tăng context length
        device_map="cuda:0",                     # Direct placement on GPU 0
    )

    # ------------------------------------------------------------------
    # 2. Configure LoRA (theo chuẩn Unsloth Gemma 4 docs)
    # ------------------------------------------------------------------
    print("\n[2/7] Configuring LoRA adapters...")
    model = FastVisionModel.get_peft_model(
        model,
        finetune_vision_layers=True,
        finetune_language_layers=True,
        finetune_attention_modules=True,
        finetune_mlp_modules=True,
        r=32,                                    # Theo file mẫu Unsloth
        lora_alpha=32,                           # Recommended alpha == r
        lora_dropout=0,
        bias="none",
        random_state=3407,
        use_rslora=False,
        loftq_config=None,
        target_modules="all-linear",             # Finetune tất cả các lớp linear
    )

    # Chat template "gemma-4" cho E2B (non-thinking, phù hợp model nhỏ)
    # Dùng "gemma-4-thinking" cho 26B/31B nếu muốn giữ reasoning
    processor = get_chat_template(processor, "gemma-4")

    # ------------------------------------------------------------------
    # 3. Load and Format Dataset
    # ------------------------------------------------------------------
    print("\n[3/7] Loading and formatting dataset...")
    jsonl_file = os.path.join(args.data_dir, "oumi_vlm_train.jsonl")
    converted_dataset = load_jsonl_as_unsloth_dataset(jsonl_file)
    print(f"✅ Loaded {len(converted_dataset)} training examples.")

    # ------------------------------------------------------------------
    # 4. Show pre-training memory stats
    # ------------------------------------------------------------------
    gpu_stats = torch.cuda.get_device_properties(0)
    start_gpu_memory = round(
        torch.cuda.max_memory_reserved() / 1024 / 1024 / 1024, 3
    )
    max_memory = round(gpu_stats.total_memory / 1024 / 1024 / 1024, 3)
    print(f"\n📊 GPU = {gpu_stats.name}. Max memory = {max_memory} GB.")
    print(f"📊 {start_gpu_memory} GB of memory reserved before training.")

    # ------------------------------------------------------------------
    # 5. Configure Trainer (theo đúng notebook mẫu Unsloth)
    # ------------------------------------------------------------------
    print("\n[4/7] Configuring SFT Trainer...")
    trainer = SFTTrainer(
        model=model,
        train_dataset=converted_dataset,
        processing_class=processor.tokenizer,
        data_collator=UnslothVisionDataCollator(model, processor),
        args=SFTConfig(
            per_device_train_batch_size=1,
            gradient_accumulation_steps=4,
            max_grad_norm=0.3,
            warmup_ratio=0.03,
            num_train_epochs=args.num_epochs,
            learning_rate=2e-4,
            logging_steps=1,
            save_strategy="steps",
            save_steps=50,
            optim="adamw_8bit",
            weight_decay=0.001,
            lr_scheduler_type="cosine",
            seed=3407,
            output_dir=args.output_dir,
            report_to="none",
            # BẮT BUỘC cho Vision Finetuning:
            remove_unused_columns=False,
            dataset_text_field="",
            dataset_kwargs={"skip_prepare_dataset": True},
            max_length=2048,
        ),
    )

    # ------------------------------------------------------------------
    # 6. Start Training
    # ------------------------------------------------------------------
    print("\n[5/7] Starting training...")
    print("💡 Lưu ý: Loss 13-15 ban đầu là BÌNH THƯỜNG cho Gemma 4 E2B vision.\n")
    trainer_stats = trainer.train()

    # Post-training memory stats
    used_memory = round(
        torch.cuda.max_memory_reserved() / 1024 / 1024 / 1024, 3
    )
    used_memory_for_lora = round(used_memory - start_gpu_memory, 3)
    used_percentage = round(used_memory / max_memory * 100, 3)
    lora_percentage = round(used_memory_for_lora / max_memory * 100, 3)
    train_runtime = trainer_stats.metrics["train_runtime"]

    print("\n" + "=" * 60)
    print("📈 [THỐNG KÊ] Kết quả Training:")
    print(f"   - Thời gian train: {train_runtime:.1f}s ({train_runtime / 60:.2f} phút)")
    print(f"   - Peak reserved memory: {used_memory} GB")
    print(f"   - Memory cho LoRA training: {used_memory_for_lora} GB")
    print(f"   - Peak memory % of max: {used_percentage}%")
    print(f"   - LoRA memory % of max: {lora_percentage}%")
    print("=" * 60)

    # ------------------------------------------------------------------
    # 7. Save / Export Model
    # ------------------------------------------------------------------
    print("\n[6/7] Saving LoRA adapters...")
    model.save_pretrained(args.save_dir)
    processor.save_pretrained(args.save_dir)
    print(f"✅ LoRA adapters saved to: {args.save_dir}")

    # Optional: Save merged float16 model (cho vLLM deployment)
    if args.merged_dir:
        print(f"\n[7/7] Saving merged float16 model to '{args.merged_dir}'...")
        model.save_pretrained_merged(args.merged_dir, processor)
        print(f"✅ Merged float16 model saved to: {args.merged_dir}")

    # Optional: Export to GGUF (cho llama.cpp / Ollama / Unsloth Studio)
    if args.gguf_dir:
        print(f"\n[7/7] Exporting to GGUF ({args.gguf_method}) -> '{args.gguf_dir}'...")
        model.save_pretrained_gguf(
            args.gguf_dir,
            processor.tokenizer,
            quantization_method=args.gguf_method,
        )
        print(f"✅ GGUF model saved to: {args.gguf_dir}")

    if not args.merged_dir and not args.gguf_dir:
        print("\n[7/7] Bỏ qua export (merged/GGUF). Dùng --merged_dir hoặc --gguf_dir để export.")

    print("\n🎉 Hoàn thành Fine-tuning!")
    print(f"   LoRA adapters: {args.save_dir}/")
    if args.merged_dir:
        print(f"   Merged float16: {args.merged_dir}/")
    if args.gguf_dir:
        print(f"   GGUF ({args.gguf_method}): {args.gguf_dir}/")


if __name__ == "__main__":
    main()
