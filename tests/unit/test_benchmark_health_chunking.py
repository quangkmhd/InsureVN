import importlib.util
import sys
from pathlib import Path
from types import ModuleType


def _load_benchmark_script() -> ModuleType:
    script_path = (
        Path(__file__).resolve().parents[2]
        / "scripts"
        / "08_chunking_compare"
        / "benchmark_health_chunking.py"
    )
    spec = importlib.util.spec_from_file_location(
        "benchmark_health_chunking",
        script_path,
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_langchain_markdown_header_chunks_keep_markdown_table_intact() -> None:
    script = _load_benchmark_script()
    markdown_text = (
        "# Bao hiem suc khoe\n\n"
        "## Quyen loi noi tru\n\n"
        "Goi bao hiem chi tra theo bang quyen loi sau.\n\n"
        "| Hang muc | Han muc |\n"
        "|---|---:|\n"
        "| Dieu tri noi tru | 1 ty dong |\n"
        "| Cap cuu | 100 trieu dong |\n\n"
        "## Loai tru\n\n"
        "Khong chi tra cac dieu tri thuoc danh muc loai tru."
    )
    document = script.SourceDocument(
        doc_id="bao-hiem-suc-khoe",
        file_name="bao_hiem_suc_khoe.md",
        path="bao_hiem_suc_khoe.md",
        text=markdown_text,
    )

    chunks = script.langchain_markdown_header_chunks(document)
    table_chunks = [chunk for chunk in chunks if "| Hang muc | Han muc |" in chunk.text]

    assert len(table_chunks) == 1
    assert "|---|---:|" in table_chunks[0].text
    assert "| Dieu tri noi tru | 1 ty dong |" in table_chunks[0].text
    assert "| Cap cuu | 100 trieu dong |" in table_chunks[0].text
    assert all(
        "| Dieu tri noi tru | 1 ty dong |" not in chunk.text
        for chunk in chunks
        if chunk is not table_chunks[0]
    )
    assert script.DISPLAY_NAMES["langchain_markdown_header"] == (
        "LangChain MarkdownHeader"
    )


def test_databricks_strategy_chunks_are_registered_and_source_mapped() -> None:
    script = _load_benchmark_script()
    markdown_text = (
        "# Bao hiem suc khoe\n\n"
        "## Quyen loi noi tru\n\n"
        "Goi bao hiem chi tra chi phi nam vien. Quyen loi cap cuu duoc ap dung "
        "theo bang quyen loi.\n\n"
        "| Hang muc | Han muc |\n"
        "|---|---:|\n"
        "| Dieu tri noi tru | 1 ty dong |\n\n"
        "## Loai tru\n\n"
        "Khong chi tra cac dieu tri thuoc danh muc loai tru."
    )
    document = script.SourceDocument(
        doc_id="bao-hiem-suc-khoe",
        file_name="bao_hiem_suc_khoe.md",
        path="bao_hiem_suc_khoe.md",
        text=markdown_text,
    )
    databricks_methods = {
        "databricks_fixed_size": script.databricks_fixed_size_chunks(
            document,
            size_tokens=80,
            overlap_tokens=10,
        ),
        "databricks_semantic": script.databricks_semantic_chunks(
            document,
            size_tokens=80,
            overlap_tokens=10,
        ),
        "databricks_recursive_code": script.databricks_recursive_code_chunks(
            document,
            size_tokens=80,
            overlap_tokens=10,
        ),
        "databricks_adaptive": script.databricks_adaptive_chunks(document),
    }

    for method, chunks in databricks_methods.items():
        assert script.DISPLAY_NAMES[method].startswith("Databricks")
        assert chunks
        assert all(chunk.method == method for chunk in chunks)
        assert all(
            0 <= chunk.start < chunk.end <= len(document.text) for chunk in chunks
        )


def test_context_enriched_and_fake_ai_methods_are_not_reported() -> None:
    script = _load_benchmark_script()
    excluded_methods = {
        "late_chunking",
        "parent_child",
        "databricks_context_enriched",
        "databricks_ai_dynamic",
    }

    assert excluded_methods.isdisjoint(script.DISPLAY_NAMES)
