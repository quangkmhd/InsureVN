# JSON Classification Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an asynchronous Python script that reads ~1500 JSON files, classifies them as good (1) or trash (0) using Gemma 4 via Ollama, and sorts them into respective output folders.

**Architecture:** An `asyncio`-based script using an `aiohttp` client to communicate with Ollama. It will feature a pool of 5 worker tasks, each assigned a dedicated API key from `.env`. The workers will pull file paths from an `asyncio.Queue` and process them concurrently.

**Tech Stack:** Python 3.12, `asyncio`, `aiohttp`, `python-dotenv`, `pytest`

---

### Task 1: Setup and Basic File Discovery

**Files:**
- Create: `scripts/05_training_eval/classify_json.py`
- Create: `tests/unit/test_classify_json.py`

- [ ] **Step 1: Write the failing test for file discovery**

```python
# tests/unit/test_classify_json.py
import pytest
import os
from pathlib import Path
from scripts.05_training_eval.classify_json import get_unprocessed_files

def test_get_unprocessed_files(tmp_path):
    # Setup dummy environment
    input_dir = tmp_path / "input"
    good_dir = tmp_path / "good"
    trash_dir = tmp_path / "trash"
    
    input_dir.mkdir()
    good_dir.mkdir()
    trash_dir.mkdir()
    
    # Create input files
    (input_dir / "file1.json").write_text("{}")
    (input_dir / "file2.json").write_text("{}")
    (input_dir / "file3.json").write_text("{}")
    
    # Create already processed file in good_dir
    (good_dir / "file2.json").write_text("{}")
    
    # Create already processed file in trash_dir
    (trash_dir / "file3.json").write_text("{}")
    
    # Test function
    unprocessed = get_unprocessed_files(input_dir, good_dir, trash_dir)
    assert len(unprocessed) == 1
    assert unprocessed[0].name == "file1.json"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_classify_json.py::test_get_unprocessed_files -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'scripts.05_training_eval.classify_json'`

- [ ] **Step 3: Write minimal implementation**

```python
# scripts/05_training_eval/classify_json.py
import os
from pathlib import Path
from typing import List

def get_unprocessed_files(input_dir: Path, good_dir: Path, trash_dir: Path) -> List[Path]:
    """Finds all JSON files in input_dir that don't exist in good_dir or trash_dir."""
    unprocessed = []
    if not input_dir.exists():
        return []
        
    for file_path in input_dir.rglob("*.json"):
        good_path = good_dir / file_path.name
        trash_path = trash_dir / file_path.name
        
        if not good_path.exists() and not trash_path.exists():
            unprocessed.append(file_path)
            
    return unprocessed
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_classify_json.py::test_get_unprocessed_files -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/05_training_eval/classify_json.py tests/unit/test_classify_json.py
git commit -m "feat: add file discovery logic for json classifier"
```

---

### Task 2: Configuration and API Key Loading

**Files:**
- Modify: `scripts/05_training_eval/classify_json.py`
- Modify: `tests/unit/test_classify_json.py`

- [ ] **Step 1: Write the failing test for key loading**

```python
# tests/unit/test_classify_json.py
# (Add to existing file)
from scripts.05_training_eval.classify_json import load_ollama_keys

def test_load_ollama_keys(monkeypatch):
    monkeypatch.setenv("OLLAMA_KEY_1", "key1")
    monkeypatch.setenv("OLLAMA_KEY_2", "key2")
    monkeypatch.setenv("OLLAMA_KEY_3", "key3")
    monkeypatch.setenv("OLLAMA_KEY_4", "key4")
    monkeypatch.setenv("OLLAMA_KEY_5", "key5")
    
    keys = load_ollama_keys()
    assert len(keys) == 5
    assert "key1" in keys
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_classify_json.py::test_load_ollama_keys -v`
Expected: FAIL with `ImportError: cannot import name 'load_ollama_keys'`

- [ ] **Step 3: Write minimal implementation**

```python
# scripts/05_training_eval/classify_json.py
# (Add to existing file)
import os
from dotenv import load_dotenv

def load_ollama_keys() -> List[str]:
    """Loads 5 Ollama keys from environment variables."""
    load_dotenv()
    keys = []
    for i in range(1, 6):
        key = os.getenv(f"OLLAMA_KEY_{i}")
        if key:
            keys.append(key)
    if not keys:
        # Fallback if specific numbered keys aren't used, look for generic keys
        print("Warning: No OLLAMA_KEY_X found in .env")
    return keys
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_classify_json.py::test_load_ollama_keys -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/05_training_eval/classify_json.py tests/unit/test_classify_json.py
git commit -m "feat: add api key loading for json classifier"
```

---

### Task 3: Ollama API Calling Logic

**Files:**
- Modify: `scripts/05_training_eval/classify_json.py`

- [ ] **Step 1: Write the asynchronous API caller function**

```python
# scripts/05_training_eval/classify_json.py
# (Add to existing file)
import aiohttp
import asyncio
import json
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

OLLAMA_URL = "http://localhost:11434/api/chat" # Default Ollama URL, update if cloud URL is different

async def call_ollama(session: aiohttp.ClientSession, file_path: Path, api_key: str) -> int:
    """Sends JSON content to Gemma 4 and returns 1 or 0."""
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

    payload = {
        "model": "gemma4", # Or the exact model name in your ollama instance
        "messages": [{"role": "user", "content": prompt}],
        "format": "json",
        "stream": False
    }

    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}

    for attempt in range(3): # 1 initial + 2 retries
        try:
            async with session.post(OLLAMA_URL, json=payload, headers=headers, timeout=30) as response:
                if response.status == 200:
                    data = await response.json()
                    response_text = data.get("message", {}).get("content", "")
                    try:
                        result = json.loads(response_text)
                        if "classification" in result and result["classification"] in [0, 1]:
                            return result["classification"]
                    except json.JSONDecodeError:
                        pass
                
                logging.warning(f"Attempt {attempt+1}: Invalid response for {file_path.name}. Status: {response.status}")
                await asyncio.sleep(2)
        except Exception as e:
            logging.warning(f"Attempt {attempt+1}: Request failed for {file_path.name}: {e}")
            await asyncio.sleep(2)
            
    logging.error(f"Failed to process {file_path.name} after 3 attempts.")
    return -1
```

- [ ] **Step 2: Commit**

```bash
git add scripts/05_training_eval/classify_json.py
git commit -m "feat: add asynchronous ollama api calling logic"
```

---

### Task 4: Worker Pool and Main Loop

**Files:**
- Modify: `scripts/05_training_eval/classify_json.py`

- [ ] **Step 1: Write the worker and main async functions**

```python
# scripts/05_training_eval/classify_json.py
# (Add to existing file)
import shutil
import argparse

async def worker(worker_id: int, queue: asyncio.Queue, session: aiohttp.ClientSession, api_key: str, good_dir: Path, trash_dir: Path, dry_run: bool):
    """Worker coroutine that pulls files from the queue and processes them."""
    while True:
        try:
            file_path = queue.get_nowait()
        except asyncio.QueueEmpty:
            break
            
        logging.info(f"Worker {worker_id} processing {file_path.name}...")
        classification = await call_ollama(session, file_path, api_key)
        
        if classification == 1:
            dest = good_dir / file_path.name
            if not dry_run:
                shutil.copy2(file_path, dest)
            logging.info(f"Worker {worker_id} -> GOOD: {file_path.name}")
        elif classification == 0:
            dest = trash_dir / file_path.name
            if not dry_run:
                shutil.copy2(file_path, dest)
            logging.info(f"Worker {worker_id} -> TRASH: {file_path.name}")
        else:
            logging.error(f"Worker {worker_id} -> FAILED: {file_path.name}")
            
        queue.task_done()

async def main_async(input_dir: str, good_dir: str, trash_dir: str, dry_run: bool):
    input_path = Path(input_dir)
    good_path = Path(good_dir)
    trash_path = Path(trash_dir)
    
    good_path.mkdir(parents=True, exist_ok=True)
    trash_path.mkdir(parents=True, exist_ok=True)
    
    keys = load_ollama_keys()
    if not keys:
        logging.error("No API keys found. Exiting.")
        return
        
    unprocessed_files = get_unprocessed_files(input_path, good_path, trash_path)
    
    if dry_run:
        logging.info("DRY RUN MODE: Processing max 5 files.")
        unprocessed_files = unprocessed_files[:5]
        
    logging.info(f"Found {len(unprocessed_files)} files to process.")
    
    queue = asyncio.Queue()
    for f in unprocessed_files:
        queue.put_nowait(f)
        
    async with aiohttp.ClientSession() as session:
        workers = []
        # Create up to 5 workers, matching the number of keys
        num_workers = min(len(keys), 5)
        for i in range(num_workers):
            task = asyncio.create_task(worker(i, queue, session, keys[i], good_path, trash_path, dry_run))
            workers.append(task)
            
        await asyncio.gather(*workers)
        
    logging.info("Processing complete.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Classify JSON files using Ollama.")
    parser.add_argument("--input", default="data/health_insurance/health_insurance_extracted", help="Input directory")
    parser.add_argument("--good", default="data/health_insurance/good_content", help="Output directory for good content")
    parser.add_argument("--trash", default="data/health_insurance/trash_content", help="Output directory for trash content")
    parser.add_argument("--dry-run", action="store_true", help="Run without copying files, max 5 files")
    
    args = parser.parse_args()
    asyncio.run(main_async(args.input, args.good, args.trash, args.dry_run))
```

- [ ] **Step 2: Commit**

```bash
git add scripts/05_training_eval/classify_json.py
git commit -m "feat: complete async worker pool and main execution loop"
```
