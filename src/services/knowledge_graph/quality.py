"""Quality validation for document-derived knowledge graphs."""

from __future__ import annotations

from dataclasses import dataclass

import networkx as nx

from src.core.logger import get_logger
from src.services.knowledge_graph.document_extractor import (
    ALLOWED_RELATIONSHIP_TYPES,
)
from src.services.observability import service_observe

logger = get_logger(__name__)


@dataclass(frozen=True)
class GraphQualityReport:
    """Knowledge graph validation report."""

    is_valid: bool
    orphan_nodes: list[str]
    missing_document_lineage: list[str]
    dangling_chunk_references: list[str]
    low_confidence_edges: list[str]
    invalid_relationships: list[str]
    node_count: int
    edge_count: int
    entity_type_counts: dict[str, int]
    relationship_type_counts: dict[str, int]


class GraphQualityValidator:
    """Validate graph schema, lineage, chunk references, and confidence."""

    def __init__(self, min_confidence: float = 0.75) -> None:
        """Initialize validator with a minimum relationship confidence."""
        self._min_confidence = min_confidence

    @service_observe(
        name="service.knowledge_graph.quality.validate",
        component="graph_quality",
    )
    def validate(
        self,
        graph: nx.DiGraph,
        document_counts: dict[str, int],
        chunk_counts: dict[str, int],
    ) -> GraphQualityReport:
        """Validate graph quality constraints."""
        orphan_nodes = sorted(
            node_id
            for node_id in graph.nodes
            if graph.in_degree(node_id) == 0
            and graph.out_degree(node_id) == 0
            and not node_id.startswith("document:")
        )
        missing_lineage: list[str] = []
        dangling_chunks: list[str] = []
        low_confidence: list[str] = []
        invalid_relationships: list[str] = []
        relationship_type_counts: dict[str, int] = {}
        chunk_node_ids = {
            node_id
            for node_id, attributes in graph.nodes(data=True)
            if attributes.get("entity_type") == "Chunk"
        }

        for source_id, target_id, attributes in graph.edges(data=True):
            edge_id = f"{source_id}->{target_id}"
            relationship_type = str(attributes.get("relationship_type", ""))
            relationship_type_counts[relationship_type] = (
                relationship_type_counts.get(relationship_type, 0) + 1
            )
            if relationship_type not in ALLOWED_RELATIONSHIP_TYPES:
                invalid_relationships.append(relationship_type)
            if not attributes.get("document_id") or not attributes.get("source_path"):
                missing_lineage.append(edge_id)
            if float(attributes.get("confidence", 0.0)) < self._min_confidence:
                low_confidence.append(edge_id)
            chunk_id = attributes.get("chunk_id")
            document_id = attributes.get("document_id")
            if chunk_id and (
                document_id not in chunk_counts or str(chunk_id) not in chunk_node_ids
            ):
                dangling_chunks.append(str(chunk_id))

        entity_type_counts: dict[str, int] = {}
        for _, attributes in graph.nodes(data=True):
            entity_type = str(attributes.get("entity_type", "unknown"))
            entity_type_counts[entity_type] = entity_type_counts.get(entity_type, 0) + 1

        known_documents = set(document_counts)
        for node_id, attributes in graph.nodes(data=True):
            document_id = attributes.get("document_id")
            if (
                document_id
                and document_id not in known_documents
                and attributes.get("entity_type") == "Chunk"
            ):
                dangling_chunks.append(node_id)

        dangling_chunks = sorted(set(dangling_chunks))
        invalid_relationships = sorted(set(invalid_relationships))
        is_valid = not any(
            [
                orphan_nodes,
                missing_lineage,
                dangling_chunks,
                low_confidence,
                invalid_relationships,
            ]
        )
        report = GraphQualityReport(
            is_valid=is_valid,
            orphan_nodes=orphan_nodes,
            missing_document_lineage=missing_lineage,
            dangling_chunk_references=dangling_chunks,
            low_confidence_edges=low_confidence,
            invalid_relationships=invalid_relationships,
            node_count=graph.number_of_nodes(),
            edge_count=graph.number_of_edges(),
            entity_type_counts=entity_type_counts,
            relationship_type_counts=relationship_type_counts,
        )
        logger.info(
            "validated knowledge graph quality",
            extra={
                "component": "graph_quality",
                "node_count": report.node_count,
                "edge_count": report.edge_count,
                "entity_type_counts": report.entity_type_counts,
                "relationship_type_counts": report.relationship_type_counts,
                "orphan_count": len(report.orphan_nodes),
            },
        )
        return report
