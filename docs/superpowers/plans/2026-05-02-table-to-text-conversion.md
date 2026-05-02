# Table-to-Text Conversion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a batch Python script to detect Markdown tables in `.md` files, convert them to prose using Gemini Vertex AI, and append the text below the tables.

**Architecture:** A standalone script that uses regex to find tables, and LangChain's `ChatVertexAI` to generate descriptions. Modifies `.md` files in place with idempotency checks.

**Tech Stack:** Python 3.12, LangChain, `langchain-google-vertexai`, `pytest`, `tenacity`.

---

### Task 1: Create the LLM Client

**Files:**
- Create: `src/core/llm.py`
- Create: `tests/unit/core/test_llm.py`

- [ ] **Step 1: Write the failing test**
```python
# tests/unit/core/test_llm.py
from unittest.mock import patch
from src.core.llm import get_llm

@patch("src.core.llm.ChatVertexAI")
def test_get_llm_initializes_vertex_ai(mock_chat_vertex_ai):
    llm = get_llm()
    assert llm is not None
    mock_chat_vertex_ai.assert_called_once_with(model_name="gemini-1.5-pro-preview-0409", temperature=0.0)
```

- [ ] **Step 2: Run test to verify it fails**
Run: `pytest tests/unit/core/test_llm.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'src.core.llm'"

- [ ] **Step 3: Write minimal implementation**
```python
# src/core/llm.py
from langchain_google_vertexai import ChatVertexAI

def get_llm() -> ChatVertexAI:
    """Initialize and return the Gemini Vertex AI client."""
    return ChatVertexAI(
        model_name="gemini-1.5-pro-preview-0409",
        temperature=0.0
    )
```

- [ ] **Step 4: Run test to verify it passes**
Run: `pytest tests/unit/core/test_llm.py -v`
Expected: PASS

- [ ] **Step 5: Commit**
```bash
git add src/core/llm.py tests/unit/core/test_llm.py
git commit -m "feat(core): add get_llm utility for Vertex AI"
```

### Task 2: Implement Table Extraction Logic

**Files:**
- Create: `scripts/03_conversion/convert_tables_to_text.py`
- Create: `tests/unit/scripts/test_convert_tables_to_text.py`

- [ ] **Step 1: Write the failing test**
```python
# tests/unit/scripts/test_convert_tables_to_text.py
import pytest
from scripts.03_conversion.convert_tables_to_text import extract_markdown_tables

def test_extract_markdown_tables():
    content = "Some text.\n\n| Col1 | Col2 |\n|---|---|\n| A | B |\n\nMore text."
    tables = extract_markdown_tables(content)
    assert len(tables) == 1
    assert "Col1" in tables[0]
    
def test_extract_markdown_tables_no_table():
    content = "Some text.\n\nNo table here.\n\nMore text."
    tables = extract_markdown_tables(content)
    assert len(tables) == 0
```

- [ ] **Step 2: Run test to verify it fails**
Run: `pytest tests/unit/scripts/test_convert_tables_to_text.py -v`
Expected: FAIL with "ImportError" or similar.

- [ ] **Step 3: Write minimal implementation**
```python
# scripts/03_conversion/convert_tables_to_text.py
import re

def extract_markdown_tables(content: str) -> list[str]:
    """Finds all markdown tables in a string and returns them as a list."""
    pattern = r"(?:\|.*?\|(?:\n|\r\n?))+\|.*?\|"
    return re.findall(pattern, content)
```

- [ ] **Step 4: Run test to verify it passes**
Run: `pytest tests/unit/scripts/test_convert_tables_to_text.py -v`
Expected: PASS

- [ ] **Step 5: Commit**
```bash
git add scripts/03_conversion/convert_tables_to_text.py tests/unit/scripts/test_convert_tables_to_text.py
git commit -m "feat(scripts): add markdown table regex extraction"
```

### Task 3: Implement LLM Processing Wrapper

**Files:**
- Modify: `scripts/03_conversion/convert_tables_to_text.py`
- Modify: `tests/unit/scripts/test_convert_tables_to_text.py`

- [ ] **Step 1: Write the failing test**
```python
# tests/unit/scripts/test_convert_tables_to_text.py (append)
from unittest.mock import MagicMock
from scripts.03_conversion.convert_tables_to_text import generate_description

def test_generate_description():
    mock_llm = MagicMock()
    mock_llm.invoke.return_value.content = "This is a table description."
    
    result = generate_description("| A | B |\n|---|---|", mock_llm)
    
    assert result == "This is a table description."
    mock_llm.invoke.assert_called_once()
    assert "Dưới đây là một bảng dữ liệu bảo hiểm" in mock_llm.invoke.call_args[0][0]
```

- [ ] **Step 2: Run test to verify it fails**
Run: `pytest tests/unit/scripts/test_convert_tables_to_text.py::test_generate_description -v`
Expected: FAIL 

- [ ] **Step 3: Write minimal implementation**
```python
# scripts/03_conversion/convert_tables_to_text.py (append)
from langchain_core.language_models import BaseChatModel
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def generate_description(table_content: str, llm: BaseChatModel) -> str:
    """Sends table to LLM and returns the generated prose description."""
    prompt = f"""Dưới đây là một bảng dữ liệu bảo hiểm. Hãy diễn giải các thông tin trong bảng thành một đoạn văn xuôi chi tiết, đảm bảo không bỏ sót các con số, quyền lợi và điều kiện tương ứng. Văn phong chuyên nghiệp, dễ hiểu cho người dùng cuối.

Bảng dữ liệu:
{table_content}"""
    
    response = llm.invoke(prompt)
    return response.content.strip()
```

- [ ] **Step 4: Run test to verify it passes**
Run: `pytest tests/unit/scripts/test_convert_tables_to_text.py::test_generate_description -v`
Expected: PASS

- [ ] **Step 5: Commit**
```bash
git add scripts/03_conversion/convert_tables_to_text.py tests/unit/scripts/test_convert_tables_to_text.py
git commit -m "feat(scripts): add LLM wrapper for table description generation"
```

### Task 4: Implement File Processing and Main Loop

**Files:**
- Modify: `scripts/03_conversion/convert_tables_to_text.py`
- Modify: `tests/unit/scripts/test_convert_tables_to_text.py`

- [ ] **Step 1: Write the failing test**
```python
# tests/unit/scripts/test_convert_tables_to_text.py (append)
import tempfile
import os
from unittest.mock import patch
from scripts.03_conversion.convert_tables_to_text import process_file

@patch("scripts.03_conversion.convert_tables_to_text.generate_description")
def test_process_file(mock_generate):
    mock_generate.return_value = "Mocked description."
    
    with tempfile.NamedTemporaryFile(mode='w+', delete=False, suffix='.md') as temp_file:
        temp_file.write("Prefix\n\n| Col |\n|---|\n| Val |\n\nSuffix")
        temp_file_path = temp_file.name

    try:
        # Should process and modify the file
        mock_llm = MagicMock()
        process_file(temp_file_path, mock_llm)
        
        with open(temp_file_path, 'r') as f:
            content = f.read()
            
        assert "**Diễn giải dữ liệu:**" in content
        assert "Mocked description." in content
        assert "| Col |\n|---|\n| Val |" in content
        
        # Test Idempotency: should not process again
        mock_generate.reset_mock()
        process_file(temp_file_path, mock_llm)
        mock_generate.assert_not_called()
    finally:
        os.remove(temp_file_path)
```

- [ ] **Step 2: Run test to verify it fails**
Run: `pytest tests/unit/scripts/test_convert_tables_to_text.py::test_process_file -v`
Expected: FAIL 

- [ ] **Step 3: Write minimal implementation**
```python
# scripts/03_conversion/convert_tables_to_text.py (append)
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

def process_file(file_path: str, llm: BaseChatModel) -> None:
    """Processes a single markdown file, injecting descriptions below tables."""
    path = Path(file_path)
    content = path.read_text(encoding="utf-8")
    
    # Fast exit if no potential table
    if "|" not in content:
        return
        
    tables = extract_markdown_tables(content)
    if not tables:
        return
        
    modified = False
    for table in tables:
        # Check idempotency
        marker = "**Diễn giải dữ liệu:**"
        table_with_marker = f"{table}\n\n{marker}"
        if table_with_marker in content:
            continue # Already processed
            
        try:
            logging.info(f"Processing table in {path.name}")
            description = generate_description(table, llm)
            replacement = f"{table}\n\n{marker}\n{description}"
            content = content.replace(table, replacement, 1)
            modified = True
        except Exception as e:
            logging.error(f"Failed to process table in {path.name}: {e}")
            
    if modified:
        path.write_text(content, encoding="utf-8")
        logging.info(f"Updated {path}")

def main():
    import sys
    # Add project root to sys.path if needed
    sys.path.append(str(Path(__file__).parent.parent.parent))
    from src.core.llm import get_llm
    
    markdowns_dir = Path("data/health_insurance/health_insurance_markdowns")
    if not markdowns_dir.exists():
        logging.error(f"Directory not found: {markdowns_dir}")
        return
        
    llm = get_llm()
    md_files = list(markdowns_dir.rglob("*.md"))
    logging.info(f"Found {len(md_files)} markdown files.")
    
    for md_file in md_files:
        process_file(str(md_file), llm)
        
if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run test to verify it passes**
Run: `pytest tests/unit/scripts/test_convert_tables_to_text.py::test_process_file -v`
Expected: PASS

- [ ] **Step 5: Commit**
```bash
git add scripts/03_conversion/convert_tables_to_text.py tests/unit/scripts/test_convert_tables_to_text.py
git commit -m "feat(scripts): add file processing and main loop for table conversion"
```
