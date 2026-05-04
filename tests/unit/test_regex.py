import re


def extract_markdown_tables(content):
    # Match blocks of consecutive lines where each line contains at least one | character.
    pattern = r"(?:(?:^|\n)[^\n]*\|[^\n]*)+"
    return [m.strip() for m in re.findall(pattern, content)]


test_content = """
| col 1 | col 2 |
|---|---|
| val 1 | val 2 |
orphan part |

Normal text.
"""

tables = extract_markdown_tables(test_content)
for i, t in enumerate(tables):
    print(f"Table {i + 1}:")
    print(f"[{t}]")
