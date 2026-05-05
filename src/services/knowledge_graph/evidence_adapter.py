"""Convert graph retrieval paths into shared Evidence records."""

from __future__ import annotations

from src.models.evidence import Evidence, SourceType
from src.services.knowledge_graph.retriever import GraphPath
from src.services.observability import service_observe


class GraphEvidenceAdapter:
    """Adapt graph paths into Evidence(source_type='graph_triple')."""

    @service_observe(
        name="service.knowledge_graph.evidence_adapter.to_evidence",
        component="graph_evidence_adapter",
    )
    def to_evidence(self, paths: list[GraphPath]) -> list[Evidence]:
        """Convert traversal paths to Evidence records."""
        evidence: list[Evidence] = []
        for path in paths:
            relationship_types = [edge.relationship_type for edge in path.edges]
            source_id = "->".join(path.node_ids)
            evidence.append(
                Evidence(
                    source_type=SourceType.GRAPH_TRIPLE,
                    source_id=source_id,
                    content=" -> ".join(
                        f"{edge.source_id} {edge.relationship_type} {edge.target_id}"
                        for edge in path.edges
                    ),
                    metadata={
                        "graph_path": path.node_ids,
                        "relationship_types": relationship_types,
                        "edge_lineage": [
                            {
                                "document_id": edge.attributes.get("document_id"),
                                "source_path": edge.attributes.get("source_path"),
                                "chunk_id": edge.attributes.get("chunk_id"),
                                "page_number": edge.attributes.get("page_number"),
                                "section_type": edge.attributes.get("section_type"),
                            }
                            for edge in path.edges
                        ],
                    },
                    confidence=min(
                        float(edge.attributes.get("confidence", 0.0))
                        for edge in path.edges
                    ),
                    retrieved_by="graph_retriever",
                )
            )
        return evidence
