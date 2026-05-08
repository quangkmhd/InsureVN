"""Semantic chunking example from the Databricks RAG chunking guide."""

from __future__ import annotations

import re

from common import create_dummy_document, print_example_chunk
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter


def perform_semantic_chunking(
    document: str,
    chunk_size: int = 500,
    chunk_overlap: int = 100,
) -> list[Document]:
    """Perform semantic chunking at logical text boundaries."""
    text_splitter = RecursiveCharacterTextSplitter(
        separators=["\n\n", "\n", ". ", " ", ""],
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        length_function=len,
    )
    semantic_chunks = text_splitter.split_text(document)
    print(f"Document split into {len(semantic_chunks)} semantic chunks")

    section_patterns = [
        r"^#+\s+(.+)$",
        r"^.+\n[=\-]{2,}$",
        r"^[A-Z\s]+:$",
    ]

    documents = []
    current_section = "Introduction"
    for i, chunk in enumerate(semantic_chunks):
        for line in chunk.split("\n"):
            for pattern in section_patterns:
                match = re.match(pattern, line, re.MULTILINE)
                if match:
                    current_section = (
                        match.group(1) if match.groups() else match.group(0)
                    )
                    break

        words = re.findall(r"\b\w+\b", chunk.lower())
        stopwords = {
            "the",
            "and",
            "is",
            "of",
            "to",
            "a",
            "in",
            "that",
            "it",
            "with",
            "as",
            "for",
        }
        content_words = [word for word in words if word not in stopwords]
        semantic_density = len(content_words) / max(1, len(words))

        documents.append(
            Document(
                page_content=chunk,
                metadata={
                    "chunk_id": i,
                    "total_chunks": len(semantic_chunks),
                    "chunk_size": len(chunk),
                    "chunk_type": "semantic",
                    "section": current_section,
                    "semantic_density": round(semantic_density, 2),
                },
            )
        )

    return documents


if __name__ == "__main__":
    demo_document = create_dummy_document()
    chunked_docs = perform_semantic_chunking(
        demo_document,
        chunk_size=500,
        chunk_overlap=100,
    )

    print("\n----- CHUNKING RESULTS -----")
    print(f"Total semantic chunks: {len(chunked_docs)}")
    print_example_chunk(chunked_docs, title="EXAMPLE SEMANTIC CHUNK")

    section_counts: dict[str, int] = {}
    for doc in chunked_docs:
        section = doc.metadata["section"]
        section_counts[section] = section_counts.get(section, 0) + 1

    print("\n----- SECTION DISTRIBUTION -----")
    for section, count in section_counts.items():
        print(f"{section}: {count} chunks")

    print("\nTo integrate with Databricks:")
    print("1. Create embeddings using the Databricks embedding API")
    print("2. Store documents and embeddings in Delta table")
    print("3. Create Vector Search index using the semantic metadata for filtering")
