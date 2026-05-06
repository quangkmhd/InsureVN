from typing import Any

from langchain_core.documents import Document
from langchain_neo4j.graphs.graph_document import GraphDocument, Node, Relationship

from src.services.knowledge_graph.document_extractor import (
    DocumentGraphExtractor,
)
from src.services.knowledge_graph.document_extractor import (
    GraphDocument as ExtractedGraphDocument,
)
from src.services.observability import service_observe


class GraphDocumentAdapter:
    """Convert extracted insurance graph data to LangChain GraphDocument shape."""

    def __init__(self, extractor: DocumentGraphExtractor | None = None) -> None:
        """Initialize adapter with strict document extractor."""
        self._extractor = extractor or DocumentGraphExtractor()

    @service_observe(
        name="service.knowledge_graph.graph_document_adapter.from_document",
        component="graph_document_adapter",
    )
    def from_document(
        self,
        document: ExtractedGraphDocument,
        chunks: list[dict[str, Any]],
    ) -> Any:
        """Convert a source document and chunk payloads to a graph document."""
        extraction = self._extractor.extract(document, chunks)
        node_by_id = {
            node_id: Node(
                id=node_id,
                type=str(attributes["entity_type"]),
                properties={"id": node_id, **attributes},
            )
            for node_id, attributes in extraction.nodes.items()
        }
        relationships = [
            Relationship(
                source=node_by_id[edge.source_id],
                target=node_by_id[edge.target_id],
                type=edge.relationship_type,
                properties={
                    "source_document_id": edge.document_id,
                    "source_chunk_id": edge.chunk_id,
                    "source_path": edge.source_path,
                    "section_type": edge.section_type,
                    "confidence": edge.confidence,
                    "extraction_method": "deterministic_document_extractor",
                    "ingestion_version": "unversioned",
                },
            )
            for edge in extraction.edges
            if edge.source_id in node_by_id and edge.target_id in node_by_id
        ]

        source = Document(
            page_content=document.text,
            metadata={
                "document_id": document.document_id,
                "document_name": document.document_name,
                "company_code": document.company_code,
                "source_path": document.source_path,
            },
        )
        return GraphDocument(
            nodes=list(node_by_id.values()),
            relationships=relationships,
            source=source,
        )
