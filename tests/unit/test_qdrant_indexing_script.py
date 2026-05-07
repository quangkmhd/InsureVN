import importlib.util
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace


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


def test_indexing_script_help_runs_from_project_root() -> None:
    script_path = (
        Path(__file__).resolve().parents[2]
        / "scripts"
        / "06_db_ingestion"
        / "04_index_qdrant_documents.py"
    )

    result = subprocess.run(
        [sys.executable, str(script_path), "--help"],
        cwd=Path(__file__).resolve().parents[2],
        capture_output=True,
        check=False,
        text=True,
    )

    assert result.returncode == 0
    assert "Index processed Markdown policy documents into Qdrant" in result.stdout


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
    assert report["skipped_duplicate_count"] == 0
    assert report["readiness_result"] == "not_checked_dry_run"
    assert report["documents"][0]["file_name"] == markdown_path.name
    assert "source_path" not in report["documents"][0]


def test_dry_run_report_counts_duplicate_chunks(tmp_path) -> None:
    script = _load_indexing_script()
    first_path = tmp_path / "aia_health_first.md"
    second_path = tmp_path / "aia_health_second.md"
    markdown_text = (
        "# AIA Health\n\n## Waiting Period\n\nSpecial diseases wait 90 days."
    )
    first_path.write_text(markdown_text, encoding="utf-8")
    second_path.write_text(markdown_text, encoding="utf-8")

    report = script.build_dry_run_report(
        document_paths=[first_path, second_path],
        metadata={
            "company_code": "AIA",
            "document_id": "aia-health",
            "document_type": "policy",
            "document_name": "AIA Health Policy",
            "product_line": "health",
            "plan_code": "gold",
            "source_table_id": "documents:1",
            "effective_date": "2026-01-01",
            "ingestion_version": "rag-2026-05-05",
        },
        child_chunk_chars=200,
        child_chunk_overlap=20,
    )

    assert report["document_count"] == 2
    assert report["chunk_count"] == 4
    assert report["unique_chunk_count"] == 2
    assert report["skipped_duplicate_count"] == 2


def test_build_embedding_provider_uses_configured_google_provider(monkeypatch) -> None:
    script = _load_indexing_script()
    captured = {}

    class FakeGoogleGenAIEmbeddingProvider:
        def __init__(self, **kwargs) -> None:
            captured.update(kwargs)

    monkeypatch.setattr(
        script,
        "GoogleGenAIEmbeddingProvider",
        FakeGoogleGenAIEmbeddingProvider,
    )

    provider = script.build_embedding_provider(
        provider="google_genai",
        model_name="gemini-embedding-2",
        google_api_key="test-google-key",
        vector_size=768,
    )

    assert isinstance(provider, FakeGoogleGenAIEmbeddingProvider)
    assert captured == {
        "model_name": "gemini-embedding-2",
        "google_api_key": "test-google-key",
        "vector_size": 768,
    }


def test_build_chunks_passes_hybrid_semantic_configuration(
    monkeypatch,
    tmp_path,
) -> None:
    script = _load_indexing_script()
    markdown_path = tmp_path / "aia_health.md"
    markdown_path.write_text("## Section\n\nSemantic text.", encoding="utf-8")
    semantic_embedding_provider = object()
    captured = {}

    class FakeDocumentChunker:
        def __init__(self, **kwargs) -> None:
            captured.update(kwargs)

        def chunk_markdown(self, markdown_text, metadata):
            captured["markdown_text"] = markdown_text
            captured["metadata"] = metadata
            return SimpleNamespace(child_chunks=["child-chunk"])

    monkeypatch.setattr(script, "DocumentChunker", FakeDocumentChunker)

    chunks = script.build_chunks(
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
        child_chunk_chars=1200,
        child_chunk_overlap=150,
        chunking_strategy="hybrid_semantic",
        semantic_embedding_provider=semantic_embedding_provider,
        semantic_target_chars=1400,
        semantic_max_chars=3500,
        semantic_min_chars=350,
        semantic_breakpoint_type="interquartile",
        semantic_breakpoint_amount=1.5,
        table_line_ratio_threshold=0.55,
        table_chunk_chars=3500,
    )

    assert chunks == ["child-chunk"]
    assert captured["chunking_strategy"] == "hybrid_semantic"
    assert captured["semantic_embedding_provider"] is semantic_embedding_provider
    assert captured["semantic_target_chars"] == 1400
    assert captured["table_chunk_chars"] == 3500
    assert captured["metadata"]["file_name"] == markdown_path.name
    assert "source_path" not in captured["metadata"]


def test_build_sparse_embedding_provider_uses_langchain_fastembed(monkeypatch) -> None:
    script = _load_indexing_script()
    captured = {}

    class FakeFastEmbedSparse:
        def __init__(self, **kwargs) -> None:
            captured.update(kwargs)

    monkeypatch.setattr(script, "FastEmbedSparse", FakeFastEmbedSparse)

    provider = script.build_sparse_embedding_provider("Qdrant/bm25")

    assert isinstance(provider, FakeFastEmbedSparse)
    assert captured == {"model_name": "Qdrant/bm25"}


def test_build_embedding_provider_rejects_unimplemented_provider() -> None:
    script = _load_indexing_script()

    try:
        script.build_embedding_provider(
            provider="custom",
            model_name="custom-model",
            google_api_key="",
            vector_size=768,
        )
    except ValueError as exc:
        message = str(exc)
        assert "Unsupported RAG_EMBEDDING_PROVIDER" in message
        assert "google_genai" in message
    else:
        raise AssertionError("Unsupported embedding providers must fail explicitly.")
