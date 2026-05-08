"""Evaluation framework from the Databricks RAG chunking guide."""

from __future__ import annotations

import re
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import pandas as pd
from adaptive_chunking import perform_adaptive_chunking
from ai_driven_dynamic_chunking import (
    perform_ai_driven_chunking,
    perform_ai_driven_chunking_mock,
)
from common import create_dummy_document, document_texts
from context_enriched_chunking import (
    perform_context_enriched_chunking,
    perform_context_enriched_chunking_mock,
)
from fixed_size_chunking import perform_fixed_size_chunking
from recursive_code_chunking import perform_code_chunking
from semantic_chunking import perform_semantic_chunking


def calculate_keyword_coverage(chunks: list[str], keywords: list[str]) -> float:
    """Calculate what percentage of keywords appear in at least one chunk."""
    lowercase_chunks = [chunk.lower() for chunk in chunks]
    lowercase_keywords = [keyword.lower() for keyword in keywords]
    keywords_found = 0
    for keyword in lowercase_keywords:
        if any(keyword in chunk for chunk in lowercase_chunks):
            keywords_found += 1

    return keywords_found / max(1, len(keywords))


def calculate_chunk_coherence(chunks: list[str]) -> float:
    """Calculate average coherence based on sentence completeness."""
    incomplete_boundaries = 0
    for chunk in chunks:
        if chunk and (chunk[0].islower() or chunk[0] in ",;:)]}"):
            incomplete_boundaries += 1
        if chunk and not re.search(r"[.!?]\s*$", chunk):
            incomplete_boundaries += 1

    max_boundaries = len(chunks) * 2
    return 1 - (incomplete_boundaries / max(1, max_boundaries))


def calculate_concept_splitting(chunks: list[str], key_phrases: list[str]) -> float:
    """Calculate how often key phrases are split across chunks."""
    split_phrases = 0
    lowercase_chunks = [chunk.lower() for chunk in chunks]

    for phrase in key_phrases:
        phrase_lower = phrase.lower()
        complete_in_chunk = any(phrase_lower in chunk for chunk in lowercase_chunks)
        words = phrase_lower.split()

        if len(words) > 1:
            parts_in_different_chunks = False
            for i in range(len(words) - 1):
                part1 = " ".join(words[: i + 1])
                part2 = " ".join(words[i + 1 :])
                for j, chunk1 in enumerate(lowercase_chunks):
                    if part1 in chunk1:
                        for chunk2 in lowercase_chunks[j + 1 :]:
                            if part2 in chunk2 and part1 not in chunk2:
                                parts_in_different_chunks = True
                                break

            if parts_in_different_chunks and not complete_in_chunk:
                split_phrases += 1

    return 1 - (split_phrases / max(1, len(key_phrases)))


def _select_chunker(
    strategy: dict[str, Any],
    use_mock_llm: bool,
) -> Callable[[str], list[Any]]:
    """Return a callable for a configured chunking strategy."""
    strategy_type = strategy["type"]
    if strategy_type == "fixed":
        return lambda document: perform_fixed_size_chunking(
            document,
            chunk_size=strategy.get("size", 1000),
            chunk_overlap=strategy.get("overlap", 0),
        )
    if strategy_type == "semantic":
        return lambda document: perform_semantic_chunking(
            document,
            chunk_size=strategy.get("size", 500),
            chunk_overlap=strategy.get("overlap", 100),
        )
    if strategy_type == "recursive":
        return lambda document: perform_code_chunking(
            document,
            language=strategy.get("language", "python"),
            chunk_size=strategy.get("size", 100),
            chunk_overlap=strategy.get("overlap", 15),
        )
    if strategy_type == "adaptive":
        return lambda document: perform_adaptive_chunking(
            document,
            min_size=strategy.get("min_size", 300),
            max_size=strategy.get("max_size", 1000),
            complexity_measure=strategy.get("complexity_measure", "combined"),
        )
    if strategy_type == "context_enriched":
        if use_mock_llm:
            return lambda document: perform_context_enriched_chunking_mock(
                document,
                chunk_size=strategy.get("size", 500),
                chunk_overlap=strategy.get("overlap", 50),
                window_size=strategy.get("window_size", 1),
            )
        return lambda document: perform_context_enriched_chunking(
            document,
            chunk_size=strategy.get("size", 500),
            chunk_overlap=strategy.get("overlap", 50),
            window_size=strategy.get("window_size", 1),
        )
    if strategy_type == "ai_driven":
        if use_mock_llm:
            return lambda document: perform_ai_driven_chunking_mock(
                document,
                max_chunks=strategy.get("max_chunks", 10),
            )
        return lambda document: perform_ai_driven_chunking(
            document,
            max_chunks=strategy.get("max_chunks", 10),
        )
    raise ValueError(f"Unknown chunking strategy type: {strategy_type}")


def evaluate_chunking_strategies(
    document: str,
    keywords: list[str],
    key_phrases: list[str],
    chunking_strategies: dict[str, dict[str, Any]],
    use_mock_llm: bool = True,
) -> pd.DataFrame:
    """Evaluate chunking strategies with custom metrics."""
    results = []
    for name, strategy in chunking_strategies.items():
        print(f"Evaluating strategy: {name}")
        start_time = time.time()
        chunker = _select_chunker(strategy, use_mock_llm=use_mock_llm)
        chunks = chunker(document)
        processing_time = time.time() - start_time

        chunk_texts = document_texts(chunks)
        keyword_coverage = calculate_keyword_coverage(chunk_texts, keywords)
        chunk_coherence = calculate_chunk_coherence(chunk_texts)
        concept_integrity = calculate_concept_splitting(chunk_texts, key_phrases)

        total_chunks = len(chunks)
        chunk_sizes = [len(chunk_text) for chunk_text in chunk_texts]
        avg_chunk_size = sum(chunk_sizes) / len(chunk_sizes)
        chunk_size_std = (
            sum((size - avg_chunk_size) ** 2 for size in chunk_sizes) / len(chunk_sizes)
        ) ** 0.5
        size_consistency = 1 - (chunk_size_std / max(1, avg_chunk_size))

        results.append(
            {
                "strategy": name,
                "processing_time": round(processing_time, 2),
                "keyword_coverage": round(keyword_coverage, 2),
                "chunk_coherence": round(chunk_coherence, 2),
                "concept_integrity": round(concept_integrity, 2),
                "size_consistency": round(size_consistency, 2),
                "total_chunks": total_chunks,
                "avg_chunk_size": round(avg_chunk_size, 2),
            }
        )

    return pd.DataFrame(results)


def visualize_results(results_df: pd.DataFrame) -> None:
    """Create visualizations of the evaluation results."""
    _, axs = plt.subplots(2, 3, figsize=(18, 12))

    axs[0, 0].bar(results_df["strategy"], results_df["processing_time"])
    axs[0, 0].set_title("Processing Time (seconds)")
    axs[0, 0].set_ylabel("Time (s)")
    axs[0, 0].tick_params(axis="x", rotation=45)

    axs[0, 1].bar(results_df["strategy"], results_df["keyword_coverage"])
    axs[0, 1].set_title("Keyword Coverage")
    axs[0, 1].set_ylabel("Score (0-1)")
    axs[0, 1].tick_params(axis="x", rotation=45)

    axs[0, 2].bar(results_df["strategy"], results_df["concept_integrity"])
    axs[0, 2].set_title("Concept Integrity")
    axs[0, 2].set_ylabel("Score (0-1)")
    axs[0, 2].tick_params(axis="x", rotation=45)

    axs[1, 0].bar(results_df["strategy"], results_df["chunk_coherence"])
    axs[1, 0].set_title("Chunk Coherence")
    axs[1, 0].set_ylabel("Score (0-1)")
    axs[1, 0].tick_params(axis="x", rotation=45)

    axs[1, 1].bar(results_df["strategy"], results_df["total_chunks"])
    axs[1, 1].set_title("Total Number of Chunks")
    axs[1, 1].set_ylabel("Count")
    axs[1, 1].tick_params(axis="x", rotation=45)

    axs[1, 2].bar(results_df["strategy"], results_df["size_consistency"])
    axs[1, 2].set_title("Chunk Size Consistency")
    axs[1, 2].set_ylabel("Score (0-1)")
    axs[1, 2].tick_params(axis="x", rotation=45)

    plt.tight_layout()
    plt.show()


if __name__ == "__main__":
    demo_document = create_dummy_document()
    demo_keywords = [
        "machine learning",
        "supervised learning",
        "unsupervised learning",
        "neural networks",
        "LLMs",
        "fine-tuning",
        "pre-training",
        "reinforcement learning",
        "multimodal learning",
        "federated learning",
        "clustering",
        "classification",
        "regression",
        "PCA",
    ]
    demo_key_phrases = [
        "Large Language Models",
        "Reinforcement Learning from Human Feedback",
        "Principal Component Analysis",
        "Support Vector Machines",
        "decision becomes more difficult",
        "train-test split",
        "natural language processing",
    ]
    demo_chunking_strategies = {
        "fixed_500": {"type": "fixed", "size": 500, "overlap": 0},
        "fixed_500_overlap_100": {"type": "fixed", "size": 500, "overlap": 100},
        "semantic_500": {"type": "semantic", "size": 500, "overlap": 100},
        "adaptive_300_1000": {
            "type": "adaptive",
            "min_size": 300,
            "max_size": 1000,
            "complexity_measure": "combined",
        },
        "context_enriched_500": {
            "type": "context_enriched",
            "size": 500,
            "overlap": 50,
            "window_size": 1,
        },
        "ai_driven_10": {"type": "ai_driven", "max_chunks": 10},
    }

    results_df = evaluate_chunking_strategies(
        demo_document,
        demo_keywords,
        demo_key_phrases,
        demo_chunking_strategies,
        use_mock_llm=True,
    )

    print("\n----- EVALUATION RESULTS -----")
    print(results_df)

    try:
        visualize_results(results_df)
    except Exception as exc:
        print(f"Visualization error: {exc}")

    output_path = Path(__file__).with_name("chunking_evaluation_results.csv")
    results_df.to_csv(output_path, index=False)
    print(f"\nResults exported to '{output_path}'")
