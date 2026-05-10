import logging
from unittest.mock import MagicMock, patch

from src.services.evidence.citation_formatter import CitationFormatter
from src.services.chunking.document_chunker import DocumentChunker
from src.services.evidence.evidence_merger import EvidenceMerger
from src.services.knowledge_graph.graph_json_serializer import GraphJsonSerializer
from src.services.knowledge_graph.graph_quality_validator import GraphQualityValidator
from src.services.knowledge_graph.insurance_graph_schema import (
    build_chunk_id,
    build_company_id,
    build_document_id,
    build_plan_id,
)
from src.services.knowledge_graph.llm_graph_document_extractor import (
    DocumentGraphExtractor,
)
from src.services.knowledge_graph.neo4j_cypher_qa import Neo4jCypherQAService
from src.services.knowledge_graph.neo4j_store import Neo4jKnowledgeGraphStore
from src.services.knowledge_graph.networkx_graph_builder import NetworkxGraphBuilder
from src.services.document_retrieval.qdrant_collection_manager import QdrantCollectionManager
from src.services.evidence.qdrant_evidence import QdrantEvidenceMapper
from src.services.document_retrieval.qdrant_retriever import QdrantRetriever
from src.services.document_retrieval.qdrant_vector_store import QdrantVectorStoreFactory
from src.services.document_retrieval.retrieval_readiness import RetrievalReadinessReport
from src.services.evidence.sqlite_evidence import SqliteEvidenceMapper, SqliteProfileMapper

SERVICE_ENTRYPOINTS = (
    CitationFormatter.format,
    CitationFormatter.validate_required_fields,
    DocumentChunker.chunk_markdown,
    DocumentChunker.validate_payload,
    EvidenceMerger.merge,
    SqliteProfileMapper.from_profile_row,
    SqliteEvidenceMapper.from_mcp_result,
    NetworkxGraphBuilder.build_from_documents,
    DocumentGraphExtractor.extract,
    Neo4jCypherQAService.invoke,
    Neo4jKnowledgeGraphStore.from_connection,
    Neo4jKnowledgeGraphStore.ensure_schema,
    Neo4jKnowledgeGraphStore.import_graph_documents,
    GraphQualityValidator.validate,
    GraphJsonSerializer.save,
    GraphJsonSerializer.load,
    QdrantVectorStoreFactory.create_vector_store,
    build_chunk_id,
    build_company_id,
    build_document_id,
    build_plan_id,
    QdrantCollectionManager.ensure_collection,
    QdrantCollectionManager.ensure_payload_indexes,
    QdrantCollectionManager.build_readiness_report,
    QdrantEvidenceMapper.from_payload,
    QdrantEvidenceMapper.validate_payload,
    QdrantRetriever.setup_collection,
    QdrantRetriever.index_chunks,
    QdrantRetriever.retrieve,
    QdrantRetriever.delete_documents_by_ids,
    QdrantRetriever.assert_production_ready,
    RetrievalReadinessReport.assert_production_ready,
)


def test_service_entrypoints_are_langfuse_observed() -> None:
    """Every service boundary should create a Langfuse observation."""
    missing_observability = [
        f"{entrypoint.__module__}.{entrypoint.__qualname__}"
        for entrypoint in SERVICE_ENTRYPOINTS
        if not hasattr(entrypoint, "__wrapped__")
    ]

    assert missing_observability == []


def test_service_observe_logs_debug_and_updates_langfuse_span(caplog) -> None:
    """Service observability should debug operations without leaking raw payloads."""
    from src.services.observability import service_observe

    @service_observe(name="unit-service-operation", component="unit_service")
    def observed_service(payload: dict[str, str]) -> dict[str, int]:
        return {"payload_size": len(payload)}

    fake_client = MagicMock()
    with (
        patch("src.services.observability.get_client", return_value=fake_client),
        caplog.at_level(logging.DEBUG, logger="src.services.unit_service"),
    ):
        result = observed_service({"secret": "do-not-log"})

    assert result == {"payload_size": 1}
    assert any(
        record.message == "Service operation started"
        and record.__dict__["operation"] == "unit-service-operation"
        for record in caplog.records
    )
    assert any(
        record.message == "Service operation completed"
        and record.__dict__["operation"] == "unit-service-operation"
        and "duration_ms" in record.__dict__
        for record in caplog.records
    )
    fake_client.update_current_span.assert_any_call(
        input={
            "args": [{"type": "dict", "size": 1, "keys": ["secret"]}],
            "kwargs": {},
        },
        metadata={
            "component": "unit_service",
            "operation": "unit-service-operation",
            "function": "observed_service",
        },
    )
    assert "do-not-log" not in caplog.text
