from dataclasses import dataclass
from typing import Any

from graph_retriever.strategies import Eager
from langchain_graph_retriever import GraphRetriever


@dataclass(frozen=True)
class DocumentGraphRetriever:
    """Factory for LangChain GraphRetriever with Eager traversal."""

    vector_store: Any
    metadata_edges: list[tuple[str, str]]
    eager_k: int
    eager_start_k: int
    eager_max_depth: int

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
