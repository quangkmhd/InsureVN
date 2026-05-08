# Databricks RAG Chunking Strategy Examples

Source article:
https://community.databricks.com/t5/technical-blog/the-ultimate-guide-to-chunking-strategies-for-rag-applications/ba-p/113089

This folder splits the article's code examples into one runnable Python file per
chunking strategy, plus evaluation and best-practice helper code. The article's
rendered snippets contain several missing closing parentheses in the HTML view;
these files keep the same function boundaries and behavior while fixing syntax
so they can be imported and compiled.

Files:

- `fixed_size_chunking.py`
- `semantic_chunking.py`
- `recursive_code_chunking.py`
- `adaptive_chunking.py`
- `context_enriched_chunking.py`
- `ai_driven_dynamic_chunking.py`
- `evaluation_framework.py`
- `best_practices_guidelines.py`
- `common.py`
- `chunking_evaluation_results.csv` demo output from `evaluation_framework.py`

Optional local dependencies for running every script:

```bash
pip install -r scripts/09_databricks_chunking_strategies/requirements.txt
```

Databricks-backed examples require Databricks authentication and a queryable
serving endpoint. The mock functions can be used locally without Databricks.
