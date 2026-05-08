"""Registry for active insurance chunking strategies."""

from __future__ import annotations

from collections.abc import Iterable

from langchain_core.embeddings import Embeddings
from llama_index.core.llms import LLM

from src.eval.chunking.base import ChunkingStrategy, StrategySpec
from src.eval.chunking.heading_level_table_safe import HeadingLevelTableSafeChunking
from src.eval.chunking.hierarchical_header_recursive import (
    HierarchicalHeaderRecursiveChunking,
)
from src.eval.chunking.insurance_contract_hybrid_late import (
    InsuranceContractHybridLateChunking,
)
from src.eval.chunking.llamaindex_markdown_element import (
    LlamaIndexMarkdownElementChunking,
)
from src.eval.chunking.llm_markdown_optimal import LLMMarkdownOptimalChunking
from src.eval.chunking.markdown_header_recursive_table import (
    MarkdownHeaderRecursiveTableChunking,
)
from src.eval.chunking.markdown_then_semantic import MarkdownThenSemanticChunking
from src.eval.chunking.semantic import SemanticChunking
from src.eval.chunking.table_as_one_hybrid import TableAsOneHybridChunking

DEFAULT_INSURANCE_STRATEGY_NAMES = (
    "semantic_embedding",
    "heading_level_table_safe",
    "markdown_header_recursive_table",
    "insurance_contract_hybrid_late",
    "llm_markdown_optimal",
    "markdown_then_semantic",
    "table_as_one_hybrid",
    "llamaindex_markdown_element",
    "hierarchical_header_recursive",
)


def available_strategy_specs() -> list[StrategySpec]:
    """Return strategy metadata without instantiating models."""

    return [
        StrategySpec(
            name="semantic_embedding",
            description=SemanticChunking.description,
            requires_embeddings=True,
        ),
        StrategySpec(
            name="heading_level_table_safe",
            description=HeadingLevelTableSafeChunking.description,
        ),
        StrategySpec(
            name="markdown_header_recursive_table",
            description=MarkdownHeaderRecursiveTableChunking.description,
        ),
        StrategySpec(
            name="insurance_contract_hybrid_late",
            description=InsuranceContractHybridLateChunking.description,
            requires_embeddings=True,
            requires_llm=True,
        ),
        StrategySpec(
            name="llm_markdown_optimal",
            description=LLMMarkdownOptimalChunking.description,
            requires_llm=True,
        ),
        StrategySpec(
            name="markdown_then_semantic",
            description=MarkdownThenSemanticChunking.description,
            requires_embeddings=True,
        ),
        StrategySpec(
            name="table_as_one_hybrid",
            description=TableAsOneHybridChunking.description,
        ),
        StrategySpec(
            name="llamaindex_markdown_element",
            description=LlamaIndexMarkdownElementChunking.description,
            requires_llm=True,
        ),
        StrategySpec(
            name="hierarchical_header_recursive",
            description=HierarchicalHeaderRecursiveChunking.description,
        ),
    ]


def all_strategy_names() -> list[str]:
    """Return every implemented strategy name."""

    return [spec.name for spec in available_strategy_specs()]


def default_strategy_names() -> list[str]:
    """Return the curated strategy set for insurance document evaluation."""

    return list(DEFAULT_INSURANCE_STRATEGY_NAMES)


def build_strategies(
    selected_names: Iterable[str] | None,
    semantic_chunking_embeddings: Embeddings | None,
    markdown_element_llm: LLM | None,
    markdown_element_num_workers: int,
    hybrid_retrieval_embeddings: Embeddings | None,
    heading_cut_level: int,
    heading_max_chars: int,
    heading_min_chars: int,
    heading_max_table_rows: int,
    chunk_size: int,
    chunk_overlap: int,
) -> list[ChunkingStrategy]:
    """Instantiate selected active strategies."""

    names = list(selected_names or DEFAULT_INSURANCE_STRATEGY_NAMES)
    validate_strategy_names(names)
    strategies: list[ChunkingStrategy] = []
    for name in names:
        if name == "semantic_embedding":
            strategies.append(
                SemanticChunking(
                    require_dependency(
                        semantic_chunking_embeddings,
                        strategy_name=name,
                        dependency_name="semantic embeddings",
                    )
                )
            )
        elif name == "heading_level_table_safe":
            strategies.append(
                HeadingLevelTableSafeChunking(
                    cut_level=heading_cut_level,
                    max_chars=heading_max_chars,
                    min_chars=heading_min_chars,
                    max_table_rows=heading_max_table_rows,
                )
            )
        elif name == "markdown_header_recursive_table":
            strategies.append(
                MarkdownHeaderRecursiveTableChunking(chunk_size, chunk_overlap)
            )
        elif name == "insurance_contract_hybrid_late":
            strategies.append(
                InsuranceContractHybridLateChunking(
                    retrieval_embeddings=require_dependency(
                        hybrid_retrieval_embeddings,
                        strategy_name=name,
                        dependency_name="hybrid retrieval embeddings",
                    ),
                    table_summary_llm=require_dependency(
                        markdown_element_llm,
                        strategy_name=name,
                        dependency_name="table-summary LLM",
                    ),
                    chunk_size=chunk_size,
                    chunk_overlap=chunk_overlap,
                    table_summary_workers=markdown_element_num_workers,
                )
            )
        elif name == "llm_markdown_optimal":
            strategies.append(
                LLMMarkdownOptimalChunking(
                    llm=require_dependency(
                        markdown_element_llm,
                        strategy_name=name,
                        dependency_name="chunking LLM",
                    ),
                    cut_level=heading_cut_level,
                    max_chars=heading_max_chars,
                    min_chars=heading_min_chars,
                    max_table_rows=heading_max_table_rows,
                    num_workers=markdown_element_num_workers,
                )
            )
        elif name == "markdown_then_semantic":
            strategies.append(
                MarkdownThenSemanticChunking(
                    require_dependency(
                        semantic_chunking_embeddings,
                        strategy_name=name,
                        dependency_name="semantic embeddings",
                    )
                )
            )
        elif name == "table_as_one_hybrid":
            strategies.append(TableAsOneHybridChunking(chunk_size, chunk_overlap))
        elif name == "llamaindex_markdown_element":
            strategies.append(
                LlamaIndexMarkdownElementChunking(
                    llm=require_dependency(
                        markdown_element_llm,
                        strategy_name=name,
                        dependency_name="table-summary LLM",
                    ),
                    num_workers=markdown_element_num_workers,
                )
            )
        elif name == "hierarchical_header_recursive":
            strategies.append(
                HierarchicalHeaderRecursiveChunking(chunk_size, chunk_overlap)
            )
    return strategies


def select_strategies(
    strategies: list[ChunkingStrategy],
    selected_names: Iterable[str] | None,
) -> list[ChunkingStrategy]:
    """Select strategies by name, raising on unknown names."""

    if selected_names is None:
        selected_names = DEFAULT_INSURANCE_STRATEGY_NAMES
    selected = list(selected_names)
    strategy_by_name = {strategy.name: strategy for strategy in strategies}
    unknown = sorted(set(selected) - set(strategy_by_name))
    if unknown:
        known = ", ".join(sorted(strategy_by_name))
        msg = f"Unknown chunking strategies: {unknown}. Known strategies: {known}"
        raise ValueError(msg)
    return [strategy_by_name[name] for name in selected]


def validate_strategy_names(names: Iterable[str]) -> None:
    """Raise if any requested strategy is not active."""

    known_names = set(DEFAULT_INSURANCE_STRATEGY_NAMES)
    unknown = sorted(set(names) - known_names)
    if unknown:
        known = ", ".join(DEFAULT_INSURANCE_STRATEGY_NAMES)
        msg = f"Unknown chunking strategies: {unknown}. Known strategies: {known}"
        raise ValueError(msg)


def require_dependency[DependencyT](
    value: DependencyT | None,
    strategy_name: str,
    dependency_name: str,
) -> DependencyT:
    """Return a required dependency or raise a strategy-specific error."""

    if value is None:
        msg = f"{strategy_name} requires configured {dependency_name}."
        raise ValueError(msg)
    return value
