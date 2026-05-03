# Changelog

All notable changes to the InsureVN project will be documented in this file.

## [1.0.0] - 2026-05-03

### ✨ New Features

- **Multi-Agent Architecture**: Implemented a core agentic framework using **LangGraph**, featuring a specialized **DatabaseAgent** for complex SQL reasoning and a **SearchAgent** for dynamic information retrieval.
- **SQLite MCP Server**: Developed a custom Model Context Protocol (MCP) server for secure, read-only access to insurance databases, enabling agents to explore schemas and execute verified queries.
- **AI Extraction Reviewer**: Launched a dedicated web interface (FastAPI + modern UI) for manual validation of AI-extracted data, allowing side-by-side comparison of original documents and structured markdown.
- **Enhanced Observability Migration**: Successfully migrated from LangSmith to **Langfuse** for superior end-to-end tracing, performance monitoring, and advanced prompt management.
- **Remote Prompt Management**: Integrated **Langfuse Prompt Management (v4)**, allowing real-time instruction updates without code changes, backed by local fallbacks for high availability.
- **Flexible LLM Orchestration**: Implemented dynamic provider selection using `init_chat_model`, supporting seamless switching between **Gemini 3 Flash** (primary) and local **Gemma 4** models.
- **Agent Skill Library**: Established a comprehensive library of reusable agent capabilities, replacing legacy `.agents` workflows with standardized, portable skill definitions.
- **CLI Database Utility**: Introduced the `insurevn-db` CLI entrypoint for managing and querying the local SQLite insurance database.

### 🔧 Improvements

- **Refined AI Reasoning**: Configured optimized sampling parameters, enabled **thinking tokens** for deeper model deliberation, and implemented automatic stripping of internal reasoning blocks from final user responses.
- **Production-Grade Logging**: Implemented a centralized, structured JSON logging system for consistent audit trails across agents and MCP servers.
- **Optimized Data Pipeline**: Enhanced table-to-text conversion pipelines with improved timeout handling, granular logging, and specialized processing for complex insurance benefits matrices.
- **Secure Data Handling**: Hardened database interactions with read-only enforcement at the MCP level and implemented robust error handling for common SQL failures.
- **Observability Propagation**: Automated metadata propagation (user/session IDs) across the full stack, linking high-level agent traces to low-level tool executions in Langfuse.

### 🐛 Fixes

- Resolved environment variable naming inconsistencies by standardizing on `LANGFUSE_HOST` (reverting from experimental `LANGFUSE_BASE_URL`).
- Fixed mock behavior in integration tests to align with updated model invocation patterns and asynchronous tool calls.
- Corrected global resource path resolution for configuration files and database assets across different execution environments.

### 📝 Documentation & Testing

- **Technical Specifications**: Published detailed design documents for the Multi-Agent System architecture, MCP server protocols, and Langfuse integration strategy.
- **Robust Test Framework**: Reorganized the test suite into unit, integration, and E2E layers, including a full-stack database agent test with graceful error handling.
- **Implementation Roadmaps**: Added structured plans for future table-to-text enhancements, vector store integration, and multi-model evaluation.
