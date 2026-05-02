import os
import glob
import json
import time
import re
from pathlib import Path
from dotenv import load_dotenv
from ollama import Client

# Load environment variables from .env file
load_dotenv()

OLLAMA_API_URL = os.environ.get("OLLAMA_API_URL", "https://ollama.com")
OLLAMA_MODEL = "gemma4:31b-cloud"
API_KEY = os.environ.get("API_KEY") or os.environ.get("OllAMA_API_Key_1")

if not API_KEY:
    print("[Error] API_KEY not found in .env file.")
    exit(1)

# Initialize Ollama client
client = Client(
    host=OLLAMA_API_URL,
    headers={'Authorization': f'Bearer {API_KEY}'}
)

def build_prompt(is_table=True):
    base_instruction = """
You are an expert data extractor and OCR system analyzing images of Vietnamese insurance documents.
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
}
"""
    if is_table:
        base_instruction += "\nPay special attention to extracting the table accurately into BOTH 'markdown' and 'structured_data'."
    else:
        base_instruction += "\nThis image might not be a table. Focus on reading text into 'markdown' and providing a good 'description'."
        
    return base_instruction.strip()

def clean_json_response(text: str) -> str:
    """Xóa bỏ các thẻ markdown thừa có thể có do LLM tự thêm vào."""
    text = text.strip()
    if text.startswith("```json"):
        text = text[7:]
    elif text.startswith("```"):
        text = text[3:]
        
    if text.endswith("```"):
        text = text[:-3]
        
    # Đôi khi có text thừa trước/sau ngoặc
    start_idx = text.find("{")
    end_idx = text.rfind("}")
    if start_idx != -1 and end_idx != -1:
        text = text[start_idx:end_idx+1]
        
    return text.strip()

def process_image_with_retry(image_path: str, max_retries=3):
    """
    Gọi LLM và thử parse JSON, retry tối đa max_retries lần nếu lỗi.
    """
    filename = Path(image_path).name.lower()
    is_table = filename.startswith("table_")
    prompt = build_prompt(is_table)
    
    for attempt in range(1, max_retries + 1):
        try:
            print(f"  [Lần {attempt}] Gửi request cho: {filename} ...")
            response = client.generate(
                model=OLLAMA_MODEL,
                prompt=prompt,
                images=[image_path],
                stream=False,
                options={
                    "temperature": 0.0,
                }
            )
            
            raw_text = response.get('response', '')
            clean_text = clean_json_response(raw_text)
            
            try:
                data = json.loads(clean_text)
                print(f"  [Thành công] Đã parse JSON hợp lệ.")
                return data, None
            except json.JSONDecodeError as json_err:
                error_msg = f"Lỗi parse JSON: {json_err}"
                print(f"  [Lỗi] {error_msg}")
                if attempt == max_retries:
                    return None, f"{error_msg}. Raw output: {raw_text[:100]}..."
                
        except Exception as api_err:
            error_msg = f"Lỗi gọi API: {api_err}"
            print(f"  [Lỗi] {error_msg}")
            if attempt == max_retries:
                return None, error_msg
            time.sleep(2) # Đợi 2s trước khi thử lại
            
    return None, "Đã thử tối đa số lần nhưng vẫn thất bại."

def main():
    input_dir = "/home/quangnhvn34/dev/me/InsureVN/data/health_insurance/health_insurance_images_table"
    output_dir = "/home/quangnhvn34/dev/me/InsureVN/data/health_insurance/health_insurance_extracted"
    
    input_path = Path(input_dir)
    output_path = Path(output_dir)
    
    if not input_path.exists():
        print(f"Thư mục {input_dir} không tồn tại!")
        return

    output_path.mkdir(parents=True, exist_ok=True)

    # Tìm tất cả ảnh (.png, .jpg, .jpeg) trong thư mục và các thư mục con
    image_extensions = ('*.png', '*.jpg', '*.jpeg')
    image_files = []
    for ext in image_extensions:
        image_files.extend(input_path.rglob(ext))
        
    print(f"Tìm thấy tổng cộng {len(image_files)} file ảnh.")
    
    log_file = output_path / "extraction_log.txt"
    
    if not log_file.exists():
        with open(log_file, "w", encoding="utf-8") as f_log:
            f_log.write("=== LOG TRÍCH XUẤT ẢNH ===\n\n")

    success_count = 0
    fail_count = 0
    skipped_count = 0
    
    for img_path in image_files:
        # Tính toán đường dẫn đích trong output_dir
        rel_path = img_path.relative_to(input_path)
        expected_json = output_path / rel_path.with_suffix(".json")
        expected_md = output_path / rel_path.with_suffix(".md")
        
        if expected_json.exists():
            print(f"  [Bỏ qua] {img_path.name} đã tồn tại trong thư mục đích.")
            skipped_count += 1
            continue

        print(f"\nĐang xử lý: {img_path}")
        
        data, error = process_image_with_retry(str(img_path))
        
        if data:
            success_count += 1
            # Tạo thư mục con nếu chưa có
            expected_json.parent.mkdir(parents=True, exist_ok=True)
            
            # Ghi kết quả ra file
            with open(expected_json, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
                
            # Ghi markdown ra file riêng cho dễ nhìn
            if data.get("markdown"):
                with open(expected_md, "w", encoding="utf-8") as f:
                    f.write(data.get("markdown"))
            
            # Log
            has_content = data.get("has_content", False)
            c_type = data.get("content_type", "unknown")
            with open(log_file, "a", encoding="utf-8") as f_log:
                f_log.write(f"[SUCCESS] {img_path} | has_content: {has_content} | type: {c_type}\n")
        else:
            fail_count += 1
            print(f"  [Thất bại] Không thể trích xuất {img_path.name}")
            with open(log_file, "a", encoding="utf-8") as f_log:
                f_log.write(f"[ERROR] {img_path} | Reason: {error}\n")

    print(f"\n{'='*40}")
    print(f"Hoàn tất! Tổng: {len(image_files)}, Thành công: {success_count}, Thất bại: {fail_count}, Bỏ qua: {skipped_count}")
    print(f"Kết quả lưu tại: {output_dir}")
    print(f"Xem chi tiết tại: {log_file}")

if __name__ == "__main__":
    main()
