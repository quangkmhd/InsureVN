import os
import shutil
import json
import time
import argparse
import httpx
from pathlib import Path
from typing import List
from dotenv import load_dotenv
import queue
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

# Add specific imports needed if any
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class ApiWorker:
    def __init__(self, provider, api_key, model, endpoint):
        self.provider = provider
        self.api_key = api_key
        self.model = model
        self.endpoint = endpoint
        self.id = f"{provider}-{api_key[:5] if api_key else 'None'}..."

    def process(self, file_path: Path) -> int:
        try:
            content = file_path.read_text(encoding='utf-8')
        except Exception as e:
            logging.error(f"Failed to read {file_path.name}: {e}")
            return -1

        prompt = (
            "Analyze the following JSON content extracted from a health insurance document. "
            "Classify it as 1 (good content/information for a SQL database) or 0 (trash/no need content). "
            "Return ONLY a JSON object with a single key 'classification' and an integer value of 1 or 0. "
            "Example: {\"classification\": 1}\n\n"
            f"Content:\n{content}"
        )

        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json"
        }

        if self.provider == "OLLAMA":
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"
            data = {
                "model": self.model,
                "prompt": prompt,
                "stream": False,
                "format": "json",
                "options": {
                    "temperature": 0.0
                }
            }
            with httpx.Client(timeout=1120.0) as client:
                response = client.post(self.endpoint, headers=headers, json=data)
                response.raise_for_status()
                result = response.json()
                response_text = result.get("response", "")
                
        else: # NVIDIA
            headers["Authorization"] = f"Bearer {self.api_key}"
            data = {
                "model": self.model,
                "messages": [
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.0,
                "max_tokens": 1024
            }
            with httpx.Client(timeout=120.0) as client:
                response = client.post(self.endpoint, headers=headers, json=data)
                response.raise_for_status()
                result = response.json()
                response_text = result['choices'][0]['message']['content']

        # Parse response_text
        try:
            # Clean text if it has markdown blocks
            text = response_text.strip()
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
                
            parsed = json.loads(text.strip())
            if "classification" in parsed and parsed["classification"] in [0, 1]:
                return parsed["classification"]
        except json.JSONDecodeError:
            pass
            
        logging.warning(f"Could not parse valid classification from response: {response_text}")
        return -1


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
                "gemma4:31b-cloud", # adjust if needed
                ollama_url
            ))
            
    # Also support local ollama if no keys provided or explicitly requested
    if not workers_list and os.environ.get("USE_LOCAL_OLLAMA") == "true":
        workers_list.append(ApiWorker(
            "OLLAMA", "", 
            "gemma4", 
            "http://localhost:11434/api/generate"
        ))

    logging.info(f"✅ Đã tải thành công {len(workers_list)} API Keys (Workers).")
    for w in workers_list:
        logging.info(f"  - {w.id}")
    return workers_list

def get_unprocessed_files(input_dir: Path, good_dir: Path, trash_dir: Path) -> List[Path]:
    """Finds all JSON files in input_dir that don't exist in good_dir or trash_dir (preserving subdirs)."""
    unprocessed = []
    if not input_dir.exists():
        return []

    for file_path in input_dir.rglob("*.json"):
        try:
            rel_path = file_path.relative_to(input_dir)
            good_file = good_dir / rel_path
            trash_file = trash_dir / rel_path

            if not good_file.exists() and not trash_file.exists():
                unprocessed.append(file_path)
        except ValueError:
            continue

    return unprocessed

def process_single_file(
    file_path: Path,
    input_dir: Path,
    good_dir: Path,
    trash_dir: Path,
    worker_queue: queue.Queue,
    dry_run: bool,
) -> str:
    """Processes a single file: pre-check for structured_data, then use worker if needed.

    Args:
        file_path: Path to the JSON file to process.
        input_dir: Base input directory for calculating relative paths.
        good_dir: Directory to copy good files to.
        trash_dir: Directory to copy trash files to.
        worker_queue: Queue of available ApiWorker instances.
        dry_run: If True, does not copy files and processes limited count.

    Returns:
        A string indicating the result: "SUCCESS_GOOD", "SUCCESS_TRASH", or "FAILED".
    """
    try:
        content_text = file_path.read_text(encoding="utf-8")
        data = json.loads(content_text)

        # Rule: missing or empty structured_data -> trash
        structured_data = data.get("structured_data")
        # If structured_data is missing, None, or empty list/dict, it's trash
        if not structured_data:
            classification = 0
            is_auto = True
        else:
            is_auto = False
    except Exception as e:
        logging.error(f"Failed to pre-process {file_path.name}: {e}")
        return "FAILED"

    rel_path = file_path.relative_to(input_dir)

    if is_auto:
        dest = trash_dir / rel_path
        if not dry_run:
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(file_path, dest)
        logging.info(f"AUTO -> TRASH (no structured_data): {rel_path}")
        return "SUCCESS_TRASH"

    for attempt in range(1, 4):  # 3 attempts
        worker = worker_queue.get()
        try:
            classification = worker.process(file_path)

            if classification == 1:
                dest = good_dir / rel_path
                if not dry_run:
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(file_path, dest)
                logging.info(f"Worker {worker.id} -> GOOD: {rel_path}")
                worker_queue.put(worker)
                return "SUCCESS_GOOD"
            elif classification == 0:
                dest = trash_dir / rel_path
                if not dry_run:
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(file_path, dest)
                logging.info(f"Worker {worker.id} -> TRASH: {rel_path}")
                worker_queue.put(worker)
                return "SUCCESS_TRASH"
            else:
                worker_queue.put(worker)
                if attempt == 3:
                    logging.error(f"Worker {worker.id} -> FAILED parsing: {rel_path}")
                    return "FAILED"
                logging.warning(
                    f"Worker {worker.id} -> Retrying parse failure: {rel_path} (Attempt {attempt}/3)"
                )
                time.sleep(2)

        except Exception as e:
            worker_queue.put(worker)
            if attempt == 3:
                logging.error(f"Worker {worker.id} -> FAILED exception: {rel_path} - {str(e)}")
                return "FAILED"
            logging.warning(
                f"Worker {worker.id} -> Retrying exception: {rel_path} - {str(e)} (Attempt {attempt}/3)"
            )
            time.sleep(2)
    return "FAILED"

def main(input_dir: str, good_dir: str, trash_dir: str, dry_run: bool):
    input_path = Path(input_dir)
    good_path = Path(good_dir)
    trash_path = Path(trash_dir)
    
    good_path.mkdir(parents=True, exist_ok=True)
    trash_path.mkdir(parents=True, exist_ok=True)
    
    workers_list = load_workers()
    if not workers_list:
        logging.error("No API keys found. Exiting.")
        return
        
    worker_queue = queue.Queue()
    for w in workers_list:
        worker_queue.put(w)
        
    unprocessed_files = get_unprocessed_files(input_path, good_path, trash_path)
    
    if dry_run:
        logging.info("DRY RUN MODE: Processing max 5 files.")
        unprocessed_files = unprocessed_files[:5]
        
    logging.info(f"Found {len(unprocessed_files)} files to process.")
    
    success_good = 0
    success_trash = 0
    failed = 0
    
    num_threads = min(20, len(workers_list)) # Cap at 20 or number of keys
    
    with ThreadPoolExecutor(max_workers=num_threads) as executor:
        futures = {
            executor.submit(
                process_single_file, f, input_path, good_path, trash_path, worker_queue, dry_run
            ): f
            for f in unprocessed_files
        }
        
        for future in as_completed(futures):
            result = future.result()
            if result == "SUCCESS_GOOD":
                success_good += 1
            elif result == "SUCCESS_TRASH":
                success_trash += 1
            else:
                failed += 1
                
    logging.info(f"Processing complete. Good: {success_good}, Trash: {success_trash}, Failed: {failed}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Classify JSON files using Ollama/Nvidia.")
    parser.add_argument("--input", default="data/health_insurance/health_insurance_extracted", help="Input directory")
    parser.add_argument("--good", default="data/health_insurance/good_content", help="Output directory for good content")
    parser.add_argument("--trash", default="data/health_insurance/trash_content", help="Output directory for trash content")
    parser.add_argument("--dry-run", action="store_true", help="Run without copying files, max 5 files")
    
    args = parser.parse_args()
    main(args.input, args.good, args.trash, args.dry_run)
