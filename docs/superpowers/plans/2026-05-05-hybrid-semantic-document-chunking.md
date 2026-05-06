# Hybrid Semantic Document Chunking Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add hybrid semantic chunking for insurance policy Markdown while preserving table-heavy documents as useful row-group chunks for Qdrant retrieval.

**Architecture:** `DocumentChunker` remains the ingestion boundary that emits parent sections and Qdrant-ready child chunks. It routes each parent section to semantic chunking, recursive Markdown chunking, or table-aware row grouping based on section shape and available embeddings.

**Tech Stack:** Python 3.12, LangChain `RecursiveCharacterTextSplitter`, LangChain Experimental `SemanticChunker`, Qdrant payload metadata, pytest.

---

### Task 1: Add Behavior Tests

**Files:**
- Modify: `tests/unit/test_document_chunker.py`

- [ ] **Step 1: Add a fake embedding provider**

```python
class RecordingEmbeddings(Embeddings):
    """Deterministic embeddings that record semantic splitter usage."""

    def __init__(self) -> None:
        self.document_batches: list[list[str]] = []

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        self.document_batches.append(texts)
        return [[1.0, 0.0] for _ in texts]

    def embed_query(self, text: str) -> list[float]:
        return [1.0, 0.0]
```

- [ ] **Step 2: Add tests for semantic routing, table row grouping, and oversized semantic fallback**

Run: `pytest tests/unit/test_document_chunker.py -v`

Expected: FAIL because `DocumentChunker` does not yet accept semantic/table configuration.

### Task 2: Implement Hybrid Chunking

**Files:**
- Modify: `src/services/document_chunker.py`

- [ ] **Step 1: Add LangChain imports and chunking configuration parameters**

Use `SemanticChunker` only when an embedding provider is available. Use `RecursiveCharacterTextSplitter.from_language(Language.MARKDOWN, ...)` for deterministic fallback.

- [ ] **Step 2: Route sections**

Rules:
- Empty section -> no child chunks.
- Table-heavy section -> split consecutive Markdown table rows, repeating table headers.
- `hybrid_semantic` with embeddings -> semantic split, then recursively split any oversized semantic chunk.
- Otherwise -> recursive Markdown split.

- [ ] **Step 3: Preserve payload behavior**

Keep existing `ParentSection`, `ChildChunk`, `ChunkedDocument`, `content_hash`, `parent_text`, and required Qdrant payload fields.

Run: `pytest tests/unit/test_document_chunker.py -v`

Expected: PASS.

### Task 3: Wire Ingestion Configuration

**Files:**
- Modify: `src/core/config.py`
- Modify: `scripts/06_db_ingestion/04_index_qdrant_documents.py`
- Modify: `.env`

- [ ] **Step 1: Add typed RAG chunking settings**

Settings:
- `RAG_CHUNKING_STRATEGY`
- `RAG_SEMANTIC_TARGET_CHARS`
- `RAG_SEMANTIC_MAX_CHARS`
- `RAG_SEMANTIC_MIN_CHARS`
- `RAG_SEMANTIC_BREAKPOINT_TYPE`
- `RAG_SEMANTIC_BREAKPOINT_AMOUNT`
- `RAG_TABLE_LINE_RATIO_THRESHOLD`
- `RAG_TABLE_CHUNK_MAX_CHARS`

- [ ] **Step 2: Reuse the dense embedding provider**

Build the configured dense embedding provider once in the indexing script and pass it both to `DocumentChunker` and `QdrantRetriever`.

Run: `pytest tests/unit/test_qdrant_indexing_script.py -v`

Expected: PASS.

### Task 4: Verify

**Files:**
- Modify as needed from earlier tasks only.

- [ ] **Step 1: Run focused tests**

```bash
pytest tests/unit/test_document_chunker.py tests/unit/test_qdrant_indexing_script.py -v
```

- [ ] **Step 2: Run formatting/linting on changed files**

```bash
ruff format src/services/document_chunker.py src/core/config.py scripts/06_db_ingestion/04_index_qdrant_documents.py tests/unit/test_document_chunker.py tests/unit/test_qdrant_indexing_script.py
ruff check src/services/document_chunker.py src/core/config.py scripts/06_db_ingestion/04_index_qdrant_documents.py tests/unit/test_document_chunker.py tests/unit/test_qdrant_indexing_script.py
```
