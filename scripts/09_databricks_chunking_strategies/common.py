"""Shared helpers for the Databricks chunking strategy examples."""

from __future__ import annotations

from typing import Any


def create_dummy_document() -> str:
    """Create a compact document that exercises the chunking examples."""
    return """
# Machine Learning Overview

Machine learning studies algorithms that learn patterns from data. Supervised
learning uses labeled examples for classification and regression, while
unsupervised learning discovers hidden structures such as clustering and
dimensionality reduction.

## Neural Networks and LLMs

Neural networks model nonlinear relationships with layers of learned weights.
Large Language Models are trained with pre-training, fine-tuning, instruction
tuning, and sometimes Reinforcement Learning from Human Feedback. The decision
becomes more difficult when a retrieval system must preserve enough context for
natural language processing queries.

## Classical Methods

Support Vector Machines, Random Forests, and Principal Component Analysis are
common techniques. A train-test split helps evaluate generalization. PCA is
often used before clustering when the feature space is large.

## Advanced Topics

Multimodal learning combines text, images, audio, or video. Federated learning
trains across distributed data sources without centralizing raw records. These
systems can require careful chunking because short definitions and longer
technical explanations appear in the same source.
""".strip()


def document_text(chunk: Any) -> str:
    """Return plain text from either a LangChain Document or a raw string."""
    if hasattr(chunk, "page_content"):
        return str(chunk.page_content)
    return str(chunk)


def document_texts(chunks: list[Any]) -> list[str]:
    """Return plain-text contents for a list of chunks."""
    return [document_text(chunk) for chunk in chunks]


def print_example_chunk(chunks: list[Any], title: str = "EXAMPLE CHUNK") -> None:
    """Print the middle chunk and its metadata when available."""
    if not chunks:
        print("No chunks produced.")
        return

    middle_chunk_idx = len(chunks) // 2
    example_chunk = chunks[middle_chunk_idx]
    text = document_text(example_chunk)

    print(f"\n----- {title} -----")
    print(f"Chunk {middle_chunk_idx} content ({len(text)} characters):")
    print("-" * 40)
    print(text)
    print("-" * 40)
    if hasattr(example_chunk, "metadata"):
        print(f"Metadata: {example_chunk.metadata}")


def safe_average(values: list[float]) -> float:
    """Return the average of values, or 0.0 for an empty list."""
    if not values:
        return 0.0
    return sum(values) / len(values)
