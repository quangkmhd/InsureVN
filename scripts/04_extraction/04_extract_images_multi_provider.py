import os
import shutil
import json
import time
import re
import base64
import httpx
from pathlib import Path
import queue
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

# --- CẤU HÌNH ---
INPUT_DIR = "/home/quangnhvn34/dev/me/InsureVN/data/health_insurance/health_insurance_images_table"
OUTPUT_DIR = "/home/quangnhvn34/dev/me/InsureVN/data/health_insurance/health_insurance_extracted"
MAX_RETRIES = 2
MAX_CONCURRENT_WORKERS = 20 # Số luồng song song, tuỳ thuộc vào tổng số key bạn có

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
    text = text.strip()
    if text.startswith("```json"):
        text = text[7:]
    elif text.startswith("```"):
        text = text[3:]
        
    if text.endswith("```"):
        text = text[:-3]
        
    start_idx = text.find("{")
    end_idx = text.rfind("}")
    if start_idx != -1 and end_idx != -1:
        text = text[start_idx:end_idx+1]
        
    return text.strip()

class ApiWorker:
    def __init__(self, provider, api_key, model, endpoint):
        self.provider = provider
        self.api_key = api_key
        self.model = model
        self.endpoint = endpoint
        self.id = f"{provider}-{api_key[:5]}..."

    def process(self, image_path, prompt):
        with open(image_path, "rb") as image_file:
            base64_image = base64.b64encode(image_file.read()).decode('utf-8')
            
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        
        if self.provider == "OLLAMA":
            headers["Authorization"] = f"Bearer {self.api_key}"
            data = {
                "model": self.model,
                "prompt": prompt,
                "images": [base64_image],
                "stream": False,
                "options": {
                    "temperature": 0.0
                }
            }
            with httpx.Client(timeout=1180.0) as client:
                response = client.post(self.endpoint, headers=headers, json=data)
                response.raise_for_status()
                result = response.json()
                return result.get("response", "")
                
        else: # NVIDIA (OpenAI compatible)
            headers["Authorization"] = f"Bearer {self.api_key}"
                
            data = {
                "model": self.model,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{base64_image}"}}
                        ]
                    }
                ],
                "temperature": 0.0,
                "max_tokens": 8096
            }
            with httpx.Client(timeout=1180.0) as client:
                response = client.post(self.endpoint, headers=headers, json=data)
                response.raise_for_status()
                result = response.json()
                return result['choices'][0]['message']['content']

def load_workers():
    workers_list = []
    env_path = Path("/home/quangnhvn34/dev/me/InsureVN/.env")
    
    if not env_path.exists():
        print("❌ Không tìm thấy file .env")
        return []

    # Đọc thủ công file .env để xử lý cả những dòng bị lỗi syntax (thiếu dấu =)
    with open(env_path, "r", encoding="utf-8") as f:
        lines = f.readlines()
        
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        
        if "=" in line:
            k, v = line.split("=", 1)
        else:
            # Xử lý trường hợp "OllAMA_API_Key_3 bc6c1ff9..." bị thiếu dấu =
            parts = line.split(maxsplit=1)
            if len(parts) == 2:
                k, v = parts
            else:
                continue
                
        k = k.strip().upper()
        v = v.strip()
        
        if not v:
            continue
            
        if k.startswith("NVIDIA_NIM_API") or k.startswith("NVIDIA_PAI_KEY"):
            workers_list.append(ApiWorker(
                "NVIDIA", v, 
                "google/gemma-4-31b-it", 
                "https://integrate.api.nvidia.com/v1/chat/completions"
            ))
        elif k.startswith("OLLAMA_API_KEY"):
            ollama_url = os.environ.get("OLLAMA_API_URL", "https://ollama.com") + "/api/generate"
            workers_list.append(ApiWorker(
                "OLLAMA", v, 
                "gemma4:31b-cloud", 
                ollama_url
            ))
            
    print(f"✅ Đã tải thành công {len(workers_list)} API Keys (Workers).")
    for w in workers_list:
        print(f"  - {w.id}")
    return workers_list

def process_single_image(img_path, input_path, output_path, worker_queue, log_file_lock, log_file, progress=None):
    start_time = time.time()
    
    def update_progress():
        if progress is not None:
            with log_file_lock:
                progress['done'] += 1
                return progress['done'], progress['total']
        return 0, 0

    rel_path = img_path.relative_to(input_path)
    expected_json = output_path / rel_path.with_suffix(".json")
    expected_md = output_path / rel_path.with_suffix(".md")
    
    # 1. Bỏ qua nếu đã xử lý
    if expected_json.exists():
        update_progress()
        return "SKIPPED", str(img_path)
        
    filename = img_path.name.lower()
    is_table = filename.startswith("table_")
    prompt = build_prompt(is_table)
    
    for attempt in range(1, MAX_RETRIES + 1):
        # 2. Lấy 1 API Key từ Queue (chờ nếu tất cả đang bận)
        worker = worker_queue.get()
        try:
            raw_text = worker.process(str(img_path), prompt)
            clean_text = clean_json_response(raw_text)
            
            # Kiểm tra parse JSON và sửa lỗi escape nếu có
            try:
                data = json.loads(clean_text)
            except json.JSONDecodeError as json_err:
                if "Invalid \\escape" in str(json_err):
                    # Thay thế các backslash đứng trước ký tự không hợp lệ thành double backslash
                    clean_text = re.sub(r'\\([^"\\/bfnrtu])', r'\\\\\1', clean_text)
                    data = json.loads(clean_text)
                else:
                    raise json_err
            
            # Ghi kết quả
            expected_json.parent.mkdir(parents=True, exist_ok=True)
            with open(expected_json, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
                
            if data.get("markdown"):
                with open(expected_md, "w", encoding="utf-8") as f:
                    f.write(data.get("markdown"))
            
            # Copy ảnh gốc sang cùng vị trí để dễ kiểm tra
            expected_img = output_path / rel_path
            shutil.copy2(img_path, expected_img)
            
            # 3. Thành công, trả worker lại queue để thread khác dùng
            worker_queue.put(worker)
            
            # Ghi log thread-safe
            with log_file_lock:
                has_content = data.get("has_content", False)
                c_type = data.get("content_type", "unknown")
                with open(log_file, "a", encoding="utf-8") as f_log:
                    f_log.write(f"[SUCCESS] {img_path.name} | provider: {worker.provider} | type: {c_type}\n")
            
            exec_time = time.time() - start_time
            done, total = update_progress()
            prefix = f"[{done}/{total}] " if total > 0 else ""
            print(f"✅ {prefix}[Thành công] Đã lưu tại: file://{expected_json.absolute()} (bởi {worker.id} - {exec_time:.1f}s)")
            return "SUCCESS", str(img_path)
            
        except Exception as e:
            error_msg = str(e)
            
            # Trả worker lại vào queue
            worker_queue.put(worker)
            
            if attempt == MAX_RETRIES:
                with log_file_lock:
                    with open(log_file, "a", encoding="utf-8") as f_log:
                        f_log.write(f"[ERROR] {img_path.name} | provider: {worker.id} | Reason: {error_msg}\n")
                exec_time = time.time() - start_time
                done, total = update_progress()
                prefix = f"[{done}/{total}] " if total > 0 else ""
                print(f"❌ {prefix}[Thất bại] {img_path.name} (bởi {worker.id}) - Lỗi: {error_msg} ({exec_time:.1f}s)")
                return "FAILED", str(img_path)
            
            print(f"⚠️ [Retry {attempt}/{MAX_RETRIES}] {img_path.name} - {error_msg}. Đang thử lại...")
            time.sleep(2) # Đợi một xíu trước khi retry (lần retry sẽ lấy key rảnh tiếp theo)

def main():
    print("=== BẮT ĐẦU TRÍCH XUẤT ẢNH ĐA LUỒNG ===")
    
    input_path = Path(INPUT_DIR)
    output_path = Path(OUTPUT_DIR)
    
    if not input_path.exists():
        print(f"❌ Thư mục {INPUT_DIR} không tồn tại!")
        return

    output_path.mkdir(parents=True, exist_ok=True)

    # Lấy danh sách workers (từ .env)
    workers_list = load_workers()
    if not workers_list:
        print("❌ Không có API key nào để chạy. Dừng chương trình.")
        return
        
    # Tạo Thread-safe Queue cho Workers
    worker_queue = queue.Queue()
    for w in workers_list:
        worker_queue.put(w)

    # Tìm tất cả ảnh
    image_files = []
    for ext in ('*.png', '*.jpg', '*.jpeg'):
        image_files.extend(input_path.rglob(ext))
        
    print(f"\n📂 Tìm thấy tổng cộng {len(image_files)} file ảnh cần xử lý.")
    
    log_file = output_path / "extraction_multi_log.txt"
    log_file_lock = threading.Lock()
    
    if not log_file.exists():
        with open(log_file, "w", encoding="utf-8") as f_log:
            f_log.write("=== LOG TRÍCH XUẤT ẢNH (MULTI-PROVIDER) ===\n\n")

    success_count = 0
    fail_count = 0
    skipped_count = 0

    # Chạy đa luồng song song
    num_threads = min(MAX_CONCURRENT_WORKERS, len(workers_list))
    print(f"🚀 Bắt đầu xử lý với {num_threads} luồng song song...\n")
    
    progress_tracker = {"done": 0, "total": len(image_files)}
    
    with ThreadPoolExecutor(max_workers=num_threads) as executor:
        # Submit toàn bộ task
        futures = {
            executor.submit(
                process_single_image, 
                img_path, input_path, output_path, worker_queue, log_file_lock, log_file, progress_tracker
            ): img_path for img_path in image_files
        }
        
        # Nhận kết quả
        for future in as_completed(futures):
            status, path = future.result()
            if status == "SUCCESS":
                success_count += 1
            elif status == "FAILED":
                fail_count += 1
            elif status == "SKIPPED":
                skipped_count += 1

    print(f"\n{'='*40}")
    print(f"🎉 Hoàn tất! Tổng: {len(image_files)}")
    print(f"✅ Thành công: {success_count}")
    print(f"❌ Thất bại: {fail_count}")
    print(f"⏭️ Bỏ qua: {skipped_count}")
    print(f"Kết quả lưu tại: {OUTPUT_DIR}")

if __name__ == "__main__":
    main()
