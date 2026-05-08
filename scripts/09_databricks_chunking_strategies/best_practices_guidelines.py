"""Best-practice helper snippets from the Databricks RAG chunking guide."""

from __future__ import annotations

import re
from typing import Any

from adaptive_chunking import ensure_nltk_punkt, sentence_tokenize
from common import create_dummy_document
from langchain_core.documents import Document
from langchain_text_splitters import (
    CharacterTextSplitter,
    Language,
    RecursiveCharacterTextSplitter,
)


def perform_baseline_testing(document: str) -> list[dict[str, float]]:
    """Test different chunk sizes and overlaps to establish a baseline."""
    test_sizes = [100, 200, 500, 1000]
    results = []
    for size in test_sizes:
        splitter = CharacterTextSplitter(
            chunk_size=size,
            chunk_overlap=int(size * 0.2),
            separator="\n\n",
        )
        chunks = splitter.split_text(document)
        results.append(
            {
                "chunk_size": size,
                "overlap": int(size * 0.2),
                "num_chunks": len(chunks),
                "avg_chunk_length": sum(len(chunk) for chunk in chunks) / len(chunks),
            }
        )

    return results


def optimize_chunking_by_content_type(document: str, content_type: str) -> list[str]:
    """Apply optimized chunking based on content type."""
    if content_type == "general":
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=400,
            chunk_overlap=60,
            separators=["\n\n", "\n", ". ", " ", ""],
        )
    elif content_type == "technical":
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=150,
            chunk_overlap=30,
            separators=["\n\n", "\n", ". ", " ", ""],
        )
    elif content_type == "narrative":
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=800,
            chunk_overlap=100,
            separators=["\n\n", "\n", ". ", " ", ""],
        )
    else:
        raise ValueError("content_type must be one of: general, technical, narrative")

    return splitter.split_text(document)


def hybrid_chunking(document: str) -> list[dict[str, Any]]:
    """Process different sections of a document with appropriate methods."""
    sections = []
    current_section: dict[str, Any] = {"type": "text", "content": ""}

    for line in document.split("\n"):
        if re.match(r"```python|```js|```java", line):
            if current_section["content"]:
                sections.append(current_section)
            current_section = {
                "type": "code",
                "language": line.strip("`"),
                "content": "",
            }
        elif re.match(r"```", line) and current_section["type"] == "code":
            if current_section["content"]:
                sections.append(current_section)
            current_section = {"type": "text", "content": ""}
        elif re.match(r"\|.*\|.*\|", line):
            if current_section["type"] != "table":
                if current_section["content"]:
                    sections.append(current_section)
                current_section = {"type": "table", "content": line + "\n"}
            else:
                current_section["content"] += line + "\n"
        else:
            current_section["content"] += line + "\n"

    if current_section["content"]:
        sections.append(current_section)

    chunks = []
    for section in sections:
        if section["type"] == "code":
            code_splitter = RecursiveCharacterTextSplitter.from_language(
                language=Language.PYTHON,
                chunk_size=100,
                chunk_overlap=20,
            )
            section_chunks = code_splitter.split_text(section["content"])
        elif section["type"] == "table":
            section_chunks = [section["content"]]
        else:
            text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=400,
                chunk_overlap=50,
                separators=["\n\n", "\n", ". ", " ", ""],
            )
            section_chunks = text_splitter.split_text(section["content"])

        for i, chunk in enumerate(section_chunks):
            chunks.append(
                {
                    "content": chunk,
                    "type": section["type"],
                    "index": i,
                    "total": len(section_chunks),
                }
            )

    return chunks


def chunks_with_metadata(
    document: str,
    title: str,
    document_type: str,
    date: str,
) -> list[Document]:
    """Create chunks with rich metadata."""
    splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)

    headings = {}
    for match in re.finditer(r"(#{1,6})\s+(.*?)\s*$", document, re.MULTILINE):
        heading_level = len(match.group(1))
        heading_text = match.group(2)
        headings[match.start()] = {"level": heading_level, "text": heading_text}

    text_chunks = splitter.split_text(document)
    doc_chunks = []
    for i, chunk in enumerate(text_chunks):
        chunk_start_pos = document.find(chunk)
        current_heading = None
        for pos, heading in sorted(headings.items()):
            if pos <= chunk_start_pos:
                current_heading = heading
            else:
                break

        metadata = {
            "chunk_id": i,
            "document_title": title,
            "document_type": document_type,
            "date": date,
            "total_chunks": len(text_chunks),
        }
        if current_heading:
            metadata["section"] = current_heading["text"]
            metadata["section_level"] = current_heading["level"]

        doc_chunks.append(Document(page_content=chunk, metadata=metadata))

    return doc_chunks


def semantic_boundary_chunking(document: str, target_size: int = 500) -> list[str]:
    """Create chunks that respect sentence boundaries."""
    ensure_nltk_punkt()
    sentences = sentence_tokenize(document)
    chunks = []
    current_chunk: list[str] = []
    current_size = 0

    for sentence in sentences:
        sentence_len = len(sentence)
        if current_size + sentence_len > target_size and current_chunk:
            chunks.append(" ".join(current_chunk))
            current_chunk = [sentence]
            current_size = sentence_len
        else:
            current_chunk.append(sentence)
            current_size += sentence_len

    if current_chunk:
        chunks.append(" ".join(current_chunk))

    return chunks


def process_structured_content(document: str) -> list[str]:
    """Handle different types of structured content."""
    patterns = {
        "table": r"\|.*\|.*\|[\s\S]*?\n\n",
        "code_block": r"```[\s\S]*?```",
        "image": r"!\[.*?\]\(.*?\)",
    }
    structured_parts = {}
    placeholder_count = 0
    modified_document = document

    for content_type, pattern in patterns.items():
        matches = re.finditer(pattern, document, re.MULTILINE)
        for match in matches:
            placeholder = f"[PLACEHOLDER_{placeholder_count}]"
            placeholder_count += 1
            structured_parts[placeholder] = {
                "type": content_type,
                "content": match.group(0),
            }
            modified_document = modified_document.replace(match.group(0), placeholder)

    text_splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
    base_chunks = text_splitter.split_text(modified_document)
    final_chunks = []

    for chunk in base_chunks:
        current_chunk = chunk
        for placeholder, content_data in structured_parts.items():
            if placeholder in chunk:
                if content_data["type"] in {"code_block", "table"}:
                    current_chunk = current_chunk.replace(
                        placeholder,
                        content_data["content"],
                    )
                elif content_data["type"] == "image":
                    image_ref = content_data["content"]
                    image_alt = re.search(r"!\[(.*?)\]", image_ref)
                    alt_text = image_alt.group(1) if image_alt else "image"
                    current_chunk = current_chunk.replace(
                        placeholder,
                        f"[Image description: {alt_text}]",
                    )
        final_chunks.append(current_chunk)

    return final_chunks


def evaluate_chunking_performance(
    queries: list[str],
    retrieved_chunks: list[list[Document]],
    user_ratings: list[float],
) -> list[dict[str, Any]]:
    """Analyze and refine chunking based on user feedback."""
    chunk_effectiveness: dict[Any, dict[str, Any]] = {}

    for query, chunks, rating in zip(
        queries, retrieved_chunks, user_ratings, strict=False
    ):
        for chunk in chunks:
            chunk_id = chunk.metadata.get("chunk_id", "unknown")
            if chunk_id not in chunk_effectiveness:
                chunk_effectiveness[chunk_id] = {
                    "query_count": 0,
                    "total_rating": 0,
                    "queries": [],
                }

            chunk_effectiveness[chunk_id]["query_count"] += 1
            chunk_effectiveness[chunk_id]["total_rating"] += rating
            chunk_effectiveness[chunk_id]["queries"].append(query)

    refinement_suggestions = []
    for chunk_id, stats in chunk_effectiveness.items():
        if stats["query_count"] > 0:
            avg_rating = stats["total_rating"] / stats["query_count"]
            if avg_rating < 3:
                refinement_suggestions.append(
                    {
                        "chunk_id": chunk_id,
                        "avg_rating": avg_rating,
                        "issue": "Low performance across queries",
                        "suggestion": (
                            "Consider refining this chunk or checking content quality"
                        ),
                    }
                )

            query_keywords = " ".join(stats["queries"]).lower()
            if "code" in query_keywords and avg_rating < 4:
                refinement_suggestions.append(
                    {
                        "chunk_id": chunk_id,
                        "avg_rating": avg_rating,
                        "issue": "Poor performance on code-related queries",
                        "suggestion": "Use code-specific chunking for this section",
                    }
                )

    return refinement_suggestions


if __name__ == "__main__":
    demo_document = create_dummy_document()
    print("Baseline testing:")
    print(perform_baseline_testing(demo_document))
    print("\nOptimized general chunks:")
    print(optimize_chunking_by_content_type(demo_document, "general"))
    print("\nMetadata chunks:")
    print(chunks_with_metadata(demo_document, "Demo", "guide", "2026-05-07")[0])
