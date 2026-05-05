from src.services.knowledge_graph.document_extractor import GraphDocument
from src.services.knowledge_graph.graph_document_adapter import (
    GraphDocumentAdapter,
)


def test_graph_document_adapter_builds_langchain_graph_document_contract() -> None:
    document = GraphDocument(
        document_id="aia_health_2026",
        document_name="AIA Health 2026 Policy Wording",
        company_code="AIA",
        source_path="data/processed/aia_health_2026.md",
        text="## Plan: Gold\nBenefits:\n- Inpatient care",
    )
    chunks = [
        {
            "document_id": "aia_health_2026",
            "chunk_index": 12,
            "company_code": "AIA",
            "document_name": "AIA Health 2026 Policy Wording",
            "plan_code": "gold",
            "section_type": "benefits",
            "page_number": 7,
            "source_path": "data/processed/aia_health_2026.md",
            "text": "Benefits: Inpatient care.",
        }
    ]

    graph_document = GraphDocumentAdapter().from_document(document, chunks)

    assert graph_document.source.metadata["document_id"] == "aia_health_2026"
    node_ids = {node.id for node in graph_document.nodes}
    relationship_types = {
        relationship.type for relationship in graph_document.relationships
    }
    assert "company:AIA" in node_ids
    assert "document:aia_health_2026" in node_ids
    assert "plan:AIA:gold" in node_ids
    assert "DOCUMENT_DEFINES" in relationship_types
    assert "OFFERS" in relationship_types
