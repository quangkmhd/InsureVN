# JSON Classification Pipeline Design
**Date:** 2026-05-01
**Topic:** JSON Classification Pipeline

## Architecture & Components
- **Input**: ~1500 JSON files containing extracted health insurance document data (tables, text, pictures) in `/home/quangnhvn34/dev/me/InsureVN/data/health_insurance/health_insurance_extracted`.
- **Processing**: 
  - Asynchronous Python script using `asyncio` to read files.
  - A pool of 5 worker coroutines. Each worker gets assigned one of the 5 Ollama API keys loaded from the `.env` file.
  - Each worker processes 1 file at a time using its designated API key to prevent rate limits. Maximum of 5 concurrent requests overall.
- **Output**: 
  - `good_content/`: JSON files classified as 1 (good content/information for SQL DB).
  - `trash_content/`: JSON files classified as 0 (trash/no need content).

## Data Flow
1. Load 5 API keys from `.env`.
2. Discover all `.json` files in the input directory.
3. For each file, check if a file with the same name already exists in either `good_content/` or `trash_content/`. If it does, skip processing.
4. Send the raw content of the JSON file to Gemma 4 running in Ollama Cloud.
5. Parse the LLM response.
6. Copy the file to the corresponding output directory based on the classification.

## Error Handling
- **LLM Output Format**: Force Gemma 4 to return structured JSON format representing its classification (e.g., `{"classification": 1}`).
- **Retries**: If the LLM returns an invalid JSON format or something other than a valid classification (1 or 0), the script will retry processing the file up to 2 times before logging a failure and skipping.
- **API Errors**: API timeouts or 429/500 errors will trigger the retry mechanism.

## Testing
- Include a `--dry-run` flag to process only 5 files and log the LLM response without copying files.
- Track success, skips, and failures in a simple local log file (`classification.log`).
