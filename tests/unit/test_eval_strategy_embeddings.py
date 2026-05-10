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
from src.eval.embeddings import (
    build_retrieval_embeddings,
    prepare_qwen3_retrieval_texts,
    prepare_sentence_transformer_texts,
)
from src.eval.embeddings.adapters import (
    GoogleGenAIEmbeddings,
    Qwen3AutoModelEmbeddings,
    extract_google_retry_delay_seconds,
)
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


def test_runner_does_not_reuse_google_retrieval_embeddings_for_semantic_chunking() -> (
    None
):
    config = ChunkingRunConfig(
        embedding_provider="google_genai",
        embedding_model_name="gemini-embedding-2",
        embedding_device=None,
        semantic_chunking_embedding_provider="sentence_transformers",
        semantic_chunking_embedding_model=FAST_MULTILINGUAL_EMBEDDING_MODEL,
        semantic_chunking_embedding_device="cuda",
    )

    assert not can_reuse_retrieval_embeddings_for_semantic_chunking(config)


def test_prepare_sentence_transformer_texts_adds_e5_retrieval_prefixes() -> None:
    assert prepare_sentence_transformer_texts(
        model_name="intfloat/multilingual-e5-large",
        texts=["Quyền lợi nội trú"],
        purpose="retrieval_query",
    ) == ["query: Quyền lợi nội trú"]
    assert prepare_sentence_transformer_texts(
        model_name="intfloat/multilingual-e5-large",
        texts=["Điều khoản chi trả"],
        purpose="retrieval_document",
    ) == ["passage: Điều khoản chi trả"]


def test_prepare_qwen3_retrieval_texts_adds_query_prompt() -> None:
    assert prepare_qwen3_retrieval_texts(
        texts=["Quyền lợi nội trú là gì?"],
        purpose="retrieval_query",
    ) == [
        "Instruct: Given a web search query, retrieve relevant passages "
        "that answer the query\nQuery: Quyền lợi nội trú là gì?"
    ]
    assert prepare_qwen3_retrieval_texts(
        texts=["Điều khoản chi trả"],
        purpose="retrieval_document",
    ) == ["Điều khoản chi trả"]


def test_build_retrieval_embeddings_uses_qwen3_transformers_adapter() -> None:
    embeddings = build_retrieval_embeddings(
        provider="sentence_transformers",
        model_name="Qwen/Qwen3-Embedding-8B",
        batch_size=4,
        device="cuda",
    )

    assert isinstance(embeddings, Qwen3AutoModelEmbeddings)
    assert embeddings.batch_size == 4


def test_extract_google_retry_delay_seconds_from_quota_error() -> None:
    error = RuntimeError(
        "ClientError: 429 RESOURCE_EXHAUSTED. Please retry in 51.96621762s."
    )

    assert extract_google_retry_delay_seconds(error) == 51.96621762


def test_google_embeddings_wait_for_retry_delay_when_all_keys_hit_quota(
    monkeypatch,
) -> None:
    embeddings = GoogleGenAIEmbeddings(
        model_name="gemini-embedding-2",
        google_api_key="key-1",
        google_api_keys=("key-1", "key-2"),
        batch_size=2,
    )
    embeddings._clients = [object(), object()]
    sleep_calls: list[float] = []
    fake_time = {"now": 100.0}

    def fake_monotonic() -> float:
        return fake_time["now"]

    def fake_sleep(seconds: float) -> None:
        sleep_calls.append(seconds)
        fake_time["now"] += seconds

    monkeypatch.setattr(
        "src.eval.embeddings.adapters.time.monotonic",
        fake_monotonic,
    )
    call_count = 0

    def fake_embed(
        _client: object, _texts: list[str], _task_type: str
    ) -> list[list[float]]:
        nonlocal call_count
        call_count += 1
        if call_count <= 2:
            raise RuntimeError(
                "ClientError: 429 RESOURCE_EXHAUSTED. "
                "Please retry in 1.5s. "
                "{'details': [{'@type': 'type.googleapis.com/google.rpc.RetryInfo', "
                "'retryDelay': '1s'}]}"
            )
        return [[0.1, 0.2]]

    monkeypatch.setattr("src.eval.embeddings.adapters.time.sleep", fake_sleep)

    assert embeddings._embed_with_failover(
        fake_embed,
        ["quyen loi noi tru"],
        "RETRIEVAL_DOCUMENT",
    ) == [[0.1, 0.2]]
    assert sleep_calls == [1.5]
    assert embeddings._client_index == 0


def test_google_embeddings_disable_invalid_key_after_first_failure() -> None:
    embeddings = GoogleGenAIEmbeddings(
        model_name="gemini-embedding-2",
        google_api_key="key-1",
        google_api_keys=("key-1", "key-2"),
        batch_size=2,
    )
    invalid_client = object()
    valid_client = object()
    embeddings._clients = [invalid_client, valid_client]
    calls: list[object] = []

    def fake_embed(
        client: object, _texts: list[str], _task_type: str
    ) -> list[list[float]]:
        calls.append(client)
        if client is invalid_client:
            raise RuntimeError("400 API_KEY_INVALID")
        return [[0.3, 0.4]]

    assert embeddings._embed_with_failover(
        fake_embed,
        ["quyen loi noi tru"],
        "RETRIEVAL_DOCUMENT",
    ) == [[0.3, 0.4]]
    assert calls == [invalid_client, valid_client]
    assert embeddings._client_disabled == [True, False]
