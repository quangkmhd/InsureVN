"""Adaptive chunking example from the Databricks RAG chunking guide."""

from __future__ import annotations

import re
from typing import Any

import numpy as np
from common import create_dummy_document, safe_average
from langchain_core.documents import Document
from langchain_text_splitters import TextSplitter

try:
    import nltk
    from nltk.tokenize import sent_tokenize
except ImportError:  # pragma: no cover - optional local dependency
    nltk = None
    sent_tokenize = None


def ensure_nltk_punkt() -> None:
    """Download NLTK punkt resources when NLTK is installed."""
    if nltk is None:
        return
    for resource in ("punkt", "punkt_tab"):
        try:
            nltk.data.find(f"tokenizers/{resource}")
        except LookupError:
            nltk.download(resource)


def sentence_tokenize(text: str) -> list[str]:
    """Tokenize sentences with NLTK when available, otherwise use regex."""
    if sent_tokenize is not None:
        try:
            return sent_tokenize(text)
        except LookupError:
            ensure_nltk_punkt()
            try:
                return sent_tokenize(text)
            except LookupError:
                pass
    return [part.strip() for part in re.split(r"(?<=[.!?])\s+", text) if part.strip()]


class AdaptiveTextSplitter(TextSplitter):
    """Custom text splitter that adapts chunk sizes based on text complexity."""

    def __init__(
        self,
        min_chunk_size: int = 300,
        max_chunk_size: int = 1000,
        min_chunk_overlap: int = 30,
        max_chunk_overlap: int = 150,
        complexity_measure: str = "lexical_density",
        length_function: Any = len,
        **kwargs: Any,
    ) -> None:
        """Initialize adaptive chunking parameters."""
        super().__init__(**kwargs)
        self.min_chunk_size = min_chunk_size
        self.max_chunk_size = max_chunk_size
        self.min_chunk_overlap = min_chunk_overlap
        self.max_chunk_overlap = max_chunk_overlap
        self.complexity_measure = complexity_measure
        self.length_function = length_function

    def analyze_complexity(self, text: str) -> float:
        """Analyze text complexity and return a score between 0 and 1."""
        if not text.strip():
            return 0.0

        if self.complexity_measure in {"lexical_density", "combined"}:
            words = re.findall(r"\b\w+\b", text.lower())
            lex_density = len(set(words)) / len(words) if words else 0
            lex_density = min(1.0, lex_density / 0.8)
        else:
            lex_density = 0

        if self.complexity_measure in {"sentence_length", "combined"}:
            sentences = sentence_tokenize(text)
            if sentences:
                avg_length = safe_average(
                    [float(len(sentence)) for sentence in sentences]
                )
                sent_complexity = min(1.0, avg_length / 200)
            else:
                sent_complexity = 0
        else:
            sent_complexity = 0

        if self.complexity_measure == "combined":
            return (lex_density + sent_complexity) / 2
        if self.complexity_measure == "lexical_density":
            return lex_density
        return sent_complexity

    def split_text(self, text: str) -> list[str]:
        """Split text into chunks based on adaptive sizing."""
        if not text:
            return []

        sentences = sentence_tokenize(text)
        chunks = []
        current_chunk: list[str] = []
        current_size = 0
        current_complexity = 0.5

        for sentence in sentences:
            sentence_len = self.length_function(sentence)
            if sentence_len == 0:
                continue

            sentence_complexity = self.analyze_complexity(sentence)
            if current_chunk:
                current_complexity = (current_complexity + sentence_complexity) / 2
            else:
                current_complexity = sentence_complexity

            target_size = self.max_chunk_size - (
                current_complexity * (self.max_chunk_size - self.min_chunk_size)
            )
            target_overlap = self.min_chunk_overlap + (
                current_complexity * (self.max_chunk_overlap - self.min_chunk_overlap)
            )

            if current_size + sentence_len > target_size and current_chunk:
                chunks.append(" ".join(current_chunk))
                overlap_size = 0
                overlap_chunk = []
                for prev_sentence in reversed(current_chunk):
                    prev_len = self.length_function(prev_sentence)
                    if overlap_size + prev_len <= target_overlap:
                        overlap_chunk.insert(0, prev_sentence)
                        overlap_size += prev_len
                    else:
                        break
                current_chunk = overlap_chunk + [sentence]
                current_size = sum(self.length_function(item) for item in current_chunk)
            else:
                current_chunk.append(sentence)
                current_size += sentence_len

        if current_chunk:
            chunks.append(" ".join(current_chunk))

        return chunks

    def create_documents(
        self,
        texts: list[str],
        metadatas: list[dict[str, Any]] | None = None,
    ) -> list[Document]:
        """Create Document objects with complexity metadata."""
        documents = []
        for i, text in enumerate(texts):
            complexity = self.analyze_complexity(text)
            metadata: dict[str, Any] = {
                "chunk_id": i,
                "total_chunks": len(texts),
                "chunk_size": self.length_function(text),
                "chunk_type": "adaptive",
                "text_complexity": round(complexity, 3),
            }
            if metadatas and i < len(metadatas):
                metadata.update(metadatas[i])
            documents.append(Document(page_content=text, metadata=metadata))

        return documents


def perform_adaptive_chunking(
    document: str,
    min_size: int = 300,
    max_size: int = 1000,
    min_overlap: int = 30,
    max_overlap: int = 150,
    complexity_measure: str = "combined",
) -> list[Document]:
    """Perform adaptive chunking with size varying by text complexity."""
    splitter = AdaptiveTextSplitter(
        min_chunk_size=min_size,
        max_chunk_size=max_size,
        min_chunk_overlap=min_overlap,
        max_chunk_overlap=max_overlap,
        complexity_measure=complexity_measure,
    )
    chunks = splitter.split_text(document)
    print(f"Document split into {len(chunks)} adaptive chunks")

    documents = splitter.create_documents(chunks)
    chunk_sizes = [doc.metadata["chunk_size"] for doc in documents]
    if chunk_sizes:
        avg_size = sum(chunk_sizes) / len(chunk_sizes)
        for doc in documents:
            doc.metadata["avg_chunk_size"] = round(avg_size, 1)
            doc.metadata["size_vs_avg"] = round(
                doc.metadata["chunk_size"] / avg_size, 2
            )

    return documents


if __name__ == "__main__":
    ensure_nltk_punkt()
    demo_document = create_dummy_document()
    chunked_docs = perform_adaptive_chunking(
        demo_document,
        min_size=300,
        max_size=1000,
        complexity_measure="combined",
    )

    print("\n----- CHUNKING RESULTS -----")
    print(f"Total adaptive chunks: {len(chunked_docs)}")

    complexities = [doc.metadata["text_complexity"] for doc in chunked_docs]
    sizes = [doc.metadata["chunk_size"] for doc in chunked_docs]
    print("\n----- COMPLEXITY ANALYSIS -----")
    print(f"Average complexity: {np.mean(complexities):.3f}")
    print(f"Min complexity: {min(complexities):.3f}")
    print(f"Max complexity: {max(complexities):.3f}")

    print("\n----- SIZE ANALYSIS -----")
    print(f"Average chunk size: {np.mean(sizes):.1f} characters")
    print(f"Min chunk size: {min(sizes)} characters")
    print(f"Max chunk size: {max(sizes)} characters")

    high_complex_idx = complexities.index(max(complexities))
    low_complex_idx = complexities.index(min(complexities))
    print("\n----- HIGHEST COMPLEXITY CHUNK -----")
    print(f"Complexity: {chunked_docs[high_complex_idx].metadata['text_complexity']}")
    print(f"Size: {chunked_docs[high_complex_idx].metadata['chunk_size']} characters")
    print("-" * 40)
    print(chunked_docs[high_complex_idx].page_content[:200] + "...")
    print("\n----- LOWEST COMPLEXITY CHUNK -----")
    print(f"Complexity: {chunked_docs[low_complex_idx].metadata['text_complexity']}")
    print(f"Size: {chunked_docs[low_complex_idx].metadata['chunk_size']} characters")
    print("-" * 40)
    print(chunked_docs[low_complex_idx].page_content[:200] + "...")
    print("\nTo integrate with Databricks:")
    print("1. Create embeddings using DatabricksEmbeddings")
    print("2. Store documents and embeddings in a Delta table")
    print("3. Create a Vector Search index with complexity filtering capability")
    print(
        "4. During retrieval, consider filtering by complexity for specific use cases"
    )
