"""Unit tests for document-derived knowledge graph building."""

import logging

import networkx as nx

from src.services.knowledge_graph.builder import KnowledgeGraphBuilder
from src.services.knowledge_graph.document_extractor import GraphDocument


def test_builder_no_longer_exposes_sqlite_primary_construction() -> None:
    """Prevent KnowledgeGraph from being built from SQLite topology."""
    assert not hasattr(KnowledgeGraphBuilder(), "build_from_sqlite")


def test_build_from_documents_creates_stable_document_and_chunk_nodes() -> None:
    """Build graph nodes from documents and Qdrant chunk payloads."""
    documents = [
        GraphDocument(
            document_id="aia_health_2026",
            document_name="AIA Health 2026 Policy Wording",
            company_code="AIA",
            source_path="data/processed/aia_health_2026.md",
            text="""
            ## Plan: Gold
            Benefits:
            - Inpatient care
            Exclusions:
            - Pre-existing condition
            """,
        )
    ]
    chunks = [
        {
            "document_id": "aia_health_2026",
            "chunk_index": 12,
            "company_code": "AIA",
            "document_name": "AIA Health 2026 Policy Wording",
            "plan_code": "gold",
            "section_type": "exclusions",
            "page_number": 7,
            "source_path": "data/processed/aia_health_2026.md",
            "text": "Exclusions: Pre-existing condition.",
        }
    ]

    graph = KnowledgeGraphBuilder().build_from_documents(documents, chunks)

    assert isinstance(graph, nx.DiGraph)
    assert graph.nodes["company:AIA"]["entity_type"] == "Company"
    assert graph.nodes["document:aia_health_2026"]["entity_type"] == "Document"
    assert graph.nodes["plan:AIA:gold"]["entity_type"] == "Plan"
    assert graph.nodes["chunk:aia_health_2026:12"] == {
        "entity_type": "Chunk",
        "document_id": "aia_health_2026",
        "chunk_index": 12,
        "company_code": "AIA",
        "document_name": "AIA Health 2026 Policy Wording",
        "plan_code": "gold",
        "section_type": "exclusions",
        "page_number": 7,
        "source_path": "data/processed/aia_health_2026.md",
    }


def test_build_from_documents_rejects_invalid_relationship_types() -> None:
    """Only strict GraphRAG relationship types can enter the graph."""
    documents = [
        GraphDocument(
            document_id="aia_health_2026",
            document_name="AIA Health 2026 Policy Wording",
            company_code="AIA",
            source_path="data/processed/aia_health_2026.md",
            text="""
            ## Plan: Gold
            Benefits:
            - Inpatient care
            """,
        )
    ]

    graph = KnowledgeGraphBuilder().build_from_documents(documents, chunks=[])

    relationship_types = {
        attributes["relationship_type"] for _, _, attributes in graph.edges(data=True)
    }
    assert relationship_types <= {
        "DOCUMENT_DEFINES",
        "OFFERS",
        "INCLUDES",
        "EXCLUDES",
        "APPLIES_TO",
        "HAS_WAITING_PERIOD",
        "USES_NETWORK",
        "MENTIONED_IN",
    }
    assert ("company:AIA", "plan:AIA:gold") in graph.edges
    assert ("plan:AIA:gold", "benefit:AIA:gold:inpatient_care") in graph.edges


def test_builder_logs_required_observability_metadata(caplog) -> None:
    """Emit required JSON log metadata after graph construction."""
    documents = [
        GraphDocument(
            document_id="aia_health_2026",
            document_name="AIA Health 2026 Policy Wording",
            company_code="AIA",
            source_path="data/processed/aia_health_2026.md",
            text="""
            ## Plan: Gold
            Benefits:
            - Inpatient care
            """,
        )
    ]

    with caplog.at_level(logging.INFO):
        KnowledgeGraphBuilder().build_from_documents(documents, chunks=[])

    record = next(
        item
        for item in caplog.records
        if getattr(item, "component", "") == "knowledge_graph_builder"
    )
    assert record.node_count == 4
    assert record.edge_count == 3
    assert record.entity_type_counts["Plan"] == 1
    assert record.relationship_type_counts["INCLUDES"] == 1
