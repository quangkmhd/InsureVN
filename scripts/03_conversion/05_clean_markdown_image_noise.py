"""Remove generated image links and captions from converted Markdown files."""

from __future__ import annotations

import argparse
import re
from pathlib import Path

MARKER_IMAGE_LINE_RE = re.compile(
    r"^\s*!\[[^\]]*]\([^)]*_img\.(?:jpe?g|png|webp)\)\s*$",
    re.IGNORECASE,
)
MARKER_IMAGE_TOKEN_RE = re.compile(
    r"!\[[^\]]*]\([^)]*_img\.(?:jpe?g|png|webp)\)",
    re.IGNORECASE,
)
GENERATED_CAPTION_PREFIXES = (
    "a ",
    "an ",
    "the ",
    "aia logo",
    "circular diagram",
    "downward arrow",
    "icon ",
    "illustration ",
    "man ",
    "map ",
    "qr code",
    "red booklet",
    "woman ",
)


def clean_markdown_image_noise(markdown_text: str) -> str:
    """Remove Marker image lines and generated English captions.

    Args:
        markdown_text: Markdown text produced by document conversion.

    Returns:
        Markdown text without local generated image links or adjacent captions.
    """
    lines = markdown_text.splitlines()
    cleaned_lines: list[str] = []
    index = 0

    while index < len(lines):
        line = lines[index]
        if not MARKER_IMAGE_LINE_RE.match(line):
            cleaned_lines.append(_clean_inline_image_tokens(line))
            index += 1
            continue

        index = _skip_image_noise(lines, index + 1)

    return _collapse_blank_runs(cleaned_lines)


def clean_markdown_file(path: Path, *, output_path: Path | None = None) -> bool:
    """Clean one Markdown file and write the result.

    Args:
        path: Source Markdown file path.
        output_path: Optional destination path. When omitted, the source file is
            overwritten only if cleaning changes the content.

    Returns:
        True when the cleaned text differs from the original text.
    """
    original_text = path.read_text(encoding="utf-8")
    cleaned_text = clean_markdown_image_noise(original_text)
    changed = cleaned_text != original_text
    destination_path = output_path or path

    if output_path is not None or changed:
        destination_path.parent.mkdir(parents=True, exist_ok=True)
        destination_path.write_text(cleaned_text, encoding="utf-8")

    return changed


def find_markdown_files(input_path: Path) -> list[Path]:
    """Return Markdown files from a file or directory path.

    Args:
        input_path: Markdown file or directory containing Markdown files.

    Returns:
        Sorted Markdown file paths.
    """
    if input_path.is_file():
        return [input_path]
    return sorted(input_path.rglob("*.md"))


def clean_markdown_path(
    input_path: Path,
    *,
    output_dir: Path | None = None,
    dry_run: bool = False,
) -> dict[str, int]:
    """Clean all Markdown files under a file or directory path.

    Args:
        input_path: Markdown file or directory containing Markdown files.
        output_dir: Optional output directory. Directory structure is preserved
            when cleaning a directory.
        dry_run: Count files that would change without writing output.

    Returns:
        Summary counts with ``total`` and ``changed`` keys.
    """
    markdown_files = find_markdown_files(input_path)
    changed_count = 0

    for markdown_file in markdown_files:
        output_path = _build_output_path(
            markdown_file,
            input_path=input_path,
            output_dir=output_dir,
        )
        original_text = markdown_file.read_text(encoding="utf-8")
        cleaned_text = clean_markdown_image_noise(original_text)
        changed = cleaned_text != original_text
        if not changed:
            continue

        changed_count += 1
        if dry_run:
            continue

        destination_path = output_path or markdown_file
        destination_path.parent.mkdir(parents=True, exist_ok=True)
        destination_path.write_text(cleaned_text, encoding="utf-8")

    return {"total": len(markdown_files), "changed": changed_count}


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "input_path",
        type=Path,
        help="Markdown file or directory to clean.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Write cleaned files to this directory instead of editing in place.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only report how many Markdown files would change.",
    )
    return parser.parse_args()


def main() -> None:
    """Run the Markdown image-noise cleaner from the command line."""
    args = parse_args()
    summary = clean_markdown_path(
        args.input_path,
        output_dir=args.output_dir,
        dry_run=args.dry_run,
    )
    action = "would change" if args.dry_run else "changed"
    print(
        f"Processed {summary['total']} Markdown files; {summary['changed']} {action}."
    )


def _skip_image_noise(lines: list[str], index: int) -> int:
    while index < len(lines):
        index = _skip_blank_lines(lines, index)
        paragraph_start = index
        paragraph_lines, index = _read_paragraph(lines, index)
        if not paragraph_lines:
            return index
        if not _is_generated_caption(paragraph_lines):
            return paragraph_start
    return index


def _skip_blank_lines(lines: list[str], index: int) -> int:
    while index < len(lines) and not lines[index].strip():
        index += 1
    return index


def _read_paragraph(lines: list[str], index: int) -> tuple[list[str], int]:
    paragraph_lines: list[str] = []
    while index < len(lines):
        line = lines[index]
        if not line.strip() or MARKER_IMAGE_LINE_RE.match(line):
            break
        paragraph_lines.append(line)
        index += 1
    return paragraph_lines, index


def _is_generated_caption(paragraph_lines: list[str]) -> bool:
    paragraph_text = " ".join(line.strip() for line in paragraph_lines)
    normalized_text = paragraph_text.lower()
    if not normalized_text:
        return False
    if paragraph_text[0] in {"#", "-", "*", "|", "[", "(", "<", ">"}:
        return False
    return normalized_text.startswith(GENERATED_CAPTION_PREFIXES)


def _clean_inline_image_tokens(line: str) -> str:
    return re.sub(r"[ \t]{2,}", " ", MARKER_IMAGE_TOKEN_RE.sub("", line)).rstrip()


def _collapse_blank_runs(lines: list[str]) -> str:
    collapsed_lines: list[str] = []
    blank_count = 0

    for line in lines:
        if line.strip():
            blank_count = 0
            collapsed_lines.append(line)
            continue

        blank_count += 1
        if collapsed_lines and blank_count <= 2:
            collapsed_lines.append("")

    while collapsed_lines and not collapsed_lines[-1].strip():
        collapsed_lines.pop()

    if not collapsed_lines:
        return ""
    return "\n".join(collapsed_lines) + "\n"


def _build_output_path(
    markdown_file: Path,
    *,
    input_path: Path,
    output_dir: Path | None,
) -> Path | None:
    if output_dir is None:
        return None
    if input_path.is_file():
        return output_dir / markdown_file.name
    return output_dir / markdown_file.relative_to(input_path)


if __name__ == "__main__":
    main()
