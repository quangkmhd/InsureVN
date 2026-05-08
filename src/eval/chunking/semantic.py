"""Embedding-based semantic chunking."""

from __future__ import annotations

from langchain_core.embeddings import Embeddings
from langchain_experimental.text_splitter import SemanticChunker

from src.eval.chunking.base import ChunkingStrategy, chunks_from_langchain_documents
from src.eval.models import CorpusDocument, TextChunk


class SemanticChunking(ChunkingStrategy):
    """Split text using LangChain Experimental SemanticChunker."""

    name = "semantic_embedding"
    description = "LangChain SemanticChunker with configured semantic embeddings."

    def __init__(self, embeddings: Embeddings, min_chunk_size: int = 200) -> None:
        self.retrieval_embeddings = embeddings
        self.splitter = SemanticChunker(
            embeddings=embeddings,
            breakpoint_threshold_type="percentile",
            breakpoint_threshold_amount=95,
            min_chunk_size=min_chunk_size,
        )

    def chunk_document(self, document: CorpusDocument) -> list[TextChunk]:
        """Split one document by embedding-space semantic breakpoints."""

        split_documents = self.splitter.create_documents([document.text])
        return chunks_from_langchain_documents(document, self.name, split_documents)
