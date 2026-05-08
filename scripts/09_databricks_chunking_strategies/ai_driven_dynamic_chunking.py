"""AI-driven dynamic chunking example from the Databricks RAG chunking guide."""

from __future__ import annotations

import json
import re
from typing import Any

from common import create_dummy_document
from langchain_core.documents import Document
from langchain_core.prompts import ChatPromptTemplate
from langchain_text_splitters import RecursiveCharacterTextSplitter

try:
    from databricks_langchain import ChatDatabricks
except ImportError:  # pragma: no cover - optional local dependency
    ChatDatabricks = None


def _message_content(response: Any) -> str:
    """Normalize a LangChain chat response to text."""
    return str(getattr(response, "content", response))


def _extract_json_array(content: str) -> str:
    """Extract a JSON array from raw model text."""
    fenced_match = re.search(r"```json\s*(\[.*?\])\s*```", content, re.DOTALL)
    if fenced_match:
        return fenced_match.group(1)

    json_match = re.search(r"\[\s*\".*\"\s*\]", content, re.DOTALL)
    if json_match:
        return json_match.group(0)

    return content


def perform_ai_driven_chunking(
    document: str,
    max_chunks: int = 20,
    fallback_chunk_size: int = 1000,
) -> list[Document]:
    """Use an LLM to chunk content based on semantic boundaries."""
    if ChatDatabricks is None:
        raise ImportError(
            "databricks-langchain is required for Databricks LLM chunking. "
            "Use perform_ai_driven_chunking_mock for local testing."
        )

    ai_chunking_llm = ChatDatabricks(
        endpoint="databricks-meta-llama-3-3-70b-instruct",
        temperature=0.1,
        max_tokens=4000,
    )
    chunking_prompt = ChatPromptTemplate.from_template(
        """
You are a document processing expert. Your task is to break down the following
document into at most {max_chunks} meaningful chunks. Follow these guidelines:
1. Each chunk should contain complete ideas or concepts
2. More complex sections should be in smaller chunks
3. Preserve headers with their associated content
4. Keep related information together
5. Maintain the original order of the document

DOCUMENT:
{document}

Return ONLY a valid JSON array of strings, where each string is a chunk.
Do not include any explanations or additional text outside the JSON array.
"""
    )
    chunking_chain = chunking_prompt | ai_chunking_llm

    try:
        response = chunking_chain.invoke(
            {"document": document, "max_chunks": max_chunks}
        )
        content = _extract_json_array(_message_content(response))
        chunks = json.loads(content)
        print(f"Successfully chunked document into {len(chunks)} AI-driven chunks")

        documents = []
        for i, chunk in enumerate(chunks):
            position = i / len(chunks)
            words = re.findall(r"\b\w+\b", chunk.lower())
            unique_words = set(words)
            word_density = len(unique_words) / max(1, len(words))
            documents.append(
                Document(
                    page_content=chunk,
                    metadata={
                        "chunk_id": i,
                        "total_chunks": len(chunks),
                        "chunk_size": len(chunk),
                        "chunk_type": "ai_driven",
                        "document_position": round(position, 2),
                        "word_count": len(words),
                        "unique_words": len(unique_words),
                        "word_density": round(word_density, 2),
                    },
                )
            )
        return documents

    except Exception as exc:  # pragma: no cover - external API fallback
        print(f"LLM chunking failed: {exc}")
        print("Falling back to basic chunking")
        return fallback_chunking(document, chunk_size=fallback_chunk_size)


def fallback_chunking(
    document: str,
    chunk_size: int = 1000,
    chunk_overlap: int = 100,
) -> list[Document]:
    """Fallback method if LLM chunking fails."""
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    chunks = splitter.split_text(document)
    print(f"Fallback chunking created {len(chunks)} chunks")

    documents = []
    for i, chunk in enumerate(chunks):
        documents.append(
            Document(
                page_content=chunk,
                metadata={
                    "chunk_id": i,
                    "total_chunks": len(chunks),
                    "chunk_size": len(chunk),
                    "chunk_type": "fallback",
                    "document_position": round(i / len(chunks), 2),
                },
            )
        )
    return documents


def perform_ai_driven_chunking_mock(
    document: str,
    max_chunks: int = 20,
) -> list[Document]:
    """Mock AI-driven chunking for testing without Databricks."""
    paragraphs = document.split("\n\n")
    chunks = []
    current_chunk = ""

    for paragraph in paragraphs:
        if not paragraph.strip():
            continue

        if len(current_chunk) + len(paragraph) < 500:
            current_chunk += paragraph + "\n\n"
        else:
            if current_chunk:
                chunks.append(current_chunk.strip())
            current_chunk = paragraph + "\n\n"

    if current_chunk:
        chunks.append(current_chunk.strip())

    if len(chunks) > max_chunks:
        new_chunks = []
        chunks_per_group = len(chunks) // max_chunks + 1
        for i in range(0, len(chunks), chunks_per_group):
            group = chunks[i : i + chunks_per_group]
            new_chunks.append("\n\n".join(group))
        chunks = new_chunks

    print(f"Mock AI chunking created {len(chunks)} chunks")

    documents = []
    for i, chunk in enumerate(chunks):
        position = i / len(chunks)
        words = re.findall(r"\b\w+\b", chunk.lower())
        unique_words = set(words)
        word_density = len(unique_words) / max(1, len(words))
        documents.append(
            Document(
                page_content=chunk,
                metadata={
                    "chunk_id": i,
                    "total_chunks": len(chunks),
                    "chunk_size": len(chunk),
                    "chunk_type": "mock_ai_driven",
                    "document_position": round(position, 2),
                    "word_count": len(words),
                    "unique_words": len(unique_words),
                    "word_density": round(word_density, 2),
                },
            )
        )

    return documents


if __name__ == "__main__":
    demo_document = create_dummy_document()
    print("Using mock implementation for testing...")
    chunked_docs = perform_ai_driven_chunking_mock(demo_document, max_chunks=10)

    print("\n----- CHUNKING RESULTS -----")
    print(f"Total chunks: {len(chunked_docs)}")
    print("\n----- EXAMPLE CHUNK -----")
    middle_chunk_idx = len(chunked_docs) // 2
    example_chunk = chunked_docs[middle_chunk_idx]
    print(f"Chunk {middle_chunk_idx}:")
    print("-" * 40)
    print(
        example_chunk.page_content[:200] + "..."
        if len(example_chunk.page_content) > 200
        else example_chunk.page_content
    )
    print("-" * 40)
    print(f"Metadata: {example_chunk.metadata}")
    print("\nTo use with Databricks:")
    print("1. Replace perform_ai_driven_chunking_mock with perform_ai_driven_chunking")
    print("2. Ensure your Databricks endpoint is correctly configured")
    print("3. Consider adjusting max_chunks based on your document size")
