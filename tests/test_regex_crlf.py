import re

def extract_markdown_tables(content):
    # Match any block of consecutive lines where each line contains at least one |
    # Use re.MULTILINE to make ^ and $ work at line boundaries.
    pattern = r"(?:^.*\|.*(?:\n|$))+"
    return [m.strip() for m in re.findall(pattern, content, re.MULTILINE)]

test_content = "| col 1 | col 2 |\r\n|---|---|\r\n| val 1 | val 2 |\r\n"

tables = extract_markdown_tables(test_content)
for i, t in enumerate(tables):
    print(f"Table {i+1}:")
    print(f"[{t}]")
    print(f"Repr: {repr(t)}")
