from typing import Any

from graph_retriever.strategies import Eager
from langchain_core.vectorstores import VectorStore
from langchain_graph_retriever import GraphRetriever

from src.services.knowledge_graph.document_graph_retriever import (
    DocumentGraphRetriever,
)


class FakeVectorStore(VectorStore):
    """Minimal vector store accepted by GraphRetriever validation."""

    def similarity_search(
        self,
        _query: str,
        _k: int = 4,
        **_kwargs: Any,
    ) -> list[Any]:
        return []

    @classmethod
    def from_texts(
        cls,
        _texts: list[str],
        _embedding: Any,
        _metadatas: list[dict[str, Any]] | None = None,
        **_kwargs: Any,
    ) -> "FakeVectorStore":
        return cls()


def test_document_graph_retriever_creates_eager_graph_retriever() -> None:
    retriever = DocumentGraphRetriever(
        vector_store=FakeVectorStore(),
        metadata_edges=[("company_code", "company_code")],
        eager_k=5,
        eager_start_k=1,
        eager_max_depth=2,
    )

    graph_retriever = retriever.create_retriever()

    assert isinstance(graph_retriever, GraphRetriever)
    assert graph_retriever.edges == [("company_code", "company_code")]
    assert isinstance(graph_retriever.strategy, Eager)
    assert graph_retriever.strategy.select_k == 5
    assert graph_retriever.strategy.start_k == 1
    assert graph_retriever.strategy.max_depth == 2
