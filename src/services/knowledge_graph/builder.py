"""Build deterministic NetworkX knowledge graphs from documents."""

from __future__ import annotations

from typing import Any

import networkx as nx

from src.core.logger import get_logger
from src.services.knowledge_graph.document_extractor import (
    ALLOWED_RELATIONSHIP_TYPES,
    DocumentGraphExtractor,
    GraphDocument,
)
from src.services.observability import service_observe

logger = get_logger(__name__)


class KnowledgeGraphBuilder:
    """Build a directed insurance knowledge graph from document evidence."""

    def __init__(self, extractor: DocumentGraphExtractor | None = None) -> None:
        """Initialize builder with a document extractor."""
        self._extractor = extractor or DocumentGraphExtractor()

    @service_observe(
        name="service.knowledge_graph.builder.build_from_documents",
        component="knowledge_graph_builder",
    )
    def build_from_documents(
        self,
        documents: list[GraphDocument],
        chunks: list[dict[str, Any]],
    ) -> nx.DiGraph:
        """Build a deterministic directed graph from documents and chunks.

        Args:
            documents: Normalized Markdown or converted PDF text documents.
            chunks: Phase 02 Qdrant chunk payload exports.

        Returns:
            NetworkX directed graph with document-grounded nodes and edges.
        """
        graph = nx.DiGraph()
        for document in documents:
            extraction = self._extractor.extract(document, chunks)
            for node_id, attributes in extraction.nodes.items():
                graph.add_node(node_id, **attributes)
            for edge in extraction.edges:
                if edge.relationship_type not in ALLOWED_RELATIONSHIP_TYPES:
                    continue
                graph.add_edge(
                    edge.source_id,
                    edge.target_id,
                    relationship_type=edge.relationship_type,
                    document_id=edge.document_id,
                    source_path=edge.source_path,
                    confidence=edge.confidence,
                    chunk_id=edge.chunk_id,
                    section_type=edge.section_type,
                )
        logger.info(
            "built document-derived knowledge graph",
            extra={
                "component": "knowledge_graph_builder",
                "node_count": graph.number_of_nodes(),
                "edge_count": graph.number_of_edges(),
                "entity_type_counts": _entity_type_counts(graph),
                "relationship_type_counts": _relationship_type_counts(graph),
            },
        )
        return graph


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
