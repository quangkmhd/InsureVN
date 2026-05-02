import re

def extract_markdown_tables(content):
    # Match blocks of pipe-lines, allowing for whitespace-only lines in between.
    # The block must start and end with a line containing a pipe.
    pattern = r"(?:^.*\|.*(?:\n|$))+(?:[ \t]*(?:\n|$)(?:^.*\|.*(?:\n|$))+)*"
    return [m.strip() for m in re.findall(pattern, content, re.MULTILINE)]

test_content = """
| col 1 | col 2 |
|---|---|
| val 1 | val 2 |

orphan part |

Normal text.
"""

tables = extract_markdown_tables(test_content)
for i, t in enumerate(tables):
    print(f"Table {i+1}:")
    print(f"[{t}]")
