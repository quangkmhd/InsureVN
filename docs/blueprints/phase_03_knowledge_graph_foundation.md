# Phase 03: Knowledge Graph Foundation

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` or `superpowers:executing-plans` to implement this plan task-by-task. Apply `tdd-workflow` for every code change.

> **Phase Mapping:** This is Blueprint Phase 03 = Design Spec Phase 2b (Knowledge Graph Construction). See `docs/2026-05-03-insurevn-multi-agent-platform-design.md` Section 5, Phase 2b.

### Dependencies

New packages to install:
- `networkx` — in-memory graph construction and traversal

## 1. Thong Tin Chung

**Muc tieu cot loi:** Build the relationship canonical source with NetworkX, seeded from SQLite and enriched later from document chunks, so agents can reason over plan-benefit-exclusion-waiting-period paths.

**Definition of Done:**
- NetworkX graph builds from existing SQLite tables at startup or via a build script.
- Graph entities and relationships match the design spec: Company, Plan, Benefit, Exclusion, WaitingPeriod, Condition, Hospital, GlossaryTerm, ClaimEvent.
- Graph can serialize to and reload from JSON with identical traversal results.
- `GraphRetriever` returns N-hop relationship evidence as `Evidence(source_type="graph_triple")`.
- Graph quality checks catch orphan nodes and relationship count mismatches.

## 2. Scope

**Can lam:**
- Build deterministic SQLite-to-graph extraction.
- Implement traversal patterns for Company->Plan, Plan->Exclusion->Condition, Plan->WaitingPeriod, and Plan->Hospital.
- Add graph evidence adapter and quality validator.

**Khong duoc lam trong phase nay:**
- Do not migrate to Neo4j.
- Do not rely on LLM-extracted graph triples as the primary graph source.
- Do not implement GraphRAG synthesis or specialist answers.
- Do not create claim decisions from graph output alone.

## 3. Kien Truc Va Cong Nghe

**Framework selection:** Use pure Python and NetworkX for the graph store. LangChain may be used only for future-compatible retriever interfaces; LangGraph is deferred to routing phases.

**Files to create:**
- `src/services/knowledge_graph/builder.py`
- `src/services/knowledge_graph/retriever.py`
- `src/services/knowledge_graph/serializer.py`
- `src/services/knowledge_graph/quality.py`
- `src/services/knowledge_graph/evidence_adapter.py`
- `scripts/06_db_ingestion/05_build_knowledge_graph.py`
- `tests/unit/test_knowledge_graph_builder.py`
- `tests/unit/test_graph_retriever.py`
- `tests/unit/test_graph_quality.py`
- `tests/integration/test_knowledge_graph_sqlite_build.py`

**Files to modify:**
- `src/core/config.py`: add `GRAPH_JSON_PATH`, `GRAPH_MAX_HOPS`, and `GRAPH_RELOAD_ON_STARTUP` with explicit types.
- `.env`: register graph settings.

**Tools/MCP/DB:**
- SQLite is the deterministic source for graph seeding.
- Qdrant chunks from Phase 02 are optional inputs only for later LLM-assisted enrichment and must not block this phase.

## 4. Data Flow

**Input:**
- SQLite tables: companies, plan types, benefit items/values, glossary terms, waiting periods, claim payouts, hospitals, documents.
- Optional parsed exclusion text from benefit notes.

**Output:**
- `data/processed/knowledge_graph/insurevn_graph.json` or configured equivalent.
- Graph traversal results as paths and triples.
- Evidence objects containing `graph_path`, relationship type, source table lineage, and confidence.

## 5. Huong Dan Trien Khai

1. Write failing unit tests with a tiny in-memory SQLite fixture for Company, Plan, Benefit, WaitingPeriod, and Hospital.
2. Implement graph node naming with stable searchable IDs, for example `company:AIA`, `plan:AIA:gold`, `benefit:inpatient`.
3. Write failing relationship extraction tests for `OFFERS`, `INCLUDES`, `HAS_WAITING_PERIOD`, `USES_NETWORK`, and `GOVERNED_BY`.
4. Implement `KnowledgeGraphBuilder.build_from_sqlite(connection)` using explicit extractor functions per entity type.
5. Write failing serialization tests that compare traversal outputs before and after JSON reload.
6. Implement JSON serialization with node attributes and edge attributes preserved.
7. Write failing traversal tests for N-hop plan exclusion and waiting period paths.
8. Implement `GraphRetriever.retrieve(start_entities, relation_types, max_hops)`.
9. Write failing quality tests for orphan nodes and minimum relationship counts.
10. Implement `GraphQualityValidator.validate(graph, sqlite_counts)`.
11. Add build script with dry-run, output path, and quality report options.

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
- Relationship extraction from foreign keys.
- Graph serialization and reload.
- Traversal correctness.
- Quality validation.

**Integration tests:**
- Build from a temporary or fixture SQLite database.
- Relationship counts align with SQLite counts within the documented tolerance.
- Multi-hop traversal returns within 100ms on fixture scale.

**E2E tests:** None until phase 05.

## 8. Debug Va Kiem Tra

**Reproduce common failures:**
- Run `pytest tests/unit/test_graph_retriever.py -v`.
- Dump a specific node neighborhood with `GraphRetriever.explain_path(...)`.
- Compare `relationship_type_counts` against SQL count queries.

**Verification before next phase:**
- `pytest tests/unit/test_knowledge_graph_builder.py tests/unit/test_graph_retriever.py tests/unit/test_graph_quality.py -v`
- `pytest tests/integration/test_knowledge_graph_sqlite_build.py -v`
- `ruff check src tests scripts/06_db_ingestion`
- `ruff format --check src tests scripts/06_db_ingestion`

## 9. Execution Task Breakdown

### Task 1: Graph Builder And Stable IDs

**Files:**
- Create: `src/services/knowledge_graph/builder.py`
- Test: `tests/unit/test_knowledge_graph_builder.py`

- [ ] Step 1: Write failing SQLite fixture tests for entity and relationship extraction.
- [ ] Step 2: Implement deterministic node IDs and edge extraction.
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
- Create: `scripts/06_db_ingestion/05_build_knowledge_graph.py`
- Test: `tests/unit/test_graph_quality.py`
- Test: `tests/integration/test_knowledge_graph_sqlite_build.py`

- [ ] Step 1: Write failing quality tests for orphan nodes and relationship counts.
- [ ] Step 2: Implement validator and build script with dry-run report.
- [ ] Step 3: Run Phase 03 unit and integration tests; expected PASS.
