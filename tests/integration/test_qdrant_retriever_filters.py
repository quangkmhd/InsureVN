import logging

from qdrant_client import QdrantClient

from src.models.evidence import HardFilters, RetrievalMode, RetrievalPlan, SourceType
from src.services.document_chunker import DocumentChunker
from src.services.qdrant_retriever import (
    HashingEmbeddingProvider,
    QdrantRetriever,
    RetrievalReadinessError,
    normalize_vietnamese_text,
)


def _chunk_policy(
    *,
    company_code: str,
    document_id: str,
    document_name: str,
    plan_code: str,
    markdown_text: str,
) -> list:
    chunker = DocumentChunker(child_chunk_chars=180, child_chunk_overlap=30)
    return chunker.chunk_markdown(
        markdown_text,
        metadata={
            "company_code": company_code,
            "document_id": document_id,
            "document_type": "policy",
            "document_name": document_name,
            "product_line": "health",
            "plan_code": plan_code,
            "source_path": f"data/processed/{document_id}.md",
            "source_table_id": f"documents:{document_id}",
            "effective_date": "2026-01-01",
        },
    ).child_chunks


def _build_retriever() -> QdrantRetriever:
    retriever = QdrantRetriever(
        client=QdrantClient(":memory:"),
        collection_name="phase_02_test_chunks",
        embedding_provider=HashingEmbeddingProvider(vector_size=64),
        keyword_enabled=True,
    )
    retriever.setup_collection(recreate=True)
    retriever.index_chunks(
        [
            *_chunk_policy(
                company_code="AIA",
                document_id="aia-health",
                document_name="AIA Health Policy",
                plan_code="gold",
                markdown_text=(
                    "# AIA Gold\n\n"
                    "## Thoi gian cho\n\n"
                    "Goi Gold co thoi gian cho 90 ngay cho benh dac biet.\n\n"
                    "## Thuoc dac tri\n\n"
                    "Thuoc Avastin duoc xem xet theo dieu khoan ung thu."
                ),
            ),
            *_chunk_policy(
                company_code="BMI",
                document_id="bmi-health",
                document_name="Bao Minh Health Policy",
                plan_code="standard",
                markdown_text=(
                    "# Bao Minh Standard\n\n"
                    "## Thoi gian cho\n\n"
                    "Goi Standard co thoi gian cho 30 ngay cho benh dac biet.\n\n"
                    "## Thuoc dac tri\n\n"
                    "Thuoc Herceptin duoc xem xet theo dieu khoan ung thu."
                ),
            ),
        ]
    )
    return retriever


def test_retrieve_applies_company_hard_filter_and_returns_parent_evidence() -> None:
    retriever = _build_retriever()

    evidence_items = retriever.retrieve(
        RetrievalPlan(
            search_queries=["thoi gian cho benh dac biet"],
            mode=RetrievalMode.HYBRID,
            filters=HardFilters(company_codes=["AIA"]),
            top_k=3,
        )
    )

    assert evidence_items
    assert {item.source_type for item in evidence_items} == {SourceType.QDRANT_CHUNK}
    assert {item.metadata["company_code"] for item in evidence_items} == {"AIA"}
    assert any(
        "Goi Gold co thoi gian cho 90 ngay" in item.content for item in evidence_items
    )
    assert all(item.metadata["parent_section_id"] for item in evidence_items)


def test_keyword_pillar_finds_exact_policy_terms_when_dense_signal_is_weak() -> None:
    retriever = _build_retriever()

    evidence_items = retriever.retrieve(
        RetrievalPlan(
            search_queries=["Avastin"],
            mode=RetrievalMode.BM25,
            filters=HardFilters(company_codes=["AIA"]),
            top_k=2,
        )
    )

    assert len(evidence_items) == 1
    assert evidence_items[0].metadata["document_id"] == "aia-health"
    assert "Avastin" in evidence_items[0].content


def test_diacritic_normalization_matches_vietnamese_queries() -> None:
    assert normalize_vietnamese_text("bảo hiểm sức khỏe") == "bao hiem suc khoe"

    retriever = _build_retriever()
    evidence_items = retriever.retrieve(
        RetrievalPlan(
            search_queries=["bệnh đặc biệt"],
            mode=RetrievalMode.BM25,
            filters=HardFilters(company_codes=["BMI"]),
            top_k=2,
        )
    )

    assert evidence_items
    assert {item.metadata["company_code"] for item in evidence_items} == {"BMI"}
    assert any(
        "benh dac biet" in normalize_vietnamese_text(item.content)
        for item in evidence_items
    )


def test_production_readiness_rejects_dense_only_degraded_mode() -> None:
    retriever = QdrantRetriever(
        client=QdrantClient(":memory:"),
        collection_name="dense_only_chunks",
        embedding_provider=HashingEmbeddingProvider(vector_size=32),
        keyword_enabled=False,
        allow_dense_only_degraded_mode=True,
    )

    try:
        retriever.assert_production_ready()
    except RetrievalReadinessError as exc:
        assert "keyword retrieval is disabled" in str(exc)
    else:
        raise AssertionError("Dense-only degraded mode must not be production-ready.")


def test_vector_mode_requires_explicit_degraded_mode() -> None:
    retriever = _build_retriever()

    try:
        retriever.retrieve(
            RetrievalPlan(
                search_queries=["thoi gian cho"],
                mode=RetrievalMode.VECTOR,
                filters=HardFilters(company_codes=["AIA"]),
            )
        )
    except RetrievalReadinessError as exc:
        assert "VECTOR retrieval mode is dense-only" in str(exc)
    else:
        raise AssertionError("VECTOR mode must require degraded mode.")


def test_allowed_vector_degraded_mode_logs_warning(caplog) -> None:
    retriever = _build_retriever()
    retriever.allow_dense_only_degraded_mode = True

    with caplog.at_level(logging.WARNING, logger="qdrant_retriever"):
        evidence_items = retriever.retrieve(
            RetrievalPlan(
                search_queries=["thoi gian cho"],
                mode=RetrievalMode.VECTOR,
                filters=HardFilters(company_codes=["AIA"]),
            )
        )

    assert evidence_items
    assert any(
        record.__dict__.get("retrieval_degraded") is True for record in caplog.records
    )


def test_keyword_search_paginates_all_qdrant_scroll_results() -> None:
    first_payload = {
        "company_code": "AIA",
        "document_id": "first-page",
        "document_type": "policy",
        "document_name": "First Page",
        "product_line": "health",
        "plan_code": "gold",
        "section_type": "benefit",
        "page_number": 1,
        "chunk_index": 0,
        "source_path": "data/processed/first.md",
        "source_table_id": "documents:first",
        "effective_date": "2026-01-01",
        "chunk_id": "first-page:benefit:0",
        "parent_section_id": "first-page:benefit",
        "parent_text": "Generic policy wording without the exact token.",
    }
    second_payload = {
        **first_payload,
        "document_id": "second-page",
        "document_name": "Second Page",
        "source_path": "data/processed/second.md",
        "source_table_id": "documents:second",
        "chunk_id": "second-page:benefit:0",
        "parent_section_id": "second-page:benefit",
        "parent_text": "The exact needleterm is only present on the second page.",
    }

    class _Point:
        def __init__(self, payload):
            self.payload = payload

    class _PagedClient:
        def __init__(self) -> None:
            self.offsets = []

        def scroll(self, **kwargs):
            self.offsets.append(kwargs.get("offset"))
            if kwargs.get("offset") is None:
                return [_Point(first_payload)], "next-page"
            return [_Point(second_payload)], None

    client = _PagedClient()
    retriever = QdrantRetriever(
        client=client,
        collection_name="paged",
        embedding_provider=HashingEmbeddingProvider(vector_size=32),
        keyword_enabled=True,
    )

    evidence_items = retriever.retrieve(
        RetrievalPlan(
            search_queries=["needleterm"],
            mode=RetrievalMode.BM25,
            top_k=1,
        )
    )

    assert client.offsets == [None, "next-page"]
    assert len(evidence_items) == 1
    assert evidence_items[0].metadata["document_id"] == "second-page"
