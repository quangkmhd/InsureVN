import os
import json
from pathlib import Path
import random

def process_dataset(input_dir: str, output_dir: str, train_ratio: float = 0.9):
    """Converts image/json pairs into Oumi JSONL conversational dataset with train/test splits."""
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
                
        # Use the full JSON object as the assistant's target output
        assistant_output = json.dumps(data, ensure_ascii=False, indent=2)
        

        # Oumi Conversational Format (using "image_path" or "image_url" per documentation)
        record = {
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "image_path", "content": str(img_path.absolute())},
                        {"type": "text", "content": """You are an expert data extractor and OCR system analyzing images of Vietnamese insurance documents.
Your task is to extract information and return EXACTLY a valid JSON object. Do not include Markdown blocks (like ```json), commentary, or any text outside of the JSON structure.

The JSON MUST conform to this exact schema:
{
  "has_content": true if the image contains readable text, tables, or useful info. false if it's blank or just a decoration/logo.
  "content_type": "table" (if it contains tabular data), "text" (if mostly paragraphs), "image_only" (if it's a diagram/picture without much text), or "mixed".
  "markdown": "A full Markdown string representing the extracted text or table. Preserve columns/rows using Markdown table syntax if a table exists. Use Vietnamese properly.",
  "structured_data": [
    // IF it's a table, return an array of JSON objects here. Keys should be column headers exactly as they appear in the image, values are the cell data.
    // IF NOT a table, return an empty array [].
  ],
  "description": "A short vietnamese summary of what this image shows."
}"""}
                    ]
                },
                {
                    "role": "assistant",
                    "content": assistant_output
                }
            ]
        }
        dataset.append(record)
        
    # Shuffle and Split
    random.seed(42)
    random.shuffle(dataset)
    split_idx = int(len(dataset) * train_ratio)
    train_data = dataset[:split_idx]
    test_data = dataset[split_idx:]
    
    # Setup output paths
    out_dir_path = Path(output_dir)
    out_dir_path.mkdir(parents=True, exist_ok=True)
    
    train_file = out_dir_path / "oumi_vlm_train.jsonl"
    test_file = out_dir_path / "oumi_vlm_test.jsonl"
    
    # Write Train JSONL
    with open(train_file, 'w', encoding='utf-8') as f:
        for record in train_data:
            f.write(json.dumps(record, ensure_ascii=False) + '\n')
            
    # Write Test JSONL
    with open(test_file, 'w', encoding='utf-8') as f:
        for record in test_data:
            f.write(json.dumps(record, ensure_ascii=False) + '\n')
            
    print(f"Generated {len(train_data)} train samples -> {train_file}")
    print(f"Generated {len(test_data)} test samples -> {test_file}")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="data/health_insurance/health_insurance_extracted", help="Input directory")
    parser.add_argument("--output", default="data/health_insurance/health_insurance_extracted", help="Output directory for the jsonl files")
    parser.add_argument("--train_ratio", type=float, default=0.9, help="Ratio of data to use for training (0.0 to 1.0)")
    args = parser.parse_args()
    process_dataset(args.input, args.output, args.train_ratio)
