# Marker Batch PDF Conversion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. (Gemini CLI operates in single-session mode).

**Goal:** Build a script to batch convert PDFs to Markdown using Datalab Marker with Hybrid Mode and multiprocessing, preserving original directory structures.

**Architecture:** A standalone Python script in `scripts/09_convert_pdfs_marker.py` containing reusable functions for path resolution and subprocess execution, executed via a main multiprocessing pool.

**Tech Stack:** Python 3.12, `marker-pdf`, `concurrent.futures`, `pathlib`, `subprocess`, `pytest`.

---

### Task 1: Path Resolution Function and Test

**Files:**
- Create: `scripts/09_convert_pdfs_marker.py`
- Create: `tests/unit/test_marker_conversion.py`

- [ ] **Step 1: Write the failing test for path resolution**

Create `tests/unit/test_marker_conversion.py`:
```python
import pytest
from pathlib import Path
import sys
import os

# Add scripts directory to sys.path to import the script
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../scripts')))
from importlib import import_module

# Dynamically import the script since it starts with a number
marker_script = import_module('09_convert_pdfs_marker')

def test_get_output_dir():
    base_input = Path("/data/input")
    base_output = Path("/data/output")
    pdf_path = Path("/data/input/aia.com.vn/doc.pdf")
    
    expected_out = Path("/data/output/aia.com.vn")
    result = marker_script.get_output_dir(pdf_path, base_input, base_output)
    
    assert result == expected_out
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_marker_conversion.py -v`
Expected: FAIL with "ModuleNotFoundError" or "AttributeError".

- [ ] **Step 3: Write minimal implementation**

Create `scripts/09_convert_pdfs_marker.py`:
```python
import os
from pathlib import Path

def get_output_dir(pdf_path: Path, base_input_dir: Path, base_output_dir: Path) -> Path:
    """Calculates the corresponding output directory for a given PDF path."""
    relative_path = pdf_path.parent.relative_to(base_input_dir)
    return base_output_dir / relative_path
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_marker_conversion.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

Run:
```bash
git add scripts/09_convert_pdfs_marker.py tests/unit/test_marker_conversion.py
git commit -m "test: add path resolution for marker batch conversion"
```

---

### Task 2: Subprocess Execution Function and Test

**Files:**
- Modify: `scripts/09_convert_pdfs_marker.py`
- Modify: `tests/unit/test_marker_conversion.py`

- [ ] **Step 1: Write the failing test for PDF processing logic (mocked)**

Modify `tests/unit/test_marker_conversion.py` to add:
```python
from unittest.mock import patch, MagicMock

@patch('subprocess.run')
def test_process_pdf_success(mock_run):
    # Setup mock to simulate success
    mock_run.return_value = MagicMock(returncode=0, stdout=b"Success", stderr=b"")
    
    pdf_path = Path("/data/input/aia.com.vn/doc.pdf")
    base_input = Path("/data/input")
    base_output = Path("/data/output")
    
    result = marker_script.process_pdf(pdf_path, base_input, base_output, use_llm=True)
    
    assert result is True
    # Verify subprocess.run was called correctly
    mock_run.assert_called_once()
    args, kwargs = mock_run.call_args
    assert "marker_single" in args[0]
    assert str(pdf_path) in args[0]
    assert "--use_llm" in args[0]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_marker_conversion.py -v`
Expected: FAIL with "AttributeError: module '09_convert_pdfs_marker' has no attribute 'process_pdf'".

- [ ] **Step 3: Write minimal implementation**

Modify `scripts/09_convert_pdfs_marker.py` to add:
```python
import subprocess
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def process_pdf(pdf_path: Path, base_input_dir: Path, base_output_dir: Path, use_llm: bool = False) -> bool:
    """Processes a single PDF using Marker CLI."""
    output_dir = get_output_dir(pdf_path, base_input_dir, base_output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    cmd = ["marker_single", str(pdf_path), "--output_dir", str(output_dir)]
    if use_llm:
        cmd.append("--use_llm")
        
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        logging.info(f"Successfully converted: {pdf_path.name}")
        return True
    except subprocess.CalledProcessError as e:
        logging.error(f"Failed to convert {pdf_path.name}: {e.stderr}")
        return False
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_marker_conversion.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

Run:
```bash
git add scripts/09_convert_pdfs_marker.py tests/unit/test_marker_conversion.py
git commit -m "feat: add subprocess execution logic for marker conversion"
```

---

### Task 3: Main Batch Processing Logic

**Files:**
- Modify: `scripts/09_convert_pdfs_marker.py`

- [ ] **Step 1: Add main multiprocessing logic**

Modify `scripts/09_convert_pdfs_marker.py` to add the main execution block:
```python
import concurrent.futures
import argparse

def main():
    parser = argparse.ArgumentParser(description="Batch convert PDFs using Marker")
    parser.add_argument("--input", type=str, default="data/health_insurance_pdfs", help="Input directory")
    parser.add_argument("--output", type=str, default="data/processed/marker_markdowns", help="Output directory")
    parser.add_argument("--workers", type=int, default=2, help="Number of concurrent workers")
    parser.add_argument("--no-llm", action="store_true", help="Disable LLM Hybrid Mode")
    
    args = parser.parse_args()
    
    base_input = Path(args.input)
    base_output = Path(args.output)
    use_llm = not args.no_llm
    workers = args.workers
    
    if not base_input.exists():
        logging.error(f"Input directory does not exist: {base_input}")
        return
        
    pdf_files = list(base_input.rglob("*.pdf"))
    total_files = len(pdf_files)
    logging.info(f"Found {total_files} PDF files to process. Using LLM: {use_llm}. Workers: {workers}")
    
    successful = 0
    failed = 0
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {
            executor.submit(process_pdf, pdf, base_input, base_output, use_llm): pdf
            for pdf in pdf_files
        }
        
        for future in concurrent.futures.as_completed(futures):
            pdf_path = futures[future]
            try:
                is_success = future.result()
                if is_success:
                    successful += 1
                else:
                    failed += 1
            except Exception as exc:
                logging.error(f"Exception generated processing {pdf_path.name}: {exc}")
                failed += 1
                
    logging.info(f"Batch conversion complete. Success: {successful}, Failed: {failed}")

if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Commit**

Run:
```bash
git add scripts/09_convert_pdfs_marker.py
git commit -m "feat: add parallel batch execution logic for marker conversion"
```
