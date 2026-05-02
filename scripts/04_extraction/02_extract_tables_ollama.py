import os
import glob
import json
import base64
from pathlib import Path
from dotenv import load_dotenv
from ollama import Client

# Load environment variables from .env file
load_dotenv()

OLLAMA_API_URL = os.environ.get("OLLAMA_API_URL", "http://localhost:11434")
OLLAMA_MODEL = "gemma4:31b-cloud"
API_KEY = os.environ.get("API_KEY")

if not API_KEY:
    print("[Error] API_KEY not found in .env file.")
    exit(1)

# Initialize Ollama client
client = Client(
    host=OLLAMA_API_URL,
    headers={'Authorization': f'Bearer {API_KEY}'}
)

def extract_table_from_image(image_path: str):
    """
    Sử dụng Ollama Vision model để trích xuất bảng từ ảnh và chuyển thành Markdown Table + JSON.
    """
    prompt = """
You are an expert data extractor. The provided image contains a table with information and prices.
Your task is to extract all the text and output it in exactly two formats:

1. A Markdown table that preserves the exact format, columns, and rows of the table in the image.
2. A JSON array of objects representing the rows in the table. Each object should have keys corresponding to the column headers.

Please structure your response exactly as follows without any extra explanation:
[MARKDOWN TABLE]
<your markdown table here>

[JSON]
```json
<your JSON here>
```
"""

    print(f"\nĐang xử lý ảnh: {image_path}")
    
    try:
        # Trong Ollama python client, ta có thể truyền đường dẫn ảnh hoặc bytes vào list images
        response = client.generate(
            model=OLLAMA_MODEL,
            prompt=prompt,
            images=[image_path],
            stream=False,
            options={
                "temperature": 0.0,
            }
        )
        
        response_text = response.get('response', '').strip()
        return response_text
    
    except Exception as e:
        print(f"[Error] Lỗi khi gọi Ollama API cho ảnh {image_path}: {e}")
        return None

def process_all_images(input_dir: str, output_dir: str):
    """
    Đọc tất cả ảnh trong thư mục và xử lý từng ảnh.
    """
    input_path = Path(input_dir)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    # Lấy tất cả ảnh (png, jpg, jpeg)
    image_files = []
    for ext in ["*.png", "*.jpg", "*.jpeg"]:
        image_files.extend(input_path.glob(ext))
        
    if not image_files:
        print(f"Không tìm thấy ảnh nào trong thư mục {input_dir}")
        return

    for img_file in image_files:
        result = extract_table_from_image(str(img_file))
        
        if result:
            # Lưu kết quả ra file txt cùng tên với ảnh
            out_file = output_path / f"{img_file.stem}_extracted.txt"
            with open(out_file, "w", encoding="utf-8") as f:
                f.write(result)
            print(f"-> Đã lưu kết quả tại: {out_file}")

if __name__ == "__main__":
    # Thư mục chứa ảnh đầu vào và thư mục lưu kết quả đầu ra
    INPUT_DIR = "data/images"
    OUTPUT_DIR = "data/extracted_tables"
    
    # Tạo thư mục input nếu chưa có để người dùng bỏ ảnh vào
    Path(INPUT_DIR).mkdir(parents=True, exist_ok=True)
    
    process_all_images(INPUT_DIR, OUTPUT_DIR)
