import importlib.util
import sys
from pathlib import Path


def _load_cleaner_script():
    script_path = (
        Path(__file__).resolve().parents[2]
        / "scripts"
        / "03_conversion"
        / "05_clean_markdown_image_noise.py"
    )
    spec = importlib.util.spec_from_file_location(
        "clean_markdown_image_noise", script_path
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_removes_marker_image_lines_and_following_english_captions() -> None:
    script = _load_cleaner_script()
    markdown_text = (
        "## Đồng hành xuyên suốt Trọn đời an tâm\n"
        "\n"
        "Nội dung tiếng Việt cần giữ lại.\n"
        "\n"
        "![A man holding a baby, smiling, against a pink background.]"
        "(d5fc881e4328d6a2e76c9576408ced49_img.jpg)\n"
        "\n"
        "A man in a light-colored jacket and pants is holding a baby who is "
        "wearing a blue top and blue pants. They are both smiling.\n"
        "\n"
        "A man holding a baby, smiling, against a pink background.\n"
        "\n"
        "## Tại sao cần sự bảo vệ trọn đời?\n"
    )

    cleaned_text = script.clean_markdown_image_noise(markdown_text)

    assert "_img.jpg" not in cleaned_text
    assert "A man in a light-colored jacket" not in cleaned_text
    assert "A man holding a baby" not in cleaned_text
    assert "Nội dung tiếng Việt cần giữ lại." in cleaned_text
    assert "## Tại sao cần sự bảo vệ trọn đời?" in cleaned_text


def test_keeps_non_caption_sources_after_qr_code_caption() -> None:
    script = _load_cleaner_script()
    markdown_text = """Chi phí y tế phổ biến:

![QR code linking to source (3)](67eed3534d6b2680b4a187d027e71594_img.jpg)

QR code linking to source (3)

(3) AON, Global Medical Trend rate (2025)

Teladoc Health là công ty hàng đầu trên thế giới.
"""

    cleaned_text = script.clean_markdown_image_noise(markdown_text)

    assert "![QR code" not in cleaned_text
    assert "QR code linking to source" not in cleaned_text
    assert "(3) AON, Global Medical Trend rate (2025)" in cleaned_text
    assert "Teladoc Health là công ty hàng đầu trên thế giới." in cleaned_text


def test_clean_markdown_file_can_write_to_output_path(tmp_path) -> None:
    script = _load_cleaner_script()
    input_path = tmp_path / "input.md"
    output_path = tmp_path / "output.md"
    input_path.write_text(
        (
            "Giữ lại.\n\n"
            "![Icon of a hospital bed.](dd14009e1ff79cb3499669b8f6efe9a4_img.jpg)\n\n"
            "Icon of a hospital bed.\n\n"
            "**Phòng và Giường bệnh**\n"
        ),
        encoding="utf-8",
    )

    changed = script.clean_markdown_file(input_path, output_path=output_path)

    assert changed is True
    assert input_path.read_text(encoding="utf-8").startswith("Giữ lại.")
    cleaned_text = output_path.read_text(encoding="utf-8")
    assert "_img.jpg" not in cleaned_text
    assert "Icon of a hospital bed." not in cleaned_text
    assert "**Phòng và Giường bệnh**" in cleaned_text


def test_removes_inline_marker_images_without_dropping_text() -> None:
    script = _load_cleaner_script()
    markdown_text = (
        "Thành viên của **BIDV** "
        "![BIDV logo](d66ff64371a51729ac8c1cdaa685ba6f_img.jpg)\n"
        "![Phone icon](986082884a323475ef59af56b5554821_img.jpg) "
        "**CALL CENTER**\n"
    )

    cleaned_text = script.clean_markdown_image_noise(markdown_text)

    assert "_img.jpg" not in cleaned_text
    assert "Thành viên của **BIDV**" in cleaned_text
    assert "**CALL CENTER**" in cleaned_text
