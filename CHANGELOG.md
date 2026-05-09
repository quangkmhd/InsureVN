# Changelog

All notable changes to the InsureVN project will be documented in this file.

## [Unreleased] - 2026-05-09

### ✨ New Features

- **Adaptive Semantic Density Chunking**: Implemented a new chunking strategy with an associated benchmark suite and comparison API for optimizing document retrieval.
- **RAG Evaluation Framework**: Launched a core evaluation framework and LLM infrastructure, including the Health RAG Context Benchmark v2 and specialized benchmarks for health insurance.
- **Databricks Chunking Integration**: Integrated Databricks chunking strategies to enhance document processing and retrieval quality.
- **Chunking Comparison Playground**: Introduced a tool and infrastructure for side-by-side comparison of different chunking strategies.
- **GraphRAG Framework Integration**: Integrated the GraphRAG LangChain framework with custom retrieval and schema configuration for multi-hop reasoning.
- **Quad-Retrieval Engine**: Integrated Qdrant and Knowledge Graph retrieval systems to support advanced document exploration and multi-dimensional search within LangChain.
- **Evidence Management System**: Built an end-to-end evidence architecture including adapters, mergers, citation formatters, and document chunk contracts.
- **Knowledge Graph Foundation**: Implemented a SQLite-based builder and foundation for the application's document knowledge graph.
- **Synthetic Schema Expansion**: Expanded the database schema with synthetic tables to enhance testing and simulation environments.

### 🔧 Improvements

- **Knowledge Graph Pipeline Refactor**: Reorganized the knowledge graph schema discovery and build pipeline to improve efficiency and maintainability.
- **Standardized Agent Configuration**: Established a robust, prefix-based configuration architecture with dedicated, isolated parameters managed through a centralized `Settings` registry.
- **Parameter Standardization**: Renamed `RAG_CHILD_CHUNK_TOKENS` to `RAG_CHILD_CHUNK_MAX_CHARS` across the configuration and ingestion logic for better clarity.
- **Meaningful Naming Refactor**: Systematically renamed internal agent identifiers to align with domain-specific naming standards.
- **Advanced Text Normalization**: Improved chunking accuracy and slug generation by switching to NFKD text normalization.
- **Citation Traceability**: Added structured logging to the citation formatter to provide deeper visibility into AI evidence tracking.

### 🐛 Fixes

- **Security Hardening**: Removed hardcoded NVIDIA AI API keys and sanitized the codebase to prevent credential leakage.
- **Logic & Validation**: Corrected linting and validation checks within the SQLite MCP server and resolved formatting issues in the Phase 01 evidence generation system.

### 📝 Documentation & Testing

- **Implementation Memory Guidelines**: Updated `AGENTS.md` and `GEMINI.md` with new guidelines regarding import locations and tool priority.
- **KG Refactor Documentation**: Updated agent instructions and the data pipeline work log to reflect the knowledge graph architectural changes.
- **Test Suite Cleanup**: Cleaned up test initialization files and updated knowledge graph tests to align with the new pipeline structure.
- **Langfuse Integration Tests**: Added comprehensive integration tests for Langfuse logging and observability.
- **Project Roadmaps**: Published structured blueprints for Phase 02 and Phase 03 agent workflows.
- **Technical Specifications**: Published new specifications for the Quad-Retrieval RAG architecture and updated documentation with Gemini embedding integration support.

---

## [1.0.0] - 2026-05-03

### ✨ New Features

- **Multi-Agent Architecture**: Implemented a core agentic framework using **LangGraph**, featuring a specialized **DatabaseAgent** for complex SQL reasoning and a **SearchAgent** for dynamic information retrieval.
- **SQLite MCP Server**: Developed a custom Model Context Protocol (MCP) server for secure, read-only access to insurance databases, enabling agents to explore schemas and execute verified queries.
- **AI Extraction Reviewer**: Launched a dedicated web interface (FastAPI + modern UI) for manual validation of AI-extracted data, allowing side-by-side comparison of original documents and structured markdown.
- **Enhanced Observability Migration**: Successfully migrated from LangSmith to **Langfuse** for superior end-to-end tracing, performance monitoring, and advanced prompt management.
- **Remote Prompt Management**: Integrated **Langfuse Prompt Management (v4)**, allowing real-time instruction updates without code changes, backed by local fallbacks for high availability.
- **MCP Client Instrumentation**: Added Langfuse `@observe` tracing to the Model Context Protocol (MCP) client, enabling granular latency tracking for tool discovery and initialization.
- **Flexible LLM Orchestration**: Implemented dynamic provider selection using `init_chat_model`, supporting seamless switching between **Gemini 3 Flash** (primary) and local **Gemma 4** models.
- **Agent Skill Library**: Established a comprehensive library of reusable agent capabilities, replacing legacy `.agents` workflows with standardized, portable skill definitions.
- **CLI Database Utility**: Introduced the `insurevn-db` CLI entrypoint for managing and querying the local SQLite insurance database.

### 🔧 Improvements

- **Refined AI Reasoning**: Configured optimized sampling parameters, enabled **thinking tokens** for deeper model deliberation, and implemented automatic stripping of internal reasoning blocks from final user responses.
- **Production-Grade Logging**: Implemented a centralized, structured JSON logging system for consistent audit trails across agents and MCP servers.
- **Optimized Data Pipeline**: Enhanced table-to-text conversion pipelines with improved timeout handling, granular logging, and specialized processing for complex insurance benefits matrices.
- **Secure Data Handling**: Hardened database interactions with read-only enforcement at the MCP level and implemented robust error handling for common SQL failures.
- **Observability Propagation**: Automated metadata propagation (user/session IDs) across the full stack, linking high-level agent traces to low-level tool executions in Langfuse.
- **Prompt Version Tracing**: Enhanced `DatabaseAgent` and `SearchAgent` to automatically capture and propagate Langfuse prompt versions in trace metadata for precise performance auditing.

### 🐛 Fixes

- Resolved environment variable naming inconsistencies by standardizing on `LANGFUSE_HOST` (reverting from experimental `LANGFUSE_BASE_URL`).
- Fixed mock behavior in integration tests to align with updated model invocation patterns and asynchronous tool calls.
- Corrected global resource path resolution for configuration files and database assets across different execution environments.

### 📝 Documentation & Testing

- **Technical Specifications**: Published detailed design documents for the Multi-Agent System architecture, MCP server protocols, and Langfuse integration strategy.
- **Robust Test Framework**: Reorganized the test suite into unit, integration, and E2E layers, including a full-stack database agent test with graceful error handling.
- **Implementation Roadmaps**: Added structured plans for future table-to-text enhancements, vector store integration, and multi-model evaluation.
