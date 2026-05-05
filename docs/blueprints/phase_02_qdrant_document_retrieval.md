# Phase 02: Qdrant Document Retrieval

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` or `superpowers:executing-plans` to implement this plan task-by-task. Apply `tdd-workflow` for every code change.

> **Phase Mapping:** This is Blueprint Phase 02 = Design Spec Phase 2a (Qdrant Document Retrieval). See `docs/2026-05-03-insurevn-multi-agent-platform-design.md` Section 5, Phase 2a.

### Dependencies

New packages to install:
- `langchain-qdrant` — first-choice LangChain integration for Qdrant vector stores and retrievers.
- `qdrant-client` — direct Qdrant admin, collection, payload index, and integration-test client.
- `fastembed` — local dense and sparse embedding support used by `FastEmbedSparse` when appropriate.
- `langchain-google-genai` — Gemini model and embedding integration when cloud mode is enabled.
- `sentence-transformers` — local embedding fallback only when the selected local model is not available through Qdrant/FastEmbed/Ollama.
- `underthesea` — Vietnamese word segmentation and keyword normalization.

Existing project packages used in this phase:
- `langchain` / `langchain-core` — `Document`, retriever `Runnable` contract, tools, callbacks, and structured model wrappers.
- `langgraph` — only for optional indexing workflow orchestration when indexing becomes long-running or resumable.
- `langfuse` — tracing metadata target; do not hard-code trace creation inside low-level retrieval services.

## 1. Thong Tin Chung

**Muc tieu cot loi:** Build the production document canonical source on Qdrant using LangChain-native retrieval contracts, Qdrant native dense+sparse hybrid search, strict insurance metadata filters, parent-child context expansion, reranking hooks, and citation-complete `Evidence(source_type="qdrant_chunk")`.

**Definition of Done:**
- Markdown/PDF-derived insurance documents are chunked into deterministic parent sections and child chunks.
- Qdrant collection uses named dense and sparse vectors and indexed payload fields for hard filters.
- `langchain_qdrant.QdrantVectorStore` is the default retrieval integration. Direct `qdrant-client` calls are allowed for collection setup, payload indexes, batch upserts, and tests that LangChain does not expose cleanly.
- Retrieval supports Qdrant native hybrid retrieval using dense embeddings plus sparse/BM25-style vectors. Dense-only mode is local-development degraded mode only and must fail production readiness.
- Hard filters are mandatory for company, product, plan, document type, section, and effective-date constraints when they exist in `RetrievalPlan`.
- Child retrieval expands to parent section context before evidence conversion.
- Retrieval output preserves enough citation lineage for legal review: document, source path, page/section, chunk, source table, effective date, retrieval mode, and scores.
- Retriever services expose LangChain `Runnable`/retriever-compatible interfaces so Phase 04 can compose them with `EnsembleRetriever`, LangGraph nodes, and Deep Agents tools without adapters.

## 2. Scope

**Can lam:**
- Build document loading, chunking, indexing, retrieval, evidence conversion, and production readiness checks for Qdrant.
- Prefer LangChain/Qdrant built-ins before custom code: `QdrantVectorStore`, `RetrievalMode.HYBRID`, `FastEmbedSparse`, retriever `.invoke(...)`, and callback metadata.
- Add direct Qdrant payload indexes for high-selectivity filters.
- Add fixture-backed integration tests for multi-company hard filtering and hybrid retrieval.
- Add an optional LangGraph indexing workflow only if indexing needs durable checkpoints, retries, or resumable batches.

**Khong duoc lam trong phase nay:**
- Do not implement the Neo4j knowledge graph. Phase 03 owns graph construction.
- Do not add SupervisorAgent, specialist agents, final answer generation, or claim decisions.
- Do not hand-roll a vector store or retriever when LangChain/Qdrant provides the required behavior.
- Do not allow unfiltered cross-company retrieval when a hard filter is available.
- Do not use LLM-generated filter values unless they have already been validated against canonical IDs.

## 3. Kien Truc Va Cong Nghe

**Framework selection:** Use LangChain and Qdrant first. The production retriever must wrap `langchain_qdrant.QdrantVectorStore` and expose LangChain retriever/Runnable behavior. Use `qdrant-client` for collection administration and payload index assertions. Use LangGraph only for resumable indexing orchestration, not simple synchronous retrieval. Deep Agents are not runtime dependencies in this phase, but the retriever must be tool-friendly so a later Deep Agent can call it as a retrieval tool.

**Qdrant collection design:**
- Collection name comes from `RAG_QDRANT_COLLECTION`.
- Named vectors:
  - `text_dense`: dense Vietnamese/multilingual semantic vector.
  - `text_sparse`: sparse/BM25-style vector for exact policy codes, drugs, diseases, hospital names, and legal terms.
- Required payload indexes:
  - `company_code`
  - `document_id`
  - `document_type`
  - `product_line`
  - `plan_code`
  - `section_type`
  - `effective_date`
  - `source_table_id`
- Payload must also include `document_name`, `page_number`, `chunk_index`, `parent_section_id`, `source_path`, `content_hash`, and `ingestion_version`.

**Embedding model:**
- Cloud mode: use Gemini embeddings through `langchain-google-genai` when configured by the dedicated RAG settings.
- Local mode: use a Vietnamese-capable embedding model through FastEmbed/Ollama/sentence-transformers. Candidate models must be benchmarked on Vietnamese insurance questions before promotion.
- Sparse mode: prefer `FastEmbedSparse(model_name="Qdrant/bm25")` or the Qdrant-supported sparse provider selected by config.

**Vietnamese normalization:** Apply Unicode NFC normalization and a diacritic-insensitive search key for keyword matching. Use `underthesea` for word segmentation where sparse/keyword preprocessing needs Vietnamese token boundaries.

**Files to create:**
- `src/services/document_chunker.py`: Markdown/PDF text section parser, child chunk generator, parent section expansion.
- `src/services/qdrant_collection_manager.py`: collection creation, named vector config, sparse vector config, payload index setup, readiness checks.
- `src/services/qdrant_retriever.py`: LangChain-compatible filtered hybrid retriever.
- `src/services/qdrant_evidence_adapter.py`: Qdrant/LangChain `Document` to shared `Evidence`.
- `src/services/retrieval_readiness.py`: production gate for dense+sparse availability, payload indexes, and degraded-mode rejection.
- `scripts/06_db_ingestion/04_index_qdrant_documents.py`: indexing CLI script.
- `tests/unit/test_document_chunker.py`
- `tests/unit/test_qdrant_collection_manager.py`
- `tests/unit/test_qdrant_evidence_adapter.py`
- `tests/unit/test_retrieval_readiness.py`
- `tests/integration/test_qdrant_hybrid_retriever.py`
- `tests/integration/test_qdrant_retriever_filters.py`

**Files to modify:**
- `src/core/config.py`: add `RAG_*`, `QDRANT_*`, embedding, sparse, filter, timeout, retry, and readiness settings with explicit casts.
- `.env`: register every new RAG/Qdrant parameter with comments.
- `docs/blueprints/dependency_matrix.md`: track LangChain/Qdrant packages introduced by this phase.

**Tools/MCP/DB:**
- SQLite may be read by indexing scripts only to validate canonical IDs and source lineage. SQLite does not replace Qdrant document retrieval.
- Langfuse metadata should be emitted by caller-facing hooks/return metadata, not by direct trace writes in low-level services.

## 4. Data Flow

**Input:**
- Markdown and PDF-converted text from `data/processed/` and domain-specific document folders.
- SQLite document/company/plan/source identifiers used for validation.
- `RetrievalPlan.hard_filters` from Phase 01 fixtures or later Supervisor output.

**Indexing output:**
- Qdrant points with:
  - parent/child chunk text.
  - named dense and sparse vectors.
  - citation payload.
  - normalized Vietnamese keyword fields.
  - content hash and ingestion version for idempotent re-indexing.

**Retrieval output:**
- LangChain `Document` artifacts plus normalized evidence:
  `Evidence(source_type="qdrant_chunk", source_id=<point_id>, content=<parent_section_text>, metadata=<citation_and_scores>)`.

**Required metadata fields:**
- `company_code`
- `document_id`
- `document_type`
- `document_name`
- `product_line`
- `plan_code`
- `section_type`
- `page_number`
- `chunk_index`
- `parent_section_id`
- `source_path`
- `source_table_id`
- `effective_date`
- `content_hash`
- `ingestion_version`
- `retrieval_mode`
- `dense_score`
- `sparse_score`
- `fusion_score`

## 5. Huong Dan Trien Khai

1. Write failing chunking tests for Markdown headings, PDF-converted page markers, child size, overlap, deterministic IDs, and parent expansion.
2. Implement `DocumentChunker` with stable IDs, NFC normalization, parent/child contracts, and citation payload generation.
3. Write failing Qdrant collection tests requiring `text_dense`, `text_sparse`, payload indexes, and readiness failure when sparse vectors are missing.
4. Implement `QdrantCollectionManager` using `qdrant-client` collection and index APIs.
5. Add config fields with explicit ownership: `RAG_QDRANT_URL`, `RAG_QDRANT_API_KEY`, `RAG_QDRANT_COLLECTION`, `RAG_DENSE_VECTOR_NAME`, `RAG_SPARSE_VECTOR_NAME`, `RAG_EMBEDDING_PROVIDER`, `RAG_EMBEDDING_MODEL`, `RAG_SPARSE_MODEL`, `RAG_CHILD_CHUNK_TOKENS`, `RAG_CHILD_CHUNK_OVERLAP`, `RAG_PARENT_SECTION_MAX_CHARS`, `RAG_RETRIEVAL_TOP_K`, `RAG_RETRIEVAL_TIMEOUT_SECONDS`, `RAG_REQUIRE_HYBRID_SEARCH`.
6. Write failing evidence adapter tests for missing citation fields, score preservation, parent-section text, and invalid source lineage.
7. Implement `QdrantEvidenceAdapter` using the shared `Evidence` model from Phase 01.
8. Write failing hybrid retrieval tests for exact policy codes, Vietnamese legal terms, disease/drug names, and semantic paraphrases.
9. Implement `QdrantRetriever` around `QdrantVectorStore` with `RetrievalMode.HYBRID`; use direct Qdrant query paths only where LangChain does not expose required filters or scores.
10. Write failing hard-filter tests that index two insurers with near-duplicate policy text and verify company/plan/document filters cannot leak results.
11. Add parent-section expansion: retrieved child chunk IDs map back to full parent text before evidence conversion.
12. Add retrieval readiness gate that rejects production mode if sparse retrieval, payload indexes, hard-filter validation, or citation payloads are incomplete.
13. Build indexing script with dry-run, idempotent upsert, batch size, JSON logging, and optional LangGraph checkpointing for resumable large ingestion.

## 6. Observability

**Log format:** JSON.

**Required log metadata:**
- `component`: `document_chunker`, `qdrant_collection_manager`, `qdrant_indexer`, `qdrant_retriever`, or `retrieval_readiness`
- `collection_name`
- `document_id`
- `company_code`
- `chunk_count`
- `parent_section_count`
- `hard_filters`
- `retrieval_mode`
- `dense_vector_name`
- `sparse_vector_name`
- `top_k`
- `latency_ms`
- `retrieved_count`
- `retrieval_degraded`
- `readiness_passed`

**Langfuse tracking:** Return callback-compatible metadata from the retriever so Phase 04 LangGraph nodes can attach retriever observations. Do not create Langfuse traces directly in `src/services/qdrant_*`.

## 7. Testing Strategy

Apply `tdd-workflow`.

**Unit tests:**
- Chunk boundary, overlap, parent expansion, and deterministic ID behavior.
- Collection config and payload index creation plan.
- Required Qdrant payload fields.
- Evidence conversion preserves citations and scores.
- Vietnamese normalization and diacritic-insensitive keyword keys.
- Production readiness rejects dense-only mode.

**Integration tests:**
- Qdrant service retrieval with hard filters.
- Native hybrid retrieval returns exact-code matches that dense-only misses.
- Parent expansion returns parent section text, not only child text.
- Company-specific query cannot retrieve another company when a hard filter exists.
- Exact keyword query returns the expected document even when dense similarity is weak.
- Degraded dense-only mode logs `retrieval_degraded=true` and fails production readiness checks.

**E2E tests:** None until Supervisor and specialist workflows exist.

## 8. Debug Va Kiem Tra

**Reproduce common failures:**
- Run `pytest tests/integration/test_qdrant_retriever_filters.py -v`.
- Run `pytest tests/integration/test_qdrant_hybrid_retriever.py -v`.
- Inspect collection schema and confirm named dense/sparse vectors exist.
- Inspect one indexed point payload through Qdrant client and verify citation fields.
- Query with and without `company_code` hard filter and compare returned companies.

**Verification before next phase:**
- `pytest tests/unit/test_document_chunker.py tests/unit/test_qdrant_collection_manager.py tests/unit/test_qdrant_evidence_adapter.py tests/unit/test_retrieval_readiness.py -v`
- `pytest tests/integration/test_qdrant_retriever_filters.py tests/integration/test_qdrant_hybrid_retriever.py -v`
- `ruff check src tests scripts/06_db_ingestion`
- `ruff format --check src tests scripts/06_db_ingestion`

## 9. Execution Task Breakdown

### Task 1: Chunking And Citation Payload Contracts

**Files:**
- Create: `src/services/document_chunker.py`
- Create: `src/services/qdrant_evidence_adapter.py`
- Test: `tests/unit/test_document_chunker.py`
- Test: `tests/unit/test_qdrant_evidence_adapter.py`

- [ ] Step 1: Write failing tests for parent/child chunking, deterministic IDs, Vietnamese normalization, and required payload fields.
- [ ] Step 2: Implement chunking, payload validation, and evidence conversion.
- [ ] Step 3: Run `pytest tests/unit/test_document_chunker.py tests/unit/test_qdrant_evidence_adapter.py -v`; expected PASS.

### Task 2: Qdrant Collection And Readiness Gate

**Files:**
- Create: `src/services/qdrant_collection_manager.py`
- Create: `src/services/retrieval_readiness.py`
- Test: `tests/unit/test_qdrant_collection_manager.py`
- Test: `tests/unit/test_retrieval_readiness.py`

- [ ] Step 1: Write failing tests for named vectors, sparse vectors, payload indexes, and dense-only production rejection.
- [ ] Step 2: Implement Qdrant collection setup and readiness checks.
- [ ] Step 3: Run `pytest tests/unit/test_qdrant_collection_manager.py tests/unit/test_retrieval_readiness.py -v`; expected PASS.

### Task 3: LangChain Hybrid Retriever

**Files:**
- Create: `src/services/qdrant_retriever.py`
- Test: `tests/integration/test_qdrant_retriever_filters.py`
- Test: `tests/integration/test_qdrant_hybrid_retriever.py`

- [ ] Step 1: Write failing tests for hard filters, dense retrieval, sparse retrieval, hybrid ranking, parent expansion, and degraded-mode rejection.
- [ ] Step 2: Implement `QdrantRetriever` with `QdrantVectorStore`, `RetrievalMode.HYBRID`, strict filter construction, and score-preserving evidence output.
- [ ] Step 3: Run `pytest tests/integration/test_qdrant_retriever_filters.py tests/integration/test_qdrant_hybrid_retriever.py -v`; expected PASS.

### Task 4: Indexing Script

**Files:**
- Create: `scripts/06_db_ingestion/04_index_qdrant_documents.py`

- [ ] Step 1: Add dry-run indexing with JSON logging, ID validation, collection readiness check, and idempotent batch upsert plan.
- [ ] Step 2: Run dry-run against fixture documents; expected logs include document count, parent section count, child chunk count, skipped duplicate count, and readiness result.
