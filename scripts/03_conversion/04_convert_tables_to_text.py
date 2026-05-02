import os
import re
import time
import httpx
from pathlib import Path
import queue
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
import logging

# Định nghĩa các thư mục đầu vào và đầu ra
INPUT_DIR = Path("/home/quangnhvn34/dev/me/InsureVN/data/health_insurance/health_insurance_markdowns")
OUTPUT_DIR = Path("/home/quangnhvn34/dev/me/InsureVN/data/health_insurance/health_insurance_markdowns_interpreted")

MAX_RETRIES = 2
MAX_CONCURRENT_WORKERS = 20
MARKER = "**Diễn giải dữ liệu:**"

# Thiết lập logging
LOG_FILE = OUTPUT_DIR / "table_to_text_conversion_log.txt"
# Đảm bảo folder log tồn tại
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, mode='a', encoding='utf-8'),
        logging.StreamHandler()
    ]
)

class ApiWorker:
    def __init__(self, provider, api_key, model, endpoint):
        self.provider = provider
        self.api_key = api_key
        self.model = model
        self.endpoint = endpoint
        self.id = f"{provider}-{api_key[:5]}..."

    def process(self, prompt):
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        
        if self.provider == "OLLAMA":
            headers["Authorization"] = f"Bearer {self.api_key}"
            data = {
                "model": self.model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.0
                }
            }
            with httpx.Client(timeout=120.0) as client:
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
                        "content": prompt
                    }
                ],
                "temperature": 0.0,
                "max_tokens": 4096
            }
            with httpx.Client(timeout=120.0) as client:
                response = client.post(self.endpoint, headers=headers, json=data)
                response.raise_for_status()
                result = response.json()
                return result['choices'][0]['message']['content']

def load_workers():
    workers_list = []
    env_path = Path("/home/quangnhvn34/dev/me/InsureVN/.env")
    
    if not env_path.exists():
        logging.error("❌ Không tìm thấy file .env")
        return []

    with open(env_path, "r", encoding="utf-8") as f:
        lines = f.readlines()
        
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        
        if "=" in line:
            k, v = line.split("=", 1)
        else:
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
            
    logging.info(f"✅ Đã tải thành công {len(workers_list)} API Keys (Workers).")
    for w in workers_list:
        logging.info(f"  - {w.id}")
    return workers_list

def strip_previous_interpretations(content: str) -> str:
    """Xóa tất cả nội dung diễn giải AI từ các lần chạy trước (bao gồm cả text rác có chứa |).

    Pattern: Tìm MARKER, xóa từ MARKER đến khi gặp dòng trống kép hoặc
    markdown heading hoặc bảng mới.
    """
    # Xóa từ MARKER đến khi gặp: dòng bắt đầu bằng # hoặc | hoặc hết file
    pattern = re.escape(MARKER) + r".*?(?=\n(?:#{1,6}\s|\|)|$)"
    content = re.sub(pattern, "", content, flags=re.DOTALL)
    # Dọn dẹp nhiều dòng trống liên tiếp (trên 2) thành 2
    content = re.sub(r"\n{3,}", "\n\n", content)
    return content


def _is_table_row(line: str) -> bool:
    """Kiểm tra xem dòng có phải là hàng của bảng markdown không.

    Một hàng bảng hợp lệ phải bắt đầu bằng | (bỏ qua khoảng trắng đầu dòng).
    """
    stripped = line.strip()
    return stripped.startswith("|")


def extract_markdown_tables(content: str) -> list[tuple[int, int, str]]:
    """Tìm tất cả các khối bảng bằng cách duyệt từng dòng.

    Trả về danh sách (start_char, end_char, table_text).
    Một khối bảng = chuỗi liên tiếp các dòng bắt đầu bằng |.
    """
    lines = content.split("\n")
    tables: list[tuple[int, int, str]] = []
    char_pos = 0
    block_start = -1
    block_lines: list[str] = []

    for i, line in enumerate(lines):
        if _is_table_row(line):
            if block_start == -1:
                block_start = char_pos
            block_lines.append(line)
        else:
            if block_lines:
                # Kết thúc khối bảng — chỉ ghi nhận nếu có >= 2 dòng (header + separator)
                if len(block_lines) >= 2:
                    block_text = "\n".join(block_lines)
                    block_end = char_pos  # char_pos đang ở đầu dòng hiện tại (dòng KHÔNG phải bảng)
                    tables.append((block_start, block_end, block_text))
                block_start = -1
                block_lines = []
        # +1 cho ký tự \n
        char_pos += len(line) + 1

    # Xử lý bảng ở cuối file
    if block_lines and len(block_lines) >= 2:
        block_text = "\n".join(block_lines)
        tables.append((block_start, char_pos - 1, block_text))

    return tables


def process_file(input_path: Path, output_path: Path, worker_queue: queue.Queue, progress: dict, lock: threading.Lock):
    """Xử lý một file: đọc source gốc, xóa AI cũ, trích xuất bảng, gọi AI, ghi output.
    Hỗ trợ granular resume: bỏ qua các bảng đã có diễn giải trong file output cũ.
    """
    # LUÔN đọc từ input_path (source gốc) để tránh tích lũy lỗi từ output cũ
    content = input_path.read_text(encoding="utf-8")

    # Bước 0: Xóa tất cả diễn giải AI từ các lần chạy trước (nếu source bị corrupted)
    content = strip_previous_interpretations(content)

    table_matches = extract_markdown_tables(content)
    if not table_matches:
        if not output_path.exists():
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(content, encoding="utf-8")
        with lock:
            progress['files_done'] += 1
        logging.info(f"⏭️  Bỏ qua file: {input_path.name} (Không có bảng dữ liệu)")
        return "SKIPPED_NO_TABLE", str(input_path)

    # Đọc nội dung file output cũ để thực hiện granular resume
    existing_output = ""
    if output_path.exists():
        existing_output = output_path.read_text(encoding="utf-8")
        marker_count = existing_output.count(MARKER)
        # Fast path: nếu đã đủ hết các bảng thì skip cả file
        if marker_count >= len(table_matches):
            with lock:
                progress['files_done'] += 1
                progress['tables_done'] += len(table_matches)
            logging.info(f"⏭️  Bỏ qua file: {input_path.name} (Đã hoàn thành toàn bộ)")
            return "SKIPPED_ALREADY_DONE", str(input_path)

    new_content_parts = []
    current_pos = 0
    last_output_pos = 0
    modified = False

    for idx, (start, end, table) in enumerate(table_matches):
        # Thêm đoạn văn bản từ vị trí hiện tại đến hết bảng này
        new_content_parts.append(content[current_pos:end])
        current_pos = end

        # Tìm xem bảng này đã có diễn giải trong file output cũ chưa
        existing_desc = None
        if existing_output:
            # Tìm bảng trong file output cũ (bắt đầu từ vị trí sau bảng trước đó để tránh trùng lặp)
            table_pos_in_output = existing_output.find(table, last_output_pos)
            if table_pos_in_output != -1:
                # Tìm MARKER ngay sau bảng này (trong khoảng 500 ký tự)
                search_start = table_pos_in_output + len(table)
                marker_match = re.search(re.escape(MARKER), existing_output[search_start : search_start + 500])
                if marker_match:
                    marker_pos = search_start + marker_match.start()
                    # Kiểm tra xem giữa bảng và marker có text lạ không (chỉ chấp nhận whitespace)
                    between = existing_output[search_start : marker_pos].strip()
                    if not between:
                        # Trích xuất nội dung diễn giải (đến heading hoặc bảng tiếp theo)
                        desc_start = marker_pos + len(MARKER)
                        end_match = re.search(r"\n(?:#{1,6}\s|\|)|$", existing_output[desc_start:], re.MULTILINE)
                        if end_match:
                            existing_desc = existing_output[desc_start : desc_start + end_match.start()].strip()
                            last_output_pos = desc_start + end_match.start()

        if existing_desc:
            logging.info(f"⏭️  Bỏ qua bảng {idx + 1}/{len(table_matches)} trong {input_path.name} (Đã có diễn giải)")
            new_content_parts.append(f"\n\n{MARKER}\n{existing_desc}\n")
            with lock:
                progress['tables_done'] += 1
            continue

        # Nếu không có diễn giải cũ, gọi AI
        prompt = f"""Dưới đây là một bảng dữ liệu từ tài liệu bảo hiểm. 
Hãy chuyển đổi dữ liệu trong bảng này thành một đoạn văn xuôi (diễn giải) chi tiết và đầy đủ.

Yêu cầu:
1. Không bỏ sót bất kỳ thông tin nào.
2. Sử dụng câu văn trôi chảy, chuyên nghiệp, dễ hiểu cho khách hàng.
3. Nếu bảng có nhiều chương trình bảo hiểm, hãy diễn giải rõ sự khác biệt giữa chúng.
4. Tuyệt đối không tự ý thêm bớt thông tin ngoài bảng.
5. Quan trọng: Chỉ trả về đoạn văn diễn giải thuần túy dưới dạng văn xuôi. Tuyệt đối KHÔNG được bao gồm các ký tự kẻ bảng (như dấu gạch đứng |), không được lặp lại các hàng của bảng ở định dạng thô, định dạng Markdown hoặc danh sách các con số rời rạc ở cuối đoạn văn.

Bảng dữ liệu cần xử lý:
{table}

Hãy viết đoạn diễn giải:"""

        success = False
        for attempt in range(1, MAX_RETRIES + 1):
            worker = worker_queue.get()
            try:
                logging.info(f"⏳ Đang xử lý bảng {idx + 1}/{len(table_matches)} trong {input_path.name} (Lần thử {attempt}/{MAX_RETRIES})")
                description = worker.process(prompt)

                if not description or len(description.strip()) < 10:
                    raise ValueError("Kết quả từ AI quá ngắn hoặc trống rỗng")

                description = description.strip()
                new_content_parts.append(f"\n\n{MARKER}\n{description}\n")

                modified = True
                success = True

                with lock:
                    progress['tables_done'] += 1
                logging.info(f"✅ Thành công bảng {idx + 1}/{len(table_matches)} -> {output_path.name}")

                worker_queue.put(worker)
                break
            except Exception as e:
                worker_queue.put(worker)
                if attempt == MAX_RETRIES:
                    logging.error(f"❌ Lỗi bảng {idx + 1} trong {input_path.name}: {e}")
                else:
                    time.sleep(2)

        if not success:
            with lock:
                progress['tables_failed'] += 1

    # Ghi kết quả vào output directory
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(content, encoding="utf-8")

    with lock:
        progress['files_done'] += 1
        if modified:
            logging.info(f"💾 Đã hoàn tất: {output_path} ({progress['files_done']}/{progress['total_files']} files)")

    return "SUCCESS" if modified else "SKIPPED_ALREADY_DONE", str(input_path)

def main():
    logging.info("=== BẮT ĐẦU CHUYỂN ĐỔI BẢNG (LƯU VÀO THƯ MỤC RIÊNG) ===")
    
    if not INPUT_DIR.exists():
        logging.error(f"❌ Thư mục đầu vào {INPUT_DIR} không tồn tại!")
        return

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    logging.info(f"📁 Thư mục gốc: {INPUT_DIR}")
    logging.info(f"📁 Thư mục đích: {OUTPUT_DIR}")

    workers_list = load_workers()
    if not workers_list:
        logging.error("❌ Không có API key nào để chạy. Dừng chương trình.")
        return

    md_files = list(INPUT_DIR.rglob("*.md"))
    if not md_files:
        logging.warning("Không tìm thấy file .md nào.")
        return

    # Khởi tạo queue chứa các worker
    worker_queue = queue.Queue()
    for worker in workers_list:
        worker_queue.put(worker)

    progress = {
        'total_files': len(md_files),
        'files_done': 0,
        'tables_done': 0,
        'tables_failed': 0
    }
    lock = threading.Lock()

    logging.info(f"🚀 Bắt đầu xử lý {len(md_files)} file với tối đa {MAX_CONCURRENT_WORKERS} luồng...")

    start_time = time.time()
    results = []
    
    with ThreadPoolExecutor(max_workers=MAX_CONCURRENT_WORKERS) as executor:
        futures = []
        for input_file in md_files:
            # Tính toán đường dẫn file đích tương ứng
            relative_path = input_file.relative_to(INPUT_DIR)
            output_file = OUTPUT_DIR / relative_path
            
            futures.append(executor.submit(process_file, input_file, output_file, worker_queue, progress, lock))
            
        for future in as_completed(futures):
            try:
                status, path = future.result()
                results.append((status, path))
            except Exception as e:
                logging.error(f"❌ Lỗi hệ thống khi xử lý luồng: {e}")

    end_time = time.time()
    duration = end_time - start_time

    logging.info("="*50)
    logging.info("=== HOÀN TẤT QUÁ TRÌNH CHUYỂN ĐỔI ===")
    logging.info(f"⏱️ Tổng thời gian: {duration:.2f} giây")
    logging.info(f"📁 Kết quả được lưu tại: {OUTPUT_DIR}")
    logging.info(f"📄 Tổng số file đã quét: {progress['total_files']}")
    logging.info(f"📄 Số file đã xử lý xong: {progress['files_done']}")
    logging.info(f"📊 Tổng số bảng đã diễn giải: {progress['tables_done']}")
    if progress['tables_failed'] > 0:
        logging.warning(f"⚠️ Số bảng bị lỗi: {progress['tables_failed']}")
    logging.info("="*50)

if __name__ == "__main__":
    main()
