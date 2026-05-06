import unicodedata
from unittest.mock import MagicMock, patch

from langchain_core.embeddings import Embeddings

from src.services.document_chunker import DocumentChunker


class RecordingEmbeddings(Embeddings):
    """Deterministic embeddings that record semantic splitter usage."""

    def __init__(self) -> None:
        """Initialize the call recorder."""
        self.document_batches: list[list[str]] = []

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Return stable vectors for document texts."""
        self.document_batches.append(texts)
        return [[1.0, 0.0] for _ in texts]

    def embed_query(self, _text: str) -> list[float]:
        """Return a stable vector for query text."""
        return [1.0, 0.0]


def _metadata() -> dict:
    return {
        "company_code": "AIA",
        "document_id": "doc-aia-health",
        "document_type": "policy",
        "document_name": "AIA Health Policy",
        "product_line": "health",
        "plan_code": "gold",
        "file_name": "health.md",
        "source_table_id": "documents:1",
        "effective_date": "2026-01-01",
    }


def test_document_chunker_parses_parent_sections_and_child_chunks() -> None:
    markdown_text = """# Bao hiem suc khoe

## Quyen loi nam vien

Nguoi duoc bao hiem duoc chi tra chi phi nam vien.
Han muc toi da la 10000000 VND moi nam.

## Thoi gian cho

Benh dac biet co thoi gian cho 90 ngay.
"""
    chunker = DocumentChunker(child_chunk_chars=80, child_chunk_overlap=20)

    document_chunks = chunker.chunk_markdown(
        markdown_text,
        metadata={
            "company_code": "AIA",
            "document_id": "doc-aia-health",
            "document_type": "policy",
            "document_name": "AIA Health Policy",
            "product_line": "health",
            "plan_code": "gold",
            "file_name": "health.md",
            "source_table_id": "documents:1",
            "effective_date": "2026-01-01",
        },
    )

    assert [section.heading for section in document_chunks.parent_sections] == [
        "Bao hiem suc khoe",
        "Quyen loi nam vien",
        "Thoi gian cho",
    ]
    assert document_chunks.child_chunks
    assert document_chunks.child_chunks[0].chunk_id.startswith(
        "doc-aia-health:bao-hiem-suc-khoe:0"
    )
    assert document_chunks.child_chunks[0].parent_section_id == (
        document_chunks.parent_sections[0].section_id
    )
    assert document_chunks.child_chunks[0].payload["company_code"] == "AIA"
    assert document_chunks.child_chunks[0].payload["file_name"] == "health.md"
    assert "source_path" not in document_chunks.child_chunks[0].payload
    assert document_chunks.child_chunks[0].payload["section_type"] == (
        "bao_hiem_suc_khoe"
    )


def test_document_chunker_normalizes_unicode_to_nfc() -> None:
    decomposed_text = (
        "## Ba\u0309o hie\u0302\u0309m\n\nQuyen loi ba\u0309o hie\u0302\u0309m."
    )
    chunker = DocumentChunker(child_chunk_chars=120, child_chunk_overlap=10)

    document_chunks = chunker.chunk_markdown(
        decomposed_text,
        metadata={
            "company_code": "BV",
            "document_id": "doc-bv",
            "document_type": "policy",
            "document_name": "Bao Viet",
            "product_line": "health",
            "plan_code": None,
            "file_name": "bv.md",
            "source_table_id": "documents:2",
            "effective_date": None,
        },
    )

    child_text = document_chunks.child_chunks[0].text
    assert unicodedata.is_normalized("NFC", child_text)


def test_document_chunker_validates_required_payload_fields() -> None:
    chunker = DocumentChunker()

    try:
        chunker.chunk_markdown(
            "## Section\n\nNo company code.",
            metadata={
                "document_id": "doc-missing-company",
                "document_type": "policy",
                "document_name": "Missing Company",
                "product_line": "health",
                "plan_code": "standard",
                "file_name": "missing.md",
                "source_table_id": "documents:3",
                "effective_date": "2026-01-01",
            },
        )
    except ValueError as exc:
        assert "company_code" in str(exc)
    else:
        raise AssertionError("Expected missing company_code to fail validation.")


def test_document_chunker_allows_optional_filter_payload_fields() -> None:
    chunker = DocumentChunker(child_chunk_chars=120, child_chunk_overlap=20)

    document_chunks = chunker.chunk_markdown(
        "## Thoi gian cho\n\nBenh dac biet co thoi gian cho 90 ngay.",
        metadata={
            "company_code": "AIA",
            "document_id": "doc-aia-health",
            "document_type": "policy",
            "document_name": "AIA Health Policy",
            "product_line": "health",
            "file_name": "health.md",
        },
    )

    payload = document_chunks.child_chunks[0].payload
    assert payload["company_code"] == "AIA"
    assert payload["file_name"] == "health.md"
    assert "plan_code" not in payload
    assert "source_table_id" not in payload
    assert "effective_date" not in payload


def test_document_chunker_omits_unreliable_page_number_payload() -> None:
    chunker = DocumentChunker(child_chunk_chars=200, child_chunk_overlap=0)

    document_chunks = chunker.chunk_markdown(
        "## Quyen loi nam vien\n\nChi tra chi phi nam vien.",
        metadata={
            "company_code": "AIA",
            "document_id": "doc-aia-health",
            "document_type": "policy",
            "document_name": "AIA Health Policy",
            "product_line": "health",
            "file_name": "health.md",
            "page_number": 4,
        },
    )

    payload = document_chunks.child_chunks[0].payload
    assert "page_number" not in payload


def test_document_chunker_marks_table_payload_content_type() -> None:
    markdown_text = (
        "## Bang quyen loi\n\n"
        "| Quyen loi | Han muc |\n"
        "|---|---|\n"
        "| Nam vien | 10000000 |\n"
    )
    chunker = DocumentChunker(
        child_chunk_chars=200,
        child_chunk_overlap=0,
        table_line_ratio_threshold=0.4,
    )

    document_chunks = chunker.chunk_markdown(markdown_text, metadata=_metadata())

    payload = document_chunks.child_chunks[0].payload
    assert payload["content_type"] == "mixed"
    assert payload["has_table"] is True


def test_document_chunker_adds_production_payload_lineage_fields() -> None:
    markdown_text = "## Thoi gian cho\n\nBenh dac biet co thoi gian cho 90 ngay."
    metadata = {
        "company_code": "AIA",
        "document_id": "doc-aia-health",
        "document_type": "policy",
        "document_name": "AIA Health Policy",
        "product_line": "health",
        "plan_code": "gold",
        "file_name": "health.md",
        "source_table_id": "documents:1",
        "effective_date": "2026-01-01",
        "ingestion_version": "rag-2026-05-05",
    }
    chunker = DocumentChunker(child_chunk_chars=120, child_chunk_overlap=20)

    first_chunks = chunker.chunk_markdown(markdown_text, metadata=metadata)
    second_chunks = chunker.chunk_markdown(markdown_text, metadata=metadata)

    first_payload = first_chunks.child_chunks[0].payload
    second_payload = second_chunks.child_chunks[0].payload
    assert first_payload["parent_section_id"] == (
        first_chunks.child_chunks[0].parent_section_id
    )
    assert first_payload["ingestion_version"] == "rag-2026-05-05"
    assert first_payload["content_hash"]
    assert first_payload["content_hash"] == second_payload["content_hash"]
    assert (
        first_payload["content_hash"]
        != chunker.chunk_markdown(
            "## Thoi gian cho\n\nNoi dung da thay doi.",
            metadata=metadata,
        )
        .child_chunks[0]
        .payload["content_hash"]
    )


def test_document_chunker_uses_semantic_chunking_with_size_guard() -> None:
    embeddings = RecordingEmbeddings()
    markdown_text = (
        "## Dieu tri noi tru\n\n"
        + "Chi phi nam vien duoc chi tra theo gioi han chuong trinh. " * 8
        + "Ho so boi thuong can co hoa don va chi dinh cua bac si. " * 8
    )
    chunker = DocumentChunker(
        child_chunk_chars=120,
        child_chunk_overlap=0,
        chunking_strategy="hybrid_semantic",
        semantic_embedding_provider=embeddings,
        semantic_target_chars=10000,
        semantic_max_chars=160,
        semantic_min_chars=40,
    )

    document_chunks = chunker.chunk_markdown(markdown_text, metadata=_metadata())

    assert embeddings.document_batches
    assert len(document_chunks.child_chunks) > 1
    assert all(
        len(child_chunk.text) <= 160 for child_chunk in document_chunks.child_chunks
    )


def test_document_chunker_splits_table_heavy_sections_with_repeated_header() -> None:
    table_rows = "\n".join(
        f"| {index} | Benh vien {index} | Ha Noi |" for index in range(1, 10)
    )
    markdown_text = (
        "# Danh sach co so y te\n\n"
        "| STT | Ten co so y te | Tinh thanh |\n"
        "|---|---|---|\n"
        f"{table_rows}\n"
    )
    chunker = DocumentChunker(
        child_chunk_chars=120,
        child_chunk_overlap=0,
        chunking_strategy="hybrid_semantic",
        table_chunk_chars=170,
        table_line_ratio_threshold=0.4,
    )

    document_chunks = chunker.chunk_markdown(markdown_text, metadata=_metadata())
    child_texts = [child_chunk.text for child_chunk in document_chunks.child_chunks]

    assert len(child_texts) > 1
    assert all("| STT | Ten co so y te | Tinh thanh |" in text for text in child_texts)
    assert any("Benh vien 1" in text for text in child_texts)
    assert any("Benh vien 9" in text for text in child_texts)


def test_document_chunker_updates_langfuse_with_chunking_summary() -> None:
    fake_langfuse_client = MagicMock()
    markdown_text = (
        "# Danh sach co so y te\n\n"
        "| STT | Ten co so y te |\n"
        "|---|---|\n"
        "| 1 | Benh vien A |\n"
        "| 2 | Benh vien B |\n"
    )
    chunker = DocumentChunker(
        child_chunk_chars=80,
        child_chunk_overlap=0,
        chunking_strategy="hybrid_semantic",
        table_chunk_chars=120,
        table_line_ratio_threshold=0.4,
    )

    with patch(
        "src.services.observability.get_client", return_value=fake_langfuse_client
    ):
        document_chunks = chunker.chunk_markdown(markdown_text, metadata=_metadata())

    chunking_metadata_calls = [
        call.kwargs["metadata"]["chunking"]
        for call in fake_langfuse_client.update_current_span.call_args_list
        if "metadata" in call.kwargs and "chunking" in call.kwargs["metadata"]
    ]

    assert chunking_metadata_calls
    chunking_metadata = chunking_metadata_calls[-1]
    assert chunking_metadata["strategy"] == "hybrid_semantic"
    assert chunking_metadata["parent_section_count"] == len(
        document_chunks.parent_sections
    )
    assert chunking_metadata["child_chunk_count"] == len(document_chunks.child_chunks)
    assert chunking_metadata["table_heavy_section_count"] == 1
    assert chunking_metadata["semantic_section_count"] == 0
    assert chunking_metadata["recursive_section_count"] == 0
    assert chunking_metadata["empty_section_count"] == 0
    assert chunking_metadata["fallback_chunk_count"] == 0
    assert chunking_metadata["chunk_length_max"] == max(
        len(child_chunk.text) for child_chunk in document_chunks.child_chunks
    )
