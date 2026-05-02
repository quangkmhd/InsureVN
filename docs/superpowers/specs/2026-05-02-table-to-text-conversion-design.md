# Design Spec: Table-to-Text Conversion for RAG Optimization

## 1. Overview
RAG systems generally struggle to understand and reason over complex tabular data formatted as Markdown. To improve the accuracy and context retrieval for the insurance chatbot, this one-off batch script will detect Markdown tables in the extracted `.md` files, pass them to an LLM (Gemini Vertex AI) to generate a detailed prose description of the table's contents, and inject this description directly below the table.

## 2. Input and Output
- **Input:** Existing Markdown files (`.md`) located in `data/health_insurance/health_insurance_markdowns/`.
- **Output:** The exact same Markdown files modified in place.
- **Modification Format:** For each detected table, the following will be appended immediately after the table block:
  ```markdown

  **Diễn giải dữ liệu:**
  [Generated prose from LLM]
  ```

## 3. Architecture & Data Flow
The process is implemented as a standalone batch script `scripts/03_conversion/convert_tables_to_text.py`.

1. **File Scanning:**
   - Use Python's `pathlib` to recursively scan `data/health_insurance/health_insurance_markdowns/`.
   - Pre-filter: Only process files that contain the pipe character `|` to optimize execution speed.
2. **Table Detection:**
   - Parse the file content using a Regular Expression designed to capture standard Markdown tables:
     `r"(?:\|.*\|(?:\n|\r\n?))+\|.*\|"`
3. **LLM Processing:**
   - For each detected table, invoke the Gemini Vertex AI model via the existing LangChain setup (`src.core.llm`).
   - **Prompt Design:**
     > "Dưới đây là một bảng dữ liệu bảo hiểm. Hãy diễn giải các thông tin trong bảng thành một đoạn văn xuôi chi tiết, đảm bảo không bỏ sót các con số, quyền lợi và điều kiện tương ứng. Văn phong chuyên nghiệp, dễ hiểu cho người dùng cuối."
4. **Content Injection & Saving:**
   - Replace the original table string in the file with the original table plus the LLM-generated description.
   - Save the modified content back to the `.md` file.

## 4. Error Handling & Resilience
- **API Resilience:** Implement exponential backoff/retries (e.g., using `tenacity`) for LLM API calls to handle rate limiting and quotas.
- **Fault Tolerance:** Wrap the LLM call in a `try-except` block. If processing a specific table fails after retries, log the error (with file path and table snippet) and continue to the next table.
- **Idempotency Consideration:** The script should ideally skip tables that already have a "**Diễn giải dữ liệu:**" marker immediately following them, preventing duplicate descriptions if the script needs to be re-run.

## 5. Deployment / Execution
The script is intended to be executed manually from the project root:
```bash
python scripts/03_conversion/convert_tables_to_text.py
```
