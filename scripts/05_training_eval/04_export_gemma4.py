import unsloth
from unsloth import FastVisionModel

import argparse
import os


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Export fine-tuned Gemma 4 Vision (E2B) LoRA adapters to GGUF format"
    )
    parser.add_argument(
        "--model_dir",
        default="gemma4-e2b-finetuned-lora",
        help="Directory containing LoRA adapters (adapter_model.safetensors, etc.)",
    )
    parser.add_argument(
        "--gguf_dir",
        default="gemma4-gguf",
        help="Directory to save the exported GGUF model",
    )
    parser.add_argument(
        "--gguf_method",
        default="q4_k_m",
        choices=["q4_k_m", "q8_0", "f16"],
        help="GGUF quantization method",
    )
    args = parser.parse_args()

    print("=" * 60)
    print("🦥 Export Gemma 4 Vision (E2B) to GGUF – Unsloth")
    print("=" * 60)

    if not os.path.exists(args.model_dir):
        print(
            f"❌ LỖI: Không tìm thấy thư mục model '{args.model_dir}'.\n"
            "   Vui lòng đảm bảo bạn đã copy folder adapter từ Colab về."
        )
        return

    # 1. Load Model & Processor
    # Lưu ý: FastVisionModel.from_pretrained sẽ tự động load model gốc + adapter từ model_dir
    print(f"\n[1/2] ⏳ Đang tải model và adapter từ '{args.model_dir}'...")
    model, processor = FastVisionModel.from_pretrained(
        model_name=args.model_dir,
        load_in_4bit=True,
        device_map="cuda",
    )

    # 2. Export to GGUF
    print(f"\n[2/2] 🚀 Đang export sang GGUF ({args.gguf_method}) -> '{args.gguf_dir}'...")
    print("💡 Quá trình này có thể mất vài phút và cần RAM/VRAM để merge...")

    try:
        model.save_pretrained_gguf(
            args.gguf_dir,
            processor.tokenizer,
            quantization_method=args.gguf_method,
        )
        print(f"\n✅ Xuất GGUF thành công tại: {args.gguf_dir}")
        print(f"   File GGUF chính: {args.gguf_dir}/unsloth.{args.gguf_method.upper()}.gguf")
    except Exception as e:
        print(f"\n❌ LỖI trong quá trình export: {e}")
        print("💡 Gợi ý: Kiểm tra xem bạn có đủ dung lượng đĩa và RAM không.")

    print("\n" + "=" * 60)
    print("🎉 Hoàn thành!")


if __name__ == "__main__":
    main()
