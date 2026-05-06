import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace


def _load_indexer_script():
    script_path = (
        Path(__file__).resolve().parents[2]
        / "scripts"
        / "06_db_ingestion"
        / "09_index_all_markdowns.py"
    )
    spec = importlib.util.spec_from_file_location(
        "health_markdown_indexer", script_path
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_build_document_metadata_uses_path_and_table_mapping(tmp_path) -> None:
    script = _load_indexer_script()
    markdown_dir = tmp_path / "health_insurance_markdowns"
    markdown_path = (
        markdown_dir / "aia.com.vn" / "Quy-tac-suc-khoe" / "Quy-tac-suc-khoe.md"
    )
    markdown_path.parent.mkdir(parents=True)
    markdown_path.write_text("## Quy tac\n\nNoi dung.", encoding="utf-8")
    relative_key = markdown_path.relative_to(markdown_dir).as_posix()
    table_mapping = {
        relative_key: {
            "tables": [
                {
                    "source_table_id": 123,
                    "file_name": "table_p4_n1.json",
                    "table_type": "benefit_items",
                    "page_number": 4,
                }
            ]
        }
    }

    metadata = script.build_document_metadata(
        markdown_path,
        markdown_dir=markdown_dir,
        table_mapping=table_mapping,
        ingestion_version="test-v1",
    )

    assert metadata["company_code"] == "AIA"
    assert metadata["document_id"] == "aia_com_vn_quy_tac_suc_khoe_quy_tac_suc_khoe"
    assert metadata["document_type"] == "terms_and_rules"
    assert metadata["product_line"] == "health"
    assert metadata["source_relative_path"] == relative_key
    assert metadata["has_mapped_tables"] is True
    assert metadata["table_count"] == 1
    assert metadata["table_types"] == ["benefit_items"]
    assert metadata["source_table_ids"] == [123]
    assert metadata["table_files"] == ["table_p4_n1.json"]


def test_default_indexer_paths_target_interpreted_cleaned_markdowns() -> None:
    script = _load_indexer_script()

    assert script.DEFAULT_MARKDOWN_DIR.name == (
        "health_insurance_markdowns_interpreted_cleaned"
    )
    assert script.DEFAULT_TABLE_MAPPING_PATH.parent.name == "health_insurance_markdowns"


def test_run_indexing_pipeline_indexes_qdrant_and_imports_neo4j(tmp_path) -> None:
    script = _load_indexer_script()
    markdown_dir = tmp_path / "health_insurance_markdowns"
    markdown_path = markdown_dir / "bic.vn" / "policy" / "policy.md"
    markdown_path.parent.mkdir(parents=True)
    markdown_path.write_text(
        (
            "## Plan: Gold\nBenefits:\n- Nam vien\n\n"
            "| Quyen loi | Han muc |\n|---|---|\n| Noi tru | 100 |"
        ),
        encoding="utf-8",
    )
    table_mapping_path = markdown_dir / "table_mapping.json"
    table_mapping_path.write_text("{}", encoding="utf-8")

    class FakeQdrantRetriever:
        def __init__(self) -> None:
            self.recreate = None
            self.indexed_chunks = []

        def setup_collection(self, *, recreate: bool = False) -> None:
            self.recreate = recreate

        def index_chunks(self, chunks) -> None:
            self.indexed_chunks.extend(chunks)

    class FakeNeo4jStore:
        def __init__(self) -> None:
            self.schema_ensured = False
            self.graph_documents = []

        def ensure_schema(self) -> None:
            self.schema_ensured = True

        def import_graph_documents(self, graph_documents) -> None:
            self.graph_documents.extend(graph_documents)

    class FakeGraphAdapter:
        def from_document(self, document, chunks):
            return SimpleNamespace(
                document_id=document.document_id,
                chunk_count=len(
                    [
                        chunk
                        for chunk in chunks
                        if chunk["document_id"] == document.document_id
                    ]
                ),
            )

    qdrant_retriever = FakeQdrantRetriever()
    neo4j_store = FakeNeo4jStore()

    report = script.run_indexing_pipeline(
        markdown_dir=markdown_dir,
        table_mapping_path=table_mapping_path,
        ingestion_version="test-v1",
        recreate_qdrant=True,
        qdrant_retriever=qdrant_retriever,
        neo4j_store=neo4j_store,
        graph_adapter=FakeGraphAdapter(),
        chunking_strategy="recursive",
    )

    assert report["document_count"] == 1
    assert report["chunk_count"] == len(qdrant_retriever.indexed_chunks)
    assert report["qdrant_indexed"] is True
    assert report["neo4j_imported"] is True
    assert qdrant_retriever.recreate is True
    assert neo4j_store.schema_ensured is True
    assert len(neo4j_store.graph_documents) == 1
    assert any(
        chunk.payload["content_type"] in {"mixed", "table"}
        for chunk in qdrant_retriever.indexed_chunks
    )
