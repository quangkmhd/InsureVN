from pathlib import Path

from langchain_core.embeddings import Embeddings

from src.eval.chunking.hierarchical_header_recursive import (
    HierarchicalHeaderRecursiveChunking,
)
from src.eval.chunking.insurance_contract_hybrid_late import (
    InsuranceContractHybridLateChunking,
)
from src.eval.chunking.markdown_then_semantic import MarkdownThenSemanticChunking
from src.eval.chunking.registry import default_strategy_names, validate_strategy_names
from src.eval.chunking.semantic import SemanticChunking
from src.eval.config import FAST_MULTILINGUAL_EMBEDDING_MODEL, ChunkingRunConfig
from src.eval.corpus import build_line_offsets
from src.eval.models import CorpusDocument
from src.eval.runner import can_reuse_retrieval_embeddings_for_semantic_chunking


class FakeBenchmarkEmbeddings(Embeddings):
    batch_size = 4
    dimension = 2

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [[1.0, 0.0] for _ in texts]

    def embed_query(self, _text: str) -> list[float]:
        return [1.0, 0.0]


def test_semantic_chunking_uses_semantic_embeddings_for_retrieval() -> None:
    embeddings = FakeBenchmarkEmbeddings()

    strategy = SemanticChunking(embeddings)

    assert strategy.retrieval_embeddings is embeddings


def test_markdown_then_semantic_uses_semantic_embeddings_for_retrieval() -> None:
    embeddings = FakeBenchmarkEmbeddings()

    strategy = MarkdownThenSemanticChunking(embeddings)

    assert strategy.retrieval_embeddings is embeddings


def test_insurance_contract_hybrid_uses_standard_retrieval_embeddings() -> None:
    embeddings = FakeBenchmarkEmbeddings()
    source_text = "# Quyền lợi\n\nNội dung quyền lợi bảo hiểm nội trú."
    document = CorpusDocument(
        source_path="bao_viet/test.md",
        absolute_path=Path("test.md"),
        provider="bao_viet",
        text=source_text,
        line_offsets=build_line_offsets(source_text),
    )
    strategy = InsuranceContractHybridLateChunking(
        retrieval_embeddings=embeddings,
        table_summary_llm=None,
        chunk_size=200,
        chunk_overlap=0,
    )

    chunks = strategy.chunk_document(document)

    assert strategy.retrieval_embeddings is embeddings
    assert chunks
    assert all(chunk.embedding is None for chunk in chunks)
    assert all("late_span_start" not in chunk.metadata for chunk in chunks)


def test_default_eval_strategy_is_hierarchical_header_recursive() -> None:
    assert default_strategy_names() == ["hierarchical_header_recursive"]
    validate_strategy_names(["semantic_embedding", "hierarchical_header_recursive"])


def test_hierarchical_header_recursive_adds_non_null_lineage_metadata() -> None:
    source_text = (
        "# Bao hiem suc khoe\n\n"
        "Mo dau.\n\n"
        "## Quyen loi noi tru\n\n"
        "Chi tra chi phi nam vien theo han muc."
    )
    document = CorpusDocument(
        source_path="aia.com.vn/policy.md",
        absolute_path=Path("policy.md"),
        provider="aia.com.vn",
        text=source_text,
        line_offsets=build_line_offsets(source_text),
    )
    strategy = HierarchicalHeaderRecursiveChunking(chunk_size=120, chunk_overlap=0)

    chunks = strategy.chunk_document(document)

    benefit_chunk = next(
        chunk for chunk in chunks if "Chi tra chi phi nam vien" in chunk.text
    )
    metadata = benefit_chunk.metadata
    assert metadata["document_source_path"] == "aia.com.vn/policy.md"
    assert metadata["document_provider"] == "aia.com.vn"
    assert metadata["header_hierarchy"] == [
        "Bao hiem suc khoe",
        "Quyen loi noi tru",
    ]
    assert metadata["header_path"] == "Bao hiem suc khoe > Quyen loi noi tru"
    assert metadata["header_level"] == 2
    assert metadata["section_title"] == "Quyen loi noi tru"
    assert metadata["parent_section_length"] > 0
    assert metadata["chunk_length"] == len(benefit_chunk.text)
    assert all(
        metadata[field] not in {None, ""}
        for field in (
            "document_source_path",
            "document_provider",
            "header_path",
            "section_title",
            "parent_section_length",
            "chunk_length",
        )
    )


def test_runner_reuses_retrieval_embeddings_for_matching_semantic_model() -> None:
    config = ChunkingRunConfig(
        embedding_model_name=FAST_MULTILINGUAL_EMBEDDING_MODEL,
        embedding_device="cuda",
        semantic_chunking_embedding_provider="sentence_transformers",
        semantic_chunking_embedding_model=FAST_MULTILINGUAL_EMBEDDING_MODEL,
        semantic_chunking_embedding_device="cuda",
    )

    assert can_reuse_retrieval_embeddings_for_semantic_chunking(config)


def test_runner_does_not_reuse_retrieval_embeddings_for_other_semantic_device() -> None:
    config = ChunkingRunConfig(
        embedding_model_name=FAST_MULTILINGUAL_EMBEDDING_MODEL,
        embedding_device="cuda",
        semantic_chunking_embedding_provider="sentence_transformers",
        semantic_chunking_embedding_model=FAST_MULTILINGUAL_EMBEDDING_MODEL,
        semantic_chunking_embedding_device="cpu",
    )

    assert not can_reuse_retrieval_embeddings_for_semantic_chunking(config)


def test_runner_does_not_reuse_retrieval_embeddings_for_other_semantic_provider() -> (
    None
):
    config = ChunkingRunConfig(
        embedding_model_name=FAST_MULTILINGUAL_EMBEDDING_MODEL,
        embedding_device="cuda",
        semantic_chunking_embedding_provider="ollama",
        semantic_chunking_embedding_model=FAST_MULTILINGUAL_EMBEDDING_MODEL,
        semantic_chunking_embedding_device="cuda",
    )

    assert not can_reuse_retrieval_embeddings_for_semantic_chunking(config)
