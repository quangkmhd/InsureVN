import argparse
from oumi.inference import NativeInferenceEngine
from oumi.core.configs import InferenceConfig, ModelParams, GenerationParams

def run_inference(image_path: str, model_dir: str, adapter_dir: str = None):
    # Setup model params
    model_params = ModelParams(
        model_name=model_dir,
        adapter_model=adapter_dir,
        torch_dtype_str="bfloat16",
        trust_remote_code=True,
        attn_implementation="flash_attention_2",
        chat_template="qwen3-vl-instruct"
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
    parser.add_argument("--model", default="Qwen/Qwen3-VL-4B-Instruct", help="Base model")
    parser.add_argument("--adapter", default="./output/qwen3-vl-table-extractor/checkpoint-1000", help="LoRA adapter path")
    args = parser.parse_args()
    
    run_inference(args.image, args.model, args.adapter)