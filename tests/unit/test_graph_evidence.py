from src.services.knowledge_graph.graph_evidence import GraphEvidenceMapper
from src.services.knowledge_graph.retriever import GraphPath, GraphPathEdge


def test_graph_evidence_mapper_omits_unreliable_page_number_lineage() -> None:
    path = GraphPath(
        node_ids=["plan:AIA:gold", "exclusion:AIA:gold:pre_existing_condition"],
        edges=[
            GraphPathEdge(
                source_id="plan:AIA:gold",
                target_id="exclusion:AIA:gold:pre_existing_condition",
                relationship_type="EXCLUDES",
                attributes={
                    "document_id": "aia_health_2026",
                    "source_path": "data/processed/aia_health_2026.md",
                    "chunk_id": "chunk:aia_health_2026:12",
                    "page_number": 7,
                    "section_type": "exclusions",
                    "confidence": 0.9,
                },
            )
        ],
        latency_ms=1.0,
    )

    evidence = GraphEvidenceMapper().to_evidence([path])

    edge_lineage = evidence[0].metadata["edge_lineage"][0]
    assert "page_number" not in edge_lineage
