---
name: meaningful-naming
description: Use when creating any identifier (agents, variables, parameters, attributes, or domain objects) to ensure they are descriptive and domain-specific rather than generic.
---

# Meaningful Naming

## Overview
Every identifier in the codebase should clearly describe its purpose, domain context, and specific role. Generic names like `data`, `obj`, `graph`, `tools`, `llm`, or `inputs` should be replaced with descriptive, meaningful alternatives.

## When to Use
- Declaring variables, constants, or class attributes.
- Defining function parameters or return types.
- Naming modules, classes, and packages.
- Creating keys for dictionaries or properties in JSON objects.

### Symptoms of Poor Naming
- **Framework Leakage**: Using library-specific terms (e.g., `graph`, `llm`, `vector_store`) as primary variable names instead of domain terms.
- **Vagueness**: Using single-word names that don't differentiate from other similar objects (e.g., `tools` vs `insurance_search_tools`).
- **Ambiguity**: Names that could represent multiple things in the same context (e.g., `result` in a function that computes multiple values).
- **Abbreviations**: Using `req`, `resp`, `msg` instead of `request`, `response`, `message`.

## Core Pattern: [Domain/Context] + [Noun]

### Before (Generic)
```python
def process(data):
    tools = get_tools()
    llm = init_model()
    inputs = {"q": data}
    res = llm.invoke(inputs, tools=tools)
    return res
```

### After (Meaningful)
```python
def process_claim_request(claim_data):
    insurance_tools = get_insurance_tools()
    claim_analysis_llm = init_claim_analysis_model()
    analysis_inputs = {"query": claim_data}
    claim_analysis_result = claim_analysis_llm.invoke(analysis_inputs, tools=insurance_tools)
    return claim_analysis_result
```

## Quick Reference Table
| Generic/Bad | Meaningful/Good | Context |
|-------------|-----------------|---------|
| `graph`, `agent` | `database_agent`, `policy_graph` | Agentic workers |
| `tools` | `sqlite_tools`, `search_utility_tools` | Tool definitions |
| `llm`, `model` | `chat_llm`, `extraction_model` | AI model instances |
| `inputs`, `data` | `agent_inputs`, `policy_metadata` | Data structures |
| `query`, `q` | `user_question`, `search_query` | Search/Query inputs |
| `res`, `out` | `analysis_result`, `ocr_content` | Outputs |

## Common Mistakes
- **Redundancy with Type**: `string_name` (redundant) vs `customer_name`.
- **Over-Abstraction**: `handler` when it's specifically a `claim_submission_handler`.
- **Inconsistent Depth**: Mixing `db_agent` with a generic `self.graph` in the same class.

## Red Flags - STOP and Rename
- You used a name shorter than 4 characters (unless it's a standard loop index like `i`).
- The name exists in another scope with a different meaning.
- You have to read the implementation to know what the variable holds.
- You used a framework-provided name (like `graph`) for a domain-level instance.
