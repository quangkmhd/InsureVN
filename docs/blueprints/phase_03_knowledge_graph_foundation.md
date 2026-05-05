# Phase 03: Knowledge Graph Foundation

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` or `superpowers:executing-plans` to implement this plan task-by-task. Apply `tdd-workflow` for every code change.

> **Phase Mapping:** This is Blueprint Phase 03 = Design Spec Phase 2b (Knowledge Graph Construction). See `docs/2026-05-03-insurevn-multi-agent-platform-design.md` Section 5, Phase 2b.

### Dependencies

New packages to install:
- `networkx` — in-memory graph construction and traversal

## 1. Thong Tin Chung

**Muc tieu cot loi:** Build the document-derived relationship canonical source with NetworkX from Markdown/PDF-derived policy chunks, so RAG and GraphRAG retrieval can reason over plan-benefit-exclusion-condition-waiting-period paths grounded in source documents.

**Definition of Done:**
- NetworkX graph builds from normalized Markdown text, converted PDF text, and Phase 02 Qdrant chunk payloads at startup or via a build script.
- Graph entities and relationships match the document GraphRAG scope: Company, Document, Plan, Benefit, Exclusion, WaitingPeriod, Condition, Hospital, GlossaryTerm, ClaimEvent, Section, Chunk.
- Graph can serialize to and reload from JSON with identical traversal results.
- `GraphRetriever` returns N-hop relationship evidence as `Evidence(source_type="graph_triple")`.
- Graph quality checks catch orphan nodes, missing document lineage, dangling chunk references, and low-confidence extracted triples.

## 2. Scope

**Can lam:**
- Build document-to-graph extraction from Markdown files, converted PDF text, and Qdrant chunk metadata.
- Implement traversal patterns for Company->Plan, Plan->Exclusion->Condition, Plan->WaitingPeriod, and Plan->Hospital.
- Add graph evidence adapter and quality validator.

**Khong duoc lam trong phase nay:**
- Do not migrate to Neo4j.
- Do not use SQLite as the primary source for graph construction; SQLite remains a separate structured facts retriever.
- Do not accept unconstrained LLM-extracted triples. Extraction must use strict allowed nodes, allowed relationships, confidence scores, and citation lineage to document chunks.
- Do not implement final specialist answers.
- Do not create claim decisions from graph output alone.

## 3. Kien Truc Va Cong Nghe

**Framework selection:** Use pure Python and NetworkX for the graph store. LangChain may be used only for future-compatible retriever interfaces; LangGraph is deferred to routing phases.

**Files to create:**
- `src/services/knowledge_graph/builder.py`
- `src/services/knowledge_graph/document_extractor.py`
- `src/services/knowledge_graph/retriever.py`
- `src/services/knowledge_graph/serializer.py`
- `src/services/knowledge_graph/quality.py`
- `src/services/knowledge_graph/evidence_adapter.py`
- `scripts/04_extraction/05_build_knowledge_graph.py`
- `tests/unit/test_knowledge_graph_builder.py`
- `tests/unit/test_knowledge_graph_document_extractor.py`
- `tests/unit/test_graph_retriever.py`
- `tests/unit/test_graph_quality.py`
- `tests/integration/test_knowledge_graph_document_build.py`

**Files to modify:**
- `src/core/config.py`: add `GRAPH_JSON_PATH`, `GRAPH_MAX_HOPS`, and `GRAPH_RELOAD_ON_STARTUP` with explicit types.
- `.env`: register graph settings.

**Tools/MCP/DB:**
- Markdown files, PDF-converted text, and Qdrant chunks from Phase 02 are the primary sources for graph seeding.
- SQLite may be used only for validation, ID alignment, or structured fact cross-checks. It must not drive the graph topology in this phase.

## 4. Data Flow

**Input:**
- Markdown documents and converted PDF text from `data/processed`.
- Qdrant chunk payloads from Phase 02, including `company_code`, `document_id`, `document_name`, `plan_code`, `section_type`, `page_number`, `chunk_index`, and `source_path`.
- Optional SQLite lookups only for canonical ID validation and source alignment.

**Output:**
- `data/processed/knowledge_graph/insurevn_graph.json` or configured equivalent.
- Graph traversal results as paths and triples.
- Evidence objects containing `graph_path`, relationship type, document/chunk lineage, page or section citation, and confidence.

## 5. Huong Dan Trien Khai

1. Write failing unit tests with tiny Markdown/PDF-converted text fixtures for Company, Document, Plan, Benefit, Exclusion, Condition, WaitingPeriod, and Hospital.
2. Implement graph node naming with stable searchable IDs, for example `company:AIA`, `document:aia_health_2026`, `plan:AIA:gold`, `chunk:aia_health_2026:12`.
3. Write failing relationship extraction tests for `DOCUMENT_DEFINES`, `OFFERS`, `INCLUDES`, `EXCLUDES`, `APPLIES_TO`, `HAS_WAITING_PERIOD`, `USES_NETWORK`, and `MENTIONED_IN`.
4. Implement `KnowledgeGraphBuilder.build_from_documents(documents, chunks)` using explicit extractor functions per entity type and strict allowed relationship types.
5. Write failing serialization tests that compare traversal outputs before and after JSON reload.
6. Implement JSON serialization with node attributes and edge attributes preserved.
7. Write failing traversal tests for N-hop plan exclusion and waiting period paths.
8. Implement `GraphRetriever.retrieve(start_entities, relation_types, max_hops)`.
9. Write failing quality tests for orphan nodes, missing chunk citations, confidence thresholds, and invalid relationship types.
10. Implement `GraphQualityValidator.validate(graph, document_counts, chunk_counts)`.
11. Add build script with dry-run, input document path, Qdrant payload export path, output path, and quality report options.

## 6. Observability

**Log format:** JSON.

**Required log metadata:**
- `component`: `knowledge_graph_builder`, `graph_retriever`, `graph_quality`
- `node_count`
- `edge_count`
- `entity_type_counts`
- `relationship_type_counts`
- `orphan_count`
- `query_start_entity`
- `query_relation_types`
- `max_hops`
- `latency_ms`

**Langfuse tracking:** No direct trace creation in graph services. Later LangGraph retriever nodes should attach graph query metadata and `graph_path` citations to Langfuse observations.

## 7. Testing Strategy

Apply `tdd-workflow`.

**Unit tests:**
- Entity extraction and stable node IDs.
- Relationship extraction from document sections and chunk payloads.
- Graph serialization and reload.
- Traversal correctness.
- Quality validation.

**Integration tests:**
- Build from fixture Markdown and converted PDF text plus fixture Qdrant chunk payloads.
- Extracted relationship counts align with document fixture expectations within the documented confidence threshold.
- Multi-hop traversal returns within 100ms on fixture scale.

**E2E tests:** None until phase 05.

## 8. Debug Va Kiem Tra

**Reproduce common failures:**
- Run `pytest tests/unit/test_graph_retriever.py -v`.
- Dump a specific node neighborhood with `GraphRetriever.explain_path(...)`.
- Compare `relationship_type_counts` against expected document fixture counts and inspect cited chunk lineage.

**Verification before next phase:**
- `pytest tests/unit/test_knowledge_graph_builder.py tests/unit/test_graph_retriever.py tests/unit/test_graph_quality.py -v`
- `pytest tests/unit/test_knowledge_graph_document_extractor.py tests/integration/test_knowledge_graph_document_build.py -v`
- `ruff check src tests scripts/04_extraction`
- `ruff format --check src tests scripts/04_extraction`

## 9. Execution Task Breakdown

### Task 1: Document Extractor, Graph Builder, And Stable IDs

**Files:**
- Create: `src/services/knowledge_graph/document_extractor.py`
- Create: `src/services/knowledge_graph/builder.py`
- Test: `tests/unit/test_knowledge_graph_document_extractor.py`
- Test: `tests/unit/test_knowledge_graph_builder.py`

- [ ] Step 1: Write failing Markdown/PDF-converted text fixture tests for entity and relationship extraction.
- [ ] Step 2: Implement deterministic node IDs and document-grounded edge extraction.
- [ ] Step 3: Run `pytest tests/unit/test_knowledge_graph_builder.py -v`; expected PASS.

### Task 2: Serialization, Retrieval, And Evidence

**Files:**
- Create: `src/services/knowledge_graph/retriever.py`
- Create: `src/services/knowledge_graph/serializer.py`
- Create: `src/services/knowledge_graph/evidence_adapter.py`
- Test: `tests/unit/test_graph_retriever.py`

- [ ] Step 1: Write failing traversal and reload tests.
- [ ] Step 2: Implement JSON serialization, N-hop traversal, and graph evidence conversion.
- [ ] Step 3: Run `pytest tests/unit/test_graph_retriever.py -v`; expected PASS.

### Task 3: Quality Gate And Build Script

**Files:**
- Create: `src/services/knowledge_graph/quality.py`
- Create: `scripts/04_extraction/05_build_knowledge_graph.py`
- Test: `tests/unit/test_graph_quality.py`
- Test: `tests/integration/test_knowledge_graph_document_build.py`

- [ ] Step 1: Write failing quality tests for orphan nodes, missing citations, low-confidence triples, and relationship counts.
- [ ] Step 2: Implement validator and document build script with dry-run report.
- [ ] Step 3: Run Phase 03 unit and integration tests; expected PASS.
