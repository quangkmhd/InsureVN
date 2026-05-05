from dataclasses import dataclass
from typing import Any

from graph_retriever.strategies import Eager
from langchain_graph_retriever import GraphRetriever

from src.services.observability import service_observe


@dataclass(frozen=True)
class DocumentGraphRetriever:
    """Factory for LangChain GraphRetriever with Eager traversal."""

    vector_store: Any
    metadata_edges: list[tuple[str, str]]
    eager_k: int
    eager_start_k: int
    eager_max_depth: int

    @service_observe(
        name="service.knowledge_graph.document_graph_retriever.create_retriever",
        component="document_graph_retriever",
    )
    def create_retriever(self) -> Any:
        """Create the LangChain GraphRetriever instance."""
        return GraphRetriever(
            store=self.vector_store,
            edges=self.metadata_edges,
            strategy=Eager(
                k=self.eager_k,
                start_k=self.eager_start_k,
                max_depth=self.eager_max_depth,
            ),
        )
