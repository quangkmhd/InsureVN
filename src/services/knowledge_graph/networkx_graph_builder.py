"""Build NetworkX diagnostics from LangChain graph documents."""

from __future__ import annotations

from typing import Any

import networkx as nx

from src.core.logger import get_logger
from src.services.knowledge_graph.llm_graph_document_extractor import (
    ALLOWED_NODE_TYPES,
    ALLOWED_RELATIONSHIP_TYPES,
    DocumentGraphExtractor,
    GraphDocument,
)
from src.services.observability import service_observe

logger = get_logger(__name__)


class NetworkxGraphBuilder:
    """Build a diagnostic NetworkX graph from LangChain graph documents."""

    def __init__(self, extractor: DocumentGraphExtractor | None = None) -> None:
        """Initialize builder with a LangChain document extractor."""
        self._extractor = extractor or DocumentGraphExtractor()

    @service_observe(
        name="service.knowledge_graph.networkx_graph_builder.build_from_documents",
        component="networkx_graph_builder",
    )
    def build_from_documents(
        self,
        documents: list[GraphDocument],
        chunks: list[dict[str, Any]],
    ) -> nx.DiGraph:
        """Extract and build a diagnostic graph from source documents."""
        graph_documents: list[Any] = []
        for document in documents:
            graph_documents.extend(self._extractor.extract(document, chunks))
        return self.build_from_graph_documents(graph_documents)

    @service_observe(
        name="service.knowledge_graph.networkx_graph_builder.build_from_graph_documents",
        component="networkx_graph_builder",
    )
    def build_from_graph_documents(self, graph_documents: list[Any]) -> nx.DiGraph:
        """Build a NetworkX graph from LangChain GraphDocument objects."""
        graph = nx.DiGraph()
        for graph_document in graph_documents:
            self._add_graph_document(graph, graph_document)
        logger.info(
            "built LangChain-derived knowledge graph diagnostic",
            extra={
                "component": "networkx_graph_builder",
                "node_count": graph.number_of_nodes(),
                "edge_count": graph.number_of_edges(),
                "entity_type_counts": _entity_type_counts(graph),
                "relationship_type_counts": _relationship_type_counts(graph),
            },
        )
        return graph

    def _add_graph_document(self, graph: nx.DiGraph, graph_document: Any) -> None:
        node_by_id = {}
        for node in graph_document.nodes:
            node_id = str(node.id)
            node_type = str(node.type)
            if node_type not in ALLOWED_NODE_TYPES:
                continue
            node_by_id[node_id] = node
            graph.add_node(
                node_id,
                entity_type=node_type,
                **dict(node.properties or {}),
            )
        for relationship in graph_document.relationships:
            relationship_type = str(relationship.type)
            source_id = str(relationship.source.id)
            target_id = str(relationship.target.id)
            if relationship_type not in ALLOWED_RELATIONSHIP_TYPES:
                continue
            if source_id not in node_by_id or target_id not in node_by_id:
                continue
            graph.add_edge(
                source_id,
                target_id,
                relationship_type=relationship_type,
                **dict(relationship.properties or {}),
            )


def _entity_type_counts(graph: nx.DiGraph) -> dict[str, int]:
    counts: dict[str, int] = {}
    for _, attributes in graph.nodes(data=True):
        entity_type = str(attributes.get("entity_type", "unknown"))
        counts[entity_type] = counts.get(entity_type, 0) + 1
    return counts


def _relationship_type_counts(graph: nx.DiGraph) -> dict[str, int]:
    counts: dict[str, int] = {}
    for _, _, attributes in graph.edges(data=True):
        relationship_type = str(attributes.get("relationship_type", "unknown"))
        counts[relationship_type] = counts.get(relationship_type, 0) + 1
    return counts
