"""Unit tests for LangChain graph document diagnostics."""

import logging

import networkx as nx
from langchain_core.documents import Document
from langchain_neo4j.graphs.graph_document import (
    GraphDocument as LangChainGraphDocument,
)
from langchain_neo4j.graphs.graph_document import Node, Relationship

from src.services.knowledge_graph.llm_graph_document_extractor import GraphDocument
from src.services.knowledge_graph.networkx_graph_builder import NetworkxGraphBuilder


class FakeGraphExtractor:
    def __init__(self, graph_documents: list[LangChainGraphDocument]) -> None:
        self.graph_documents = graph_documents
        self.calls = []

    def extract(self, document, chunks):
        self.calls.append((document, chunks))
        return self.graph_documents


def _sample_graph_document(
    *,
    relationship_type: str = "HAS_BENEFIT",
) -> LangChainGraphDocument:
    policy = Node(
        id="policy:aia:gold",
        type="InsurancePolicy",
        properties={"name": "AIA Gold"},
    )
    benefit = Node(
        id="benefit:noitru",
        type="Benefit",
        properties={"name": "Noi tru"},
    )
    return LangChainGraphDocument(
        nodes=[policy, benefit],
        relationships=[
            Relationship(
                source=policy,
                target=benefit,
                type=relationship_type,
                properties={
                    "source_document_id": "doc-1",
                    "source_path": "policy.md",
                    "confidence": 0.82,
                },
            )
        ],
        source=Document(page_content="AIA Gold co quyen loi noi tru."),
    )


def test_builder_no_longer_exposes_sqlite_primary_construction() -> None:
    assert not hasattr(NetworkxGraphBuilder(), "build_from_sqlite")


def test_build_from_graph_documents_creates_networkx_diagnostic_graph() -> None:
    graph = NetworkxGraphBuilder().build_from_graph_documents(
        [_sample_graph_document()]
    )

    assert isinstance(graph, nx.DiGraph)
    assert graph.nodes["policy:aia:gold"]["entity_type"] == "InsurancePolicy"
    assert graph.nodes["benefit:noitru"]["entity_type"] == "Benefit"
    assert graph.edges["policy:aia:gold", "benefit:noitru"]["relationship_type"] == (
        "HAS_BENEFIT"
    )
    assert graph.edges["policy:aia:gold", "benefit:noitru"]["confidence"] == 0.82


def test_build_from_graph_documents_filters_invalid_schema_types() -> None:
    graph = NetworkxGraphBuilder().build_from_graph_documents(
        [_sample_graph_document(relationship_type="MAKES_UP")]
    )

    assert list(graph.edges) == []
    assert "policy:aia:gold" in graph.nodes
    assert "benefit:noitru" in graph.nodes


def test_build_from_documents_uses_langchain_extractor() -> None:
    source_document = GraphDocument(
        document_id="doc-1",
        document_name="Policy",
        company_code="AIA",
        source_path="policy.md",
        text="Noi dung.",
    )
    chunks = [{"document_id": "doc-1", "text": "Noi dung."}]
    extractor = FakeGraphExtractor([_sample_graph_document()])

    graph = NetworkxGraphBuilder(extractor=extractor).build_from_documents(
        [source_document],
        chunks,
    )

    assert extractor.calls == [(source_document, chunks)]
    assert graph.number_of_nodes() == 2
    assert graph.number_of_edges() == 1


def test_builder_logs_required_observability_metadata(caplog) -> None:
    with caplog.at_level(logging.INFO):
        NetworkxGraphBuilder().build_from_graph_documents([_sample_graph_document()])

    record = next(
        item
        for item in caplog.records
        if getattr(item, "component", "") == "networkx_graph_builder"
    )
    assert record.node_count == 2
    assert record.edge_count == 1
    assert record.entity_type_counts["InsurancePolicy"] == 1
    assert record.relationship_type_counts["HAS_BENEFIT"] == 1
