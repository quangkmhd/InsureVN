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
