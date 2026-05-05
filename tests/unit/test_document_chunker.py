import unicodedata

from src.services.document_chunker import DocumentChunker


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
            "source_path": "data/processed/aia/health.md",
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
            "source_path": "data/processed/bv.md",
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
                "source_path": "data/processed/missing.md",
                "source_table_id": "documents:3",
                "effective_date": "2026-01-01",
            },
        )
    except ValueError as exc:
        assert "company_code" in str(exc)
    else:
        raise AssertionError("Expected missing company_code to fail validation.")


def test_document_chunker_adds_production_payload_lineage_fields() -> None:
    markdown_text = "## Thoi gian cho\n\nBenh dac biet co thoi gian cho 90 ngay."
    metadata = {
        "company_code": "AIA",
        "document_id": "doc-aia-health",
        "document_type": "policy",
        "document_name": "AIA Health Policy",
        "product_line": "health",
        "plan_code": "gold",
        "source_path": "data/processed/aia/health.md",
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
