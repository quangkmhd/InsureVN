"""Test the new strip + line-based extraction logic on an actual corrupted source file."""
import re
from pathlib import Path

MARKER = "**Diễn giải dữ liệu:**"

def strip_previous_interpretations(content: str) -> str:
    pattern = re.escape(MARKER) + r".*?(?=\n(?:#{1,6}\s|\|)|$)"
    content = re.sub(pattern, "", content, flags=re.DOTALL)
    content = re.sub(r"\n{3,}", "\n\n", content)
    return content

def _is_table_row(line: str) -> bool:
    stripped = line.strip()
    return stripped.startswith("|")

def extract_markdown_tables(content: str) -> list[tuple[int, int, str]]:
    lines = content.split("\n")
    tables = []
    char_pos = 0
    block_start = -1
    block_lines = []

    for i, line in enumerate(lines):
        if _is_table_row(line):
            if block_start == -1:
                block_start = char_pos
            block_lines.append(line)
        else:
            if block_lines:
                if len(block_lines) >= 2:
                    block_text = "\n".join(block_lines)
                    block_end = char_pos
                    tables.append((block_start, block_end, block_text))
                block_start = -1
                block_lines = []
        char_pos += len(line) + 1

    if block_lines and len(block_lines) >= 2:
        block_text = "\n".join(block_lines)
        tables.append((block_start, char_pos - 1, block_text))

    return tables


# Test with the actual corrupted file
src = Path("/home/quangnhvn34/dev/me/InsureVN/data/health_insurance/health_insurance_markdowns/aia.com.vn/2711-BHSK-Bung-Gia-Luc-Quy-tac-dieu-khoan-mau-2025/2711-BHSK-Bung-Gia-Luc-Quy-tac-dieu-khoan-mau-2025.md")
raw = src.read_text(encoding="utf-8")

print(f"=== BEFORE STRIP ===")
print(f"Markers found: {raw.count(MARKER)}")
print(f"Pipe lines: {sum(1 for l in raw.splitlines() if '|' in l)}")

clean = strip_previous_interpretations(raw)
print(f"\n=== AFTER STRIP ===")
print(f"Markers found: {clean.count(MARKER)}")
print(f"Pipe lines: {sum(1 for l in clean.splitlines() if '|' in l)}")

tables = extract_markdown_tables(clean)
print(f"\n=== TABLES FOUND ===")
print(f"Number of tables: {len(tables)}")
for i, (start, end, text) in enumerate(tables):
    lines = text.split("\n")
    print(f"\nTable {i+1}: {len(lines)} rows, chars [{start}:{end}]")
    print(f"  First row: {lines[0][:80]}...")
    print(f"  Last row:  {lines[-1][:80]}...")

# Verify the insertion would be at the right place
print(f"\n=== INSERTION VERIFICATION ===")
for i, (start, end, text) in enumerate(tables):
    after = clean[end:end+100].replace("\n", "\\n")
    print(f"Table {i+1} → text AFTER table: [{after[:60]}]")
