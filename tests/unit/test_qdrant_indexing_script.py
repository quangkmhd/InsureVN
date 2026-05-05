import importlib.util
from pathlib import Path


def _load_indexing_script():
    script_path = (
        Path(__file__).resolve().parents[2]
        / "scripts"
        / "06_db_ingestion"
        / "04_index_qdrant_documents.py"
    )
    spec = importlib.util.spec_from_file_location("qdrant_indexing_script", script_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_dry_run_report_counts_parent_sections_and_child_chunks(tmp_path) -> None:
    script = _load_indexing_script()
    markdown_path = tmp_path / "aia_health.md"
    markdown_path.write_text(
        "# AIA Health\n\n## Waiting Period\n\nSpecial diseases wait 90 days.",
        encoding="utf-8",
    )

    report = script.build_dry_run_report(
        document_paths=[markdown_path],
        metadata={
            "company_code": "AIA",
            "document_id": "aia-health",
            "document_type": "policy",
            "document_name": "AIA Health Policy",
            "product_line": "health",
            "plan_code": "gold",
            "source_table_id": "documents:1",
            "effective_date": "2026-01-01",
        },
        child_chunk_chars=200,
        child_chunk_overlap=20,
    )

    assert report["document_count"] == 1
    assert report["parent_section_count"] == 2
    assert report["chunk_count"] == 2
    assert report["documents"][0]["source_path"] == str(markdown_path)


def test_build_embedding_provider_rejects_unimplemented_model() -> None:
    script = _load_indexing_script()

    try:
        script.build_embedding_provider("gemini-embedding-2")
    except ValueError as exc:
        assert "Unsupported RAG_EMBEDDING_MODEL" in str(exc)
    else:
        raise AssertionError("Unsupported embedding models must fail explicitly.")
