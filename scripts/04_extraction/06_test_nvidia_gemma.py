import httpx
import json
import base64
import os
from dotenv import load_dotenv

def encode_image(image_path):
    """Đọc ảnh và chuyển sang base64"""
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')

def test_nvidia_gemma():
    # Tải biến môi trường từ file .env
    load_dotenv()
    
    # Lấy API key, hỗ trợ tên biến từ .env mà bạn đang dùng (NVIDIA_PAI_KEY_1)
    api_key = os.getenv("NVIDIA_PAI_KEY_1") or os.getenv("NVIDIA_API_KEY")
    if not api_key:
        print(
            "❌ Thiếu NVIDIA API key. Hãy cấu hình NVIDIA_PAI_KEY_1 "
            "hoặc NVIDIA_API_KEY trong .env."
        )
        return

    model = "google/gemma-4-31b-it" 
    url = "https://integrate.api.nvidia.com/v1/chat/completions"

    # Đường dẫn ảnh gốc
    image_path = "/home/quangnhvn34/dev/me/InsureVN/data/health_insurance/health_insurance_images_table/aia.com.vn/2601-TCB-BH-SucKhoeTronDoi-brochure.pdf.coredownload.inline/table_p6_n1.png"
    
    if not os.path.exists(image_path):
        print(f"❌ Không tìm thấy ảnh tại: {image_path}")
        return

    print(f"--- Đang mã hóa ảnh: {os.path.basename(image_path)} ---")
    base64_image = encode_image(image_path)

    # Cấu hình header cho Nvidia API (OpenAI-compatible)
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }

    prompt = """You are an expert data extractor and OCR system analyzing images of Vietnamese insurance documents.
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
}"""

    # Payload chuẩn format OpenAI API
    data = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": prompt
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/png;base64,{base64_image}"
                        }
                    }
                ]
            }
        ],
        "max_tokens": 4096,
        "temperature": 0.2
    }

    print(f"--- Đang gửi yêu cầu tới model: {model} qua Nvidia NIM ---")
    
    try:
        # Tăng timeout cho các tác vụ vision
        with httpx.Client(timeout=180.0) as client:
            response = client.post(url, headers=headers, content=json.dumps(data))
            
            if response.status_code == 200:
                result = response.json()
                content = result['choices'][0]['message']['content']
                print("\n✅ Kết nối thành công!")
                print(f"🤖 Phản hồi:\n{content}")

                # Lưu kết quả vào file
                try:
                    # Làm sạch content nếu model trả về có kèm markdown code block
                    json_str = content.strip()
                    if json_str.startswith("```json"):
                        json_str = json_str[7:]
                    elif json_str.startswith("```"):
                        json_str = json_str[3:]
                    if json_str.endswith("```"):
                        json_str = json_str[:-3]
                    json_str = json_str.strip()

                    parsed_json = json.loads(json_str)
                    output_file = "data/processed/nvidia_vision_test_output.json"
                    os.makedirs(os.path.dirname(output_file), exist_ok=True)
                    
                    with open(output_file, "w", encoding="utf-8") as f:
                        json.dump(parsed_json, f, ensure_ascii=False, indent=2)
                    
                    print(f"\n💾 Đã lưu output vào: {output_file}")
                except Exception as save_error:
                    print(f"\n⚠️ Lỗi khi lưu file: {str(save_error)}")
            else:
                print(f"\n❌ Lỗi HTTP: {response.status_code}")
                print(f"Chi tiết: {response.text}")
                
    except Exception as e:
        print(f"\n❌ Đã xảy ra lỗi: {str(e)}")

if __name__ == "__main__":
    test_nvidia_gemma()
