# Phase 02: Qdrant Document Retrieval

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` or `superpowers:executing-plans` to implement this plan task-by-task. Apply `tdd-workflow` for every code change.

> **Phase Mapping:** This is Blueprint Phase 02 = Design Spec Phase 2a (Qdrant Document Retrieval). See `docs/2026-05-03-insurevn-multi-agent-platform-design.md` Section 5, Phase 2a.

### Dependencies

New packages to install:
- `qdrant-client` — Qdrant vector database client
- `langchain-google-genai` — Google Gemini embedding and LLM integration
- `sentence-transformers` — local embedding model inference (for Option 2)
- `underthesea` — Vietnamese word segmentation for BM25/keyword search

## 1. Thong Tin Chung

**Muc tieu cot loi:** Add the document canonical source using Qdrant with parent-child chunks, hard filters, Vietnamese-aware dense + keyword retrieval, and citation-rich document evidence.

**Definition of Done:**
- Markdown policy documents can be chunked into child chunks and parent sections.
- Qdrant payloads include required metadata fields from the platform design.
- Retrieval applies hard filters for company, product, plan, document type, and section when provided.
- Dense vector retrieval works and keyword/sparse retrieval is implemented as a required retrieval pillar. If sparse indexing is temporarily blocked, dense-only mode must be guarded by an explicit degraded-mode flag, warning logs, and failing production-readiness gate.
- Child retrieval expands to parent section context.
- Retrieval output is normalized into `Evidence(source_type="qdrant_chunk")`.

## 2. Scope

**Can lam:**
- Build document chunking, indexing, retrieval, and Qdrant evidence adapter.
- Normalize Vietnamese text and diacritics for query matching.
- Add collection setup/configuration and fixture-backed integration tests.

**Khong duoc lam trong phase nay:**
- Do not implement Knowledge Graph traversal.
- Do not add SupervisorAgent or specialist agents.
- Do not tune for full production scale before benchmark evidence exists.
- Do not allow unfiltered cross-company retrieval when a hard filter is present.

## 3. Kien Truc Va Cong Nghe

**Framework selection:** Use LangChain retriever/vector store primitives for Qdrant and optional BM25/sparse retrieval. LangGraph is not needed yet except for future compatibility of return contracts.

**Embedding model:** 
- **Option 1 (Cloud):** Use `gemini-embedding-2` via `langchain-google-genai`. Best for high-precision multilingual performance.
- **Option 2 (Local):** Use `Qwen/Qwen2.5-Math-7B-Instruct` or specific `Qwen3-Embedding-8B` (once available) via `sentence-transformers` or `Ollama`. Best for data privacy and local high-performance inference.
Config keys: `GOOGLE_API_KEY` (for Option 1) and `RAG_EMBEDDING_MODEL`.

**Vietnamese text normalization:** Use `underthesea` for word segmentation in BM25/keyword retrieval. Apply NFC Unicode normalization on all queries and indexed text to handle diacritics (`bảo hiểm` ↔ `bao hiem`). Config key: `RAG_VIETNAMESE_SEGMENTER` (default: `underthesea`).

**Files to create:**
- `src/services/document_chunker.py`: Markdown section parser, child chunk generator, parent section expansion.
- `src/services/qdrant_retriever.py`: Qdrant collection setup and filtered retrieval.
- `src/services/qdrant_evidence_adapter.py`: Qdrant payload/document to `Evidence`.
- `scripts/06_db_ingestion/04_index_qdrant_documents.py`: indexing CLI script.
- `tests/unit/test_document_chunker.py`
- `tests/unit/test_qdrant_evidence_adapter.py`
- `tests/integration/test_qdrant_retriever_filters.py`

**Files to modify:**
- `src/core/config.py`: add `QDRANT_*`, `GOOGLE_API_KEY`, `RAG_EMBEDDING_MODEL`, and retrieval limits with explicit casts.
- `.env`: register `GOOGLE_API_KEY` and every new Qdrant/RAG parameter with comments.

**Tools/MCP/DB:**
- Qdrant stores document chunks.
- SQLite can be read by indexing scripts to validate `company_code`, `document_id`, `plan_code`, and `source_table_id` metadata.

## 4. Data Flow

**Input:**
- Markdown text from `data/processed/` or domain-specific document folders.
- Existing SQLite document/company/plan identifiers.
- `RetrievalPlan.hard_filters` from Phase 01 fixtures or later Supervisor output.

**Output:**
- Qdrant points with dense embeddings and metadata payload.
- Sparse vectors or BM25 keyword index as the second retrieval pillar. Dense-only is permitted only in local degraded mode and must not satisfy production DoD.
- Retrieved parent-section evidence with citation metadata:
  `company_code`, `document_id`, `document_type`, `document_name`, `product_line`, `plan_code`, `section_type`, `page_number`, `chunk_index`, `source_path`, `source_table_id`, `effective_date`.

## 5. Huong Dan Trien Khai

1. Write failing tests for Markdown heading parsing, child chunk size, overlap, and parent section expansion.
2. Implement `DocumentChunker` with deterministic chunk IDs and NFC Unicode normalization.
3. Write failing tests for Qdrant payload validation and missing citation fields.
4. Implement `QdrantEvidenceAdapter` using the `Evidence` model from Phase 01.
5. Add config fields with agent/tool prefixes: `RAG_QDRANT_URL`, `RAG_QDRANT_COLLECTION`, `GOOGLE_API_KEY`, `RAG_EMBEDDING_MODEL`, `RAG_CHILD_CHUNK_TOKENS`, `RAG_CHILD_CHUNK_OVERLAP`, `RAG_PARENT_SECTION_MAX_CHARS`.
6. Write failing keyword retrieval tests for exact policy codes, disease/drug names, and Vietnamese legal terms.
7. Implement BM25 or Qdrant sparse retrieval and reciprocal rank fusion with dense results.
8. Write failing integration tests that index two companies with similar policy text and query with a hard `company_code` filter.
9. Implement `QdrantRetriever.retrieve(retrieval_plan)` with strict filter construction.
10. Add parent-section expansion: retrieved child chunk IDs map back to full parent section text before conversion to evidence.
11. Add Vietnamese query normalization tests for `bao hiem` and `bảo hiểm`.
12. Build indexing script with dry-run mode and JSON logging.

## 6. Observability

**Log format:** JSON.

**Required log metadata:**
- `component`: `document_chunker`, `qdrant_indexer`, or `qdrant_retriever`
- `collection_name`
- `document_id`
- `company_code`
- `chunk_count`
- `parent_section_count`
- `hard_filters`
- `top_k`
- `latency_ms`
- `retrieved_count`

**Langfuse tracking:** Later LangGraph nodes will attach retriever observations. In this phase, expose callback hooks or metadata return fields but avoid hard-coding trace creation in retriever services.

## 7. Testing Strategy

Apply `tdd-workflow`.

**Unit tests:**
- Chunk boundary and overlap behavior.
- Required Qdrant payload fields.
- Evidence conversion preserves citations.
- Vietnamese normalization.

**Integration tests:**
- Qdrant container/service retrieval with hard filters.
- Parent expansion returns parent text, not only child text.
- Company-specific query cannot retrieve another company when a hard filter exists.
- Exact keyword query returns the expected document even when dense similarity is weak.
- Degraded dense-only mode logs `retrieval_degraded=true` and fails production readiness checks.

**E2E tests:** None until Supervisor and specialist workflows exist.

## 8. Debug Va Kiem Tra

**Reproduce common failures:**
- Run `pytest tests/integration/test_qdrant_retriever_filters.py -v`.
- Inspect one indexed point payload through Qdrant client and verify citation fields.
- Query with and without `company_code` hard filter and compare returned companies.

**Verification before next phase:**
- `pytest tests/unit/test_document_chunker.py tests/unit/test_qdrant_evidence_adapter.py -v`
- `pytest tests/integration/test_qdrant_retriever_filters.py -v`
- `ruff check src tests scripts/06_db_ingestion`
- `ruff format --check src tests scripts/06_db_ingestion`

## 9. Execution Task Breakdown

### Task 1: Chunking And Payload Contracts

**Files:**
- Create: `src/services/document_chunker.py`
- Create: `src/services/qdrant_evidence_adapter.py`
- Test: `tests/unit/test_document_chunker.py`
- Test: `tests/unit/test_qdrant_evidence_adapter.py`

- [ ] Step 1: Write failing tests for parent/child chunking and required payload fields.
- [ ] Step 2: Implement chunking, payload validation, and evidence conversion.
- [ ] Step 3: Run `pytest tests/unit/test_document_chunker.py tests/unit/test_qdrant_evidence_adapter.py -v`; expected PASS.

### Task 2: Dense + Keyword Retrieval

**Files:**
- Create: `src/services/qdrant_retriever.py`
- Test: `tests/integration/test_qdrant_retriever_filters.py`

- [ ] Step 1: Write failing tests for hard filters, dense retrieval, keyword retrieval, and degraded-mode rejection.
- [ ] Step 2: Implement Qdrant filtered retrieval and BM25/sparse fusion.
- [ ] Step 3: Run `pytest tests/integration/test_qdrant_retriever_filters.py -v`; expected PASS.

### Task 3: Indexing Script

**Files:**
- Create: `scripts/06_db_ingestion/04_index_qdrant_documents.py`

- [ ] Step 1: Add dry-run indexing path with JSON logging.
- [ ] Step 2: Run dry-run against a fixture document; expected chunk and payload counts in logs.
