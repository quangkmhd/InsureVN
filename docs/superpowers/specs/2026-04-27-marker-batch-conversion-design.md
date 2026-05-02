# Marker Batch PDF Conversion Script Design

## 1. Overview
A standalone Python script (`scripts/09_convert_pdfs_marker.py`) to batch convert all PDF files from a source directory into Markdown format using the `marker-pdf` library. The script will utilize Marker's Hybrid Mode (LLM integration) for higher accuracy and execute conversions in parallel while preserving the original subdirectory structure.

## 2. Architecture & Approach
- **Language/Location:** Python 3.12, located in the `scripts/` directory.
- **Execution Method:** The script will use the `subprocess` module to call the `marker_single` CLI command for each file. This ensures proper memory isolation for the heavy deep learning models Marker uses, avoiding potential memory leaks from the Python API during long batch runs.
- **Concurrency:** `concurrent.futures.ThreadPoolExecutor` will be used to manage a pool of worker threads. The number of workers will be configurable (defaulting to 2 to avoid OOM issues on standard machines).

## 3. Data Flow
1. **Input:** `data/health_insurance_pdfs` directory containing subdirectories (e.g., `aia.com.vn/`).
2. **Path Resolution:** The script traverses the input directory recursively to find all `.pdf` files.
3. **Output Mapping:** For each PDF, the script calculates its relative path to the source directory and creates a corresponding output directory structure in `data/processed/marker_markdowns`.
4. **Processing:**
   - Execute: `marker_single <input_pdf> --output_dir <corresponding_output_dir> --use_llm`
   - Capture standard output and error for logging.
5. **Output:** Markdown files, extracted images, and metadata saved in the designated output directories.

## 4. Error Handling & Logging
- Wrap the subprocess call in a `try...except` block.
- If a specific PDF fails to convert (e.g., corrupted file, timeout), log the error and file path to the console, and allow the thread pool to proceed to the next file.
- Use Python's built-in `logging` module to track progress (e.g., "Converted 10/150 files").

## 5. Prerequisites
- `marker-pdf` must be installed (`pip install marker-pdf[full]`).
- The `GEMINI_API_KEY` (or equivalent supported LLM key) must be present in the environment for the `--use_llm` flag to function.

## 6. Trade-offs
- Calling CLI via `subprocess` is slightly slower than direct Python API usage due to model loading overhead per file, but it guarantees memory safety for massive batch jobs, which is crucial for OCR tasks.
