# Phase 03: Knowledge Graph Foundation

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` or `superpowers:executing-plans` to implement this plan task-by-task. Apply `tdd-workflow` for every code change.

> **Phase Mapping:** This is Blueprint Phase 03 = Design Spec Phase 2b (Knowledge Graph Construction). See `docs/architecture/2026-05-03-multi-agent-platform-design.md` Section 5, Phase 2b.

### Dependencies

New packages to install:
- `langchain-neo4j` — first-choice LangChain integration for Neo4j graph access, graph documents, Cypher QA, and Neo4j vector/hybrid retrieval.
- `neo4j` — official Neo4j Python driver used for constraints, admin checks, and integration tests.
- `langchain-graph-retriever` — LangChain Graph RAG retriever with `GraphRetriever` and traversal strategies such as `Eager`.
- `networkx` — in-memory fixture graph and unit-test fallback only; not the production graph store.

Existing project packages used in this phase:
- `langchain` / `langchain-core` — `Document`, `GraphDocument`, retriever interfaces, structured output, and callbacks.
- `langgraph` — optional durable graph-build workflow when extraction/import needs checkpointing or retry boundaries.
- `deepagents` — optional developer/operator shell for long-running graph curation tasks; production retrieval remains explicit LangChain/Neo4j services.
- `langfuse` — tracing metadata target exposed through retrieval metadata.

## 1. Thong Tin Chung

**Muc tieu cot loi:** Build the production relationship canonical source in Neo4j and expose graph evidence through LangChain-compatible retrievers. Use `langchain-neo4j` for persisted domain graph storage, `langchain-graph-retriever` with `Eager` traversal for metadata-neighborhood retrieval over Qdrant/LangChain documents, and deterministic adapters that return `Evidence(source_type="graph_triple")`.

**Definition of Done:**
- Neo4j is the production graph store with schema constraints, indexes, idempotent imports, and fixture-backed integration tests.
- NetworkX is limited to fast unit fixtures and local algorithm checks. It is not the target product architecture.
- Graph entities and relationships match the document GraphRAG scope: Company, Document, Plan, Benefit, Exclusion, WaitingPeriod, Condition, Hospital, GlossaryTerm, ClaimEvent, Section, Chunk.
- Graph construction uses Qdrant chunk payloads, parsed Markdown/PDF text, and SQLite canonical IDs for validation. SQLite validates identity and structured facts; it does not replace document-grounded graph evidence.
- `GraphRetriever` is implemented in two complementary modes:
  - `DocumentGraphRetriever`: LangChain `GraphRetriever` from `langchain-graph-retriever` over Qdrant/LangChain document metadata using `Eager`.
  - `Neo4jGraphRetriever`: Neo4j/Cypher traversal for persisted entity relationships and evidence paths.
- All graph output preserves document/chunk lineage, page/section citation, confidence, extraction method, and graph path.
- Graph quality checks catch orphan nodes, missing document lineage, dangling Qdrant chunk references, invalid relationship types, duplicate entities, low-confidence triples, and Neo4j constraint/index drift.

## 2. Scope

**Can lam:**
- Build document-to-graph extraction from Markdown files, converted PDF text, and Qdrant chunk metadata.
- Persist the relationship graph to Neo4j with constraints and indexes.
- Implement `GraphDocument` conversion and Neo4j import through `langchain-neo4j` where possible.
- Implement traversal patterns for Company->Plan, Plan->Exclusion->Condition, Plan->WaitingPeriod, Plan->Hospital, Document->Section->Chunk, and ClaimEvent->Benefit/Exclusion.
- Implement LangChain Graph RAG over existing Qdrant/LangChain documents using `GraphRetriever` and `Eager`.
- Add graph evidence adapters, quality validators, and production readiness checks.

**Khong duoc lam trong phase nay:**
- Do not keep NetworkX as the production storage choice.
- Do not accept unconstrained LLM-extracted triples. Extraction must use allowed node labels, allowed relationship types, confidence scores, and citation lineage to document chunks.
- Do not allow LLM-generated Cypher to run unrestricted. Any GraphCypherQAChain usage must be schema-scoped, read-only, logged, and excluded from claim decisions until separately approved.
- Do not implement final specialist answers or claim decisions.
- Do not create claim decisions from graph output alone.
- Do not introduce a second vector canonical source in Neo4j that competes with Qdrant. Neo4j vector/hybrid search may be used for graph node discovery, but Qdrant remains the document text canonical store.

## 3. Kien Truc Va Cong Nghe

**Framework selection:** Use LangChain/Neo4j first. Use `langchain-neo4j.Neo4jGraph`, `GraphDocument`, and `Neo4jVector` where they cover the need. Use `langchain-graph-retriever.GraphRetriever` with `graph_retriever.strategies.Eager` for document metadata traversal on top of the Phase 02 vector store. Use direct Neo4j driver/Cypher only for constraints, indexes, deterministic traversals, and tests that integration packages do not cover. Use LangGraph only for durable build workflows. Use Deep Agents only as an operator/developer shell for graph curation, not as the production retrieval engine.

**Graph storage model:**
- Neo4j labels:
  - `Company`
  - `Document`
  - `Plan`
  - `Benefit`
  - `Exclusion`
  - `WaitingPeriod`
  - `Condition`
  - `Hospital`
  - `GlossaryTerm`
  - `ClaimEvent`
  - `Section`
  - `Chunk`
- Relationship types:
  - `OFFERS`
  - `INCLUDES`
  - `EXCLUDES`
  - `APPLIES_TO`
  - `HAS_WAITING_PERIOD`
  - `USES_NETWORK`
  - `DOCUMENT_DEFINES`
  - `DOCUMENT_CONTAINS`
  - `SECTION_CONTAINS`
  - `MENTIONED_IN`
  - `COVERS`
  - `GOVERNED_BY`
  - `BLOCKED_BY`
- Required relationship properties:
  - `source_document_id`
  - `source_chunk_id`
  - `source_path`
  - `page_number`
  - `section_type`
  - `confidence`
  - `extraction_method`
  - `ingestion_version`

**GraphRetriever modes:**
- `DocumentGraphRetriever`:
  - Wraps the Phase 02 LangChain/Qdrant vector store.
  - Uses `GraphRetriever(store=<qdrant_vector_store>, edges=[...], strategy=Eager(k=<...>, start_k=<...>, max_depth=<...>))`.
  - Traverses metadata edges such as `company_code`, `document_id`, `plan_code`, `section_type`, `parent_section_id`, and `source_table_id`.
  - Used for neighborhood expansion around retrieved documents/chunks.
- `Neo4jGraphRetriever`:
  - Runs deterministic read-only Cypher templates against Neo4j.
  - Traverses persisted relationship paths and returns typed triples/paths.
  - Used for insurance relationship reasoning: plan exclusions, waiting periods, covered conditions, hospital networks, claim-event blockers.

**Files to create:**
- `src/services/knowledge_graph/schema.py`: allowed labels, relationship types, constraints, indexes, and stable ID rules.
- `src/services/knowledge_graph/document_extractor.py`: strict document-grounded entity/triple extraction.
- `src/services/knowledge_graph/graph_document_adapter.py`: converts extracted entities/triples to LangChain `GraphDocument` objects.
- `src/services/knowledge_graph/neo4j_store.py`: Neo4j connection, constraints, indexes, imports, and health checks.
- `src/services/knowledge_graph/document_graph_retriever.py`: LangChain GraphRetriever + Eager over Qdrant document metadata.
- `src/services/knowledge_graph/neo4j_graph_retriever.py`: deterministic Cypher traversal retriever.
- `src/services/knowledge_graph/evidence_adapter.py`: graph paths/triples to shared `Evidence`.
- `src/services/knowledge_graph/quality.py`: graph quality and production readiness validator.
- `scripts/04_extraction/05_build_knowledge_graph.py`: graph build/import CLI.
- `tests/unit/test_knowledge_graph_schema.py`
- `tests/unit/test_knowledge_graph_document_extractor.py`
- `tests/unit/test_graph_document_adapter.py`
- `tests/unit/test_document_graph_retriever.py`
- `tests/unit/test_neo4j_graph_retriever.py`
- `tests/unit/test_graph_quality.py`
- `tests/integration/test_neo4j_knowledge_graph_import.py`
- `tests/integration/test_knowledge_graph_document_build.py`

**Files to modify:**
- `src/core/config.py`: add `GRAPH_*`, `NEO4J_*`, graph retriever, Eager traversal, confidence, timeout, retry, and readiness settings with explicit casts.
- `.env`: register graph and Neo4j settings with comments.
- `CICD/docker-compose.yml`: add local Neo4j service if absent.
- `docs/blueprints/dependency_matrix.md`: track Neo4j, LangChain graph retriever, and graph packages.

**Tools/MCP/DB:**
- Qdrant chunks from Phase 02 are the primary document-grounding input for graph construction.
- SQLite is used for canonical ID validation, conflict detection, and structured fact cross-checks.
- Neo4j stores the production relationship graph.

## 4. Data Flow

**Input:**
- Markdown documents and converted PDF text from `data/processed`.
- Qdrant chunk payloads from Phase 02, including `company_code`, `document_id`, `document_name`, `plan_code`, `section_type`, `page_number`, `chunk_index`, `parent_section_id`, `source_path`, and `source_table_id`.
- SQLite lookups for canonical IDs and relationship validation.
- Optional LLM-assisted extraction output constrained by the schema in `knowledge_graph/schema.py`.

**Build output:**
- Neo4j nodes, relationships, constraints, and indexes.
- Import quality report in `data/processed/knowledge_graph/quality_report.json`.
- Optional JSON export snapshot for review/debugging, not as the production store.

**Retrieval output:**
- Document neighborhood results from LangChain `GraphRetriever`/`Eager`.
- Neo4j relationship paths and triples.
- Evidence objects containing `graph_path`, relationship type, document/chunk lineage, page or section citation, confidence, extraction method, and query metadata.

## 5. Huong Dan Trien Khai

1. Write failing schema tests for allowed labels, relationship types, stable node IDs, required properties, Neo4j uniqueness constraints, and index definitions.
2. Implement `knowledge_graph/schema.py` with deterministic IDs such as `company:AIA`, `document:aia_health_2026`, `plan:AIA:gold`, `chunk:aia_health_2026:12`.
3. Write failing document extraction tests with tiny Markdown/PDF-converted fixtures for Company, Document, Plan, Benefit, Exclusion, Condition, WaitingPeriod, Hospital, GlossaryTerm, ClaimEvent, Section, and Chunk.
4. Implement strict extractor functions per entity and relationship type. LLM-assisted extraction must produce schema-validated Pydantic objects and include confidence plus chunk citation.
5. Write failing `GraphDocument` adapter tests verifying nodes, relationships, and source document linkage.
6. Implement `GraphDocument` conversion and Neo4j import payloads using `langchain-neo4j` where possible.
7. Write failing Neo4j store tests for connection config, health checks, uniqueness constraints, indexes, idempotent imports, and duplicate handling.
8. Implement `Neo4jKnowledgeGraphStore` with direct driver/Cypher for constraints and `Neo4jGraph.add_graph_documents(...)` for graph document import when appropriate.
9. Write failing `DocumentGraphRetriever` tests requiring `GraphRetriever` with `Eager(k, start_k, max_depth)` over metadata edges from Qdrant/LangChain documents.
10. Implement `DocumentGraphRetriever` with configurable metadata edges and result conversion to evidence.
11. Write failing `Neo4jGraphRetriever` tests for N-hop plan exclusion paths, waiting-period paths, hospital network paths, and read-only Cypher template enforcement.
12. Implement deterministic Cypher traversal templates and `Neo4jGraphRetriever.retrieve(start_entities, relation_types, max_hops)`.
13. Write failing evidence adapter tests for graph path, relationship type, source chunk lineage, page/section citation, and confidence preservation.
14. Implement graph evidence conversion to `Evidence(source_type="graph_triple")`.
15. Write failing quality tests for orphan nodes, missing chunk citations, dangling Qdrant references, low-confidence triples, invalid relationship types, duplicate entities, and Neo4j schema drift.
16. Implement `GraphQualityValidator.validate(...)` and a production readiness gate.
17. Add build script with dry-run, Qdrant payload export input, SQLite validation, Neo4j import, quality report, JSON snapshot option, and optional LangGraph checkpointing for long imports.

## 6. Observability

**Log format:** JSON.

**Required log metadata:**
- `component`: `knowledge_graph_schema`, `knowledge_graph_extractor`, `neo4j_store`, `document_graph_retriever`, `neo4j_graph_retriever`, or `graph_quality`
- `neo4j_database`
- `node_count`
- `edge_count`
- `entity_type_counts`
- `relationship_type_counts`
- `orphan_count`
- `low_confidence_count`
- `dangling_chunk_reference_count`
- `query_start_entity`
- `query_relation_types`
- `max_hops`
- `eager_k`
- `eager_start_k`
- `eager_max_depth`
- `latency_ms`
- `readiness_passed`

**Langfuse tracking:** Return graph query metadata, Cypher template ID, traversal mode, and `graph_path` citations for Phase 04 LangGraph nodes to attach to Langfuse observations. Do not create Langfuse traces directly inside graph services.

## 7. Testing Strategy

Apply `tdd-workflow`.

**Unit tests:**
- Schema labels, relationship types, required properties, constraints, and indexes.
- Entity extraction and stable node IDs.
- Relationship extraction from document sections and Qdrant chunk payloads.
- `GraphDocument` conversion and source document linkage.
- LangChain `GraphRetriever`/`Eager` metadata traversal behavior.
- Neo4j Cypher template selection and traversal correctness.
- Evidence conversion and citation preservation.
- Quality validation.

**Integration tests:**
- Neo4j service starts through local compose/test fixture.
- Constraints and indexes are created idempotently.
- Build from fixture Markdown, converted PDF text, and fixture Qdrant chunk payloads.
- Multi-hop traversal returns expected paths for exclusions, waiting periods, and hospital network membership.
- Extracted relationship counts align with document fixture expectations within the documented confidence threshold.
- DocumentGraphRetriever returns Qdrant metadata neighbors within configured `Eager` limits.

**E2E tests:** None until Phase 05 specialist workflows consume graph evidence.

## 8. Debug Va Kiem Tra

**Reproduce common failures:**
- Run `pytest tests/unit/test_document_graph_retriever.py -v`.
- Run `pytest tests/unit/test_neo4j_graph_retriever.py -v`.
- Query Neo4j constraints/indexes and compare with `knowledge_graph/schema.py`.
- Dump a specific node neighborhood with `Neo4jGraphRetriever.explain_path(...)`.
- Compare `relationship_type_counts` against expected fixture counts and inspect cited chunk lineage.

**Verification before next phase:**
- `pytest tests/unit/test_knowledge_graph_schema.py tests/unit/test_knowledge_graph_document_extractor.py tests/unit/test_graph_document_adapter.py -v`
- `pytest tests/unit/test_document_graph_retriever.py tests/unit/test_neo4j_graph_retriever.py tests/unit/test_graph_quality.py -v`
- `pytest tests/integration/test_neo4j_knowledge_graph_import.py tests/integration/test_knowledge_graph_document_build.py -v`
- `ruff check src tests scripts/04_extraction`
- `ruff format --check src tests scripts/04_extraction`

## 9. Execution Task Breakdown

### Task 1: Schema, Stable IDs, And Extraction Contracts

**Files:**
- Create: `src/services/knowledge_graph/schema.py`
- Create: `src/services/knowledge_graph/document_extractor.py`
- Test: `tests/unit/test_knowledge_graph_schema.py`
- Test: `tests/unit/test_knowledge_graph_document_extractor.py`

- [ ] Step 1: Write failing tests for allowed labels, relationship types, required properties, stable IDs, and document-grounded entity extraction.
- [ ] Step 2: Implement schema constants, ID builders, and strict extraction contracts.
- [ ] Step 3: Run `pytest tests/unit/test_knowledge_graph_schema.py tests/unit/test_knowledge_graph_document_extractor.py -v`; expected PASS.

### Task 2: GraphDocument Adapter And Neo4j Store

**Files:**
- Create: `src/services/knowledge_graph/graph_document_adapter.py`
- Create: `src/services/knowledge_graph/neo4j_store.py`
- Test: `tests/unit/test_graph_document_adapter.py`
- Test: `tests/integration/test_neo4j_knowledge_graph_import.py`

- [ ] Step 1: Write failing tests for `GraphDocument` conversion, source document linkage, Neo4j constraints, indexes, and idempotent imports.
- [ ] Step 2: Implement adapter and Neo4j store using `langchain-neo4j` plus direct driver calls for schema management.
- [ ] Step 3: Run `pytest tests/unit/test_graph_document_adapter.py tests/integration/test_neo4j_knowledge_graph_import.py -v`; expected PASS.

### Task 3: Document GraphRetriever With Eager

**Files:**
- Create: `src/services/knowledge_graph/document_graph_retriever.py`
- Test: `tests/unit/test_document_graph_retriever.py`

- [ ] Step 1: Write failing tests requiring LangChain `GraphRetriever` over Qdrant/LangChain documents with `Eager(k, start_k, max_depth)` and metadata edges.
- [ ] Step 2: Implement document metadata traversal and evidence conversion hooks.
- [ ] Step 3: Run `pytest tests/unit/test_document_graph_retriever.py -v`; expected PASS.

### Task 4: Neo4j GraphRetriever And Evidence

**Files:**
- Create: `src/services/knowledge_graph/neo4j_graph_retriever.py`
- Create: `src/services/knowledge_graph/evidence_adapter.py`
- Test: `tests/unit/test_neo4j_graph_retriever.py`

- [ ] Step 1: Write failing traversal and evidence tests for plan exclusions, waiting periods, hospital networks, and claim-event blockers.
- [ ] Step 2: Implement read-only Cypher template retrieval and graph evidence conversion.
- [ ] Step 3: Run `pytest tests/unit/test_neo4j_graph_retriever.py -v`; expected PASS.

### Task 5: Quality Gate And Build Script

**Files:**
- Create: `src/services/knowledge_graph/quality.py`
- Create: `scripts/04_extraction/05_build_knowledge_graph.py`
- Test: `tests/unit/test_graph_quality.py`
- Test: `tests/integration/test_knowledge_graph_document_build.py`

- [ ] Step 1: Write failing quality tests for orphan nodes, missing citations, dangling chunk references, low-confidence triples, duplicate entities, invalid relationships, and Neo4j schema drift.
- [ ] Step 2: Implement validator and build script with dry-run report, SQLite validation, Qdrant payload input, Neo4j import, and optional JSON snapshot.
- [ ] Step 3: Run Phase 03 unit and integration tests; expected PASS.
