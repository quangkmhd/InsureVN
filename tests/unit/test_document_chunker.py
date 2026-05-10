import unicodedata
from unittest.mock import MagicMock, patch

import pytest

from src.services.chunking.document_chunker import DocumentChunker


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


def test_document_chunker_defaults_to_hierarchical_chunks() -> None:
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

    assert chunker.chunking_strategy == "hierarchical_header_recursive"
    assert [section.heading for section in document_chunks.parent_sections] == [
        "Quyen loi nam vien",
        "Thoi gian cho",
    ]
    assert document_chunks.child_chunks
    assert document_chunks.child_chunks[0].chunk_id.startswith(
        "doc-aia-health:quyen-loi-nam-vien:0"
    )
    assert document_chunks.child_chunks[0].parent_section_id == (
        document_chunks.parent_sections[0].section_id
    )
    assert document_chunks.child_chunks[0].payload["company_code"] == "AIA"
    assert document_chunks.child_chunks[0].payload["file_name"] == "health.md"
    assert "source_path" not in document_chunks.child_chunks[0].payload
    assert document_chunks.child_chunks[0].payload["chunking_strategy"] == (
        "hierarchical_header_recursive"
    )
    assert document_chunks.child_chunks[0].payload["section_type"] == (
        "quyen_loi_nam_vien"
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


def test_document_chunker_slugifies_vietnamese_d_letter() -> None:
    chunker = DocumentChunker(child_chunk_chars=120, child_chunk_overlap=0)

    document_chunks = chunker.chunk_markdown(
        "## Điều trị nội trú\n\nChi trả chi phí điều trị nội trú.",
        metadata=_metadata(),
    )

    parent_section = document_chunks.parent_sections[0]
    child_chunk = document_chunks.child_chunks[0]
    assert parent_section.section_id == "doc-aia-health:dieu-tri-noi-tru:0"
    assert child_chunk.chunk_id == "doc-aia-health:dieu-tri-noi-tru:0:chunk:0"
    assert child_chunk.payload["section_type"] == "dieu_tri_noi_tru"


def test_document_chunker_generates_unique_chunk_ids_for_repeated_headings() -> None:
    markdown_text = """### An tâm trọn đời

Bảo vệ từ 30 ngày tuổi đến 100 tuổi.

### An tâm trọn đời

| Quyền lợi | Cơ bản | Nâng cao |
|---|---|---|
| STBH | 150.000.000 | 350.000.000 |
"""
    chunker = DocumentChunker(child_chunk_chars=200, child_chunk_overlap=0)

    document_chunks = chunker.chunk_markdown(markdown_text, metadata=_metadata())

    chunk_ids = [child_chunk.chunk_id for child_chunk in document_chunks.child_chunks]
    assert len(chunk_ids) == len(set(chunk_ids))
    assert all(
        chunk_id.startswith("doc-aia-health:an-tam-tron-doi:0:chunk:")
        for chunk_id in chunk_ids
    )


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


def test_document_chunker_rejects_blank_required_payload_fields() -> None:
    chunker = DocumentChunker()
    metadata = {**_metadata(), "company_code": "   "}

    with pytest.raises(ValueError, match="company_code"):
        chunker.chunk_markdown("## Section\n\nBlank company code.", metadata=metadata)


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


def test_document_chunker_hierarchical_strategy_adds_header_payload_metadata() -> None:
    markdown_text = (
        "# Bao hiem suc khoe\n\n"
        "Mo dau san pham.\n\n"
        "## Quyen loi noi tru\n\n"
        "Chi tra chi phi nam vien theo han muc."
    )
    chunker = DocumentChunker(
        child_chunk_chars=120,
        child_chunk_overlap=0,
        chunking_strategy="hierarchical_header_recursive",
    )

    document_chunks = chunker.chunk_markdown(markdown_text, metadata=_metadata())

    benefit_chunk = next(
        child_chunk
        for child_chunk in document_chunks.child_chunks
        if "Chi tra chi phi nam vien" in child_chunk.text
    )
    payload = benefit_chunk.payload
    assert payload["chunking_strategy"] == "hierarchical_header_recursive"
    assert payload["header_hierarchy"] == [
        "Bao hiem suc khoe",
        "Quyen loi noi tru",
    ]
    assert payload["header_path"] == "Bao hiem suc khoe > Quyen loi noi tru"
    assert payload["header_level"] == 2
    assert payload["section_heading"] == "Quyen loi noi tru"
    assert payload["header_1"] == "Bao hiem suc khoe"
    assert payload["header_2"] == "Quyen loi noi tru"
    assert payload["section_type"] == "quyen_loi_noi_tru"
    assert "parent_text" not in payload
    assert all(
        payload[field] not in {None, ""}
        for field in (
            "company_code",
            "document_id",
            "document_type",
            "document_name",
            "product_line",
            "section_type",
            "parent_section_id",
            "file_name",
            "content_hash",
            "ingestion_version",
            "header_path",
            "section_heading",
        )
    )


def test_document_chunker_requires_hierarchical_lineage_payload_fields() -> None:
    payload = {
        "company_code": "AIA",
        "document_id": "doc-aia-health",
        "document_type": "policy",
        "document_name": "AIA Health Policy",
        "product_line": "health",
        "section_type": "benefit",
        "chunk_index": 0,
        "parent_section_id": "doc-aia-health:benefit:0",
        "file_name": "health.md",
        "content_hash": "abc",
        "ingestion_version": "test-v1",
    }

    with pytest.raises(ValueError, match="chunking_strategy"):
        DocumentChunker.validate_payload(
            payload,
            expected_chunking_strategy="hierarchical_header_recursive",
        )


def test_document_chunker_rejects_invalid_hierarchical_lineage_values() -> None:
    payload = {
        "company_code": "AIA",
        "document_id": "doc-aia-health",
        "document_type": "policy",
        "document_name": "AIA Health Policy",
        "product_line": "health",
        "section_type": "benefit",
        "chunk_index": 0,
        "parent_section_id": "doc-aia-health:benefit:0",
        "file_name": "health.md",
        "content_hash": "abc",
        "ingestion_version": "test-v1",
        "chunking_strategy": "hierarchical_header_recursive",
        "header_hierarchy": "Benefit",
        "header_path": "Benefit",
        "header_level": -1,
        "section_heading": "Benefit",
    }

    with pytest.raises(ValueError, match="header_hierarchy"):
        DocumentChunker.validate_payload(
            payload,
            expected_chunking_strategy="hierarchical_header_recursive",
        )


def test_document_chunker_rejects_removed_legacy_strategies() -> None:
    for removed_strategy in ("recursive", "hybrid_semantic"):
        with pytest.raises(ValueError, match="hierarchical_header_recursive"):
            DocumentChunker(chunking_strategy=removed_strategy)


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
    assert chunking_metadata["strategy"] == "hierarchical_header_recursive"
    assert chunking_metadata["parent_section_count"] == len(
        document_chunks.parent_sections
    )
    assert chunking_metadata["child_chunk_count"] == len(document_chunks.child_chunks)
    assert chunking_metadata["recursive_section_count"] == len(
        document_chunks.parent_sections
    )
    assert chunking_metadata["empty_section_count"] == 0
    assert chunking_metadata["chunk_length_max"] == max(
        len(child_chunk.text) for child_chunk in document_chunks.child_chunks
    )


def test_document_chunker_captures_pre_heading_preamble() -> None:
    markdown_text = """AIA logo featuring a stylized mountain.

SỐNG KHỎE HƠN, LÂU HƠN

## Quyen loi nam vien

Chi tra chi phi nam vien.
"""
    chunker = DocumentChunker(child_chunk_chars=200, child_chunk_overlap=20)

    document_chunks = chunker.chunk_markdown(markdown_text, metadata=_metadata())

    headings = [section.heading for section in document_chunks.parent_sections]
    all_chunk_text = " ".join(
        child_chunk.text for child_chunk in document_chunks.child_chunks
    )
    assert (
        "AIA Health Policy" in headings
        or "Introduction" in headings
        or any(
            "AIA logo" in section.text for section in document_chunks.parent_sections
        )
    )
    assert "SỐNG KHỎE HƠN" in all_chunk_text
    assert "AIA logo" in all_chunk_text
