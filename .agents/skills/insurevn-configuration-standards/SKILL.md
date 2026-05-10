---
name: insurevn-configuration-standards
description: Use when adding new agents, services, or LLM-dependent components to InsureVN, or refactoring configuration in src/core/config.py.
---

# InsureVN Configuration Standards

## Overview
InsureVN uses a decoupled, explicit, and provider-agnostic configuration system. This ensures that every component can be independently tuned, supports indirect model resolution, and follows a strict naming convention.

## Core Principles
1. **Explicit Over Implicit**: No hidden global defaults for LLM providers or models. Every component should require explicit configuration or inherit from a global that is also explicitly set.
2. **Indirect Model Resolution**: Models should never be hardcoded strings. They should be variable names (e.g., `OLLAMA_LLM_MODEL`) that are resolved to their actual values at runtime.
3. **Uppercase Provider Naming**: Use `GOOGLE`, `OLLAMA`, `OPENROUTER`, `NVIDIA` directly. Do NOT map them to library-specific names like `google_genai`.
4. **Prefix-Based Ownership**: Support intuitive component-specific prefixes (e.g., `SQL_AGENT_`, `SEARCH_AGENT_`) in addition to legacy names.

## When to Use
- Adding a new Agent (e.g., `DocumentClassifierAgent`).
- Adding a new retrieval service (e.g., `VectorSearchService`).
- Refactoring `src/core/config.py`.
- Updating `.env` or `.env.example`.

## Implementation Pattern

### 1. Centralized Config (`src/core/config.py`)
Use `_normalize_provider`, `_resolve_indirect`, `_resolve_api_key`, and `_resolve_base_url`.

```python
# ✅ GOOD: Support multiple prefixes and indirect resolution
self.DOC_AGENT_PROVIDER: str = self._normalize_provider(
    os.getenv("DOC_AGENT_PROVIDER", self.LLM_PROVIDER)
)
self.DOC_AGENT_MODEL: str = self._resolve_indirect(
    os.getenv("DOC_AGENT_MODEL", self.LLM_MODEL)
)
self.DOC_AGENT_API_KEY: str = (
    os.getenv("DOC_AGENT_API_KEY") or self._resolve_api_key("DOC_AGENT")
)
```

### 2. Environment Variables (`.env`)
Always use uppercase for providers and indirect names for models and API keys.

```env
# ✅ GOOD
SQL_AGENT_PROVIDER=OLLAMA
SQL_AGENT_MODEL=OLLAMA_LLM_MODEL
SQL_AGENT_API_KEY=Ollama_API_Key_1
Ollama_API_Key_1=...
```

### 3. Service Level
Use case-insensitive checks for providers.

```python
# ✅ GOOD
if provider.upper() == "OLLAMA":
    # handle ollama specific logic
```

## Common Mistakes
| Mistake | Correction |
|---------|------------|
| Hardcoding "google_genai" | Use "GOOGLE" and let the factory handle mapping. |
| Hardcoding model strings | Use `_resolve_indirect` to allow .env to point to another variable. |
| Forgetting component prefixes | Always support `[COMPONENT]_PROVIDER` to allow independent tuning. |
| Using "ollama" as fallback | Default to `self.LLM_PROVIDER` which is empty by default, forcing explicit setup. |

## Red Flags
- `LLM_PROVIDER` defaulting to `ollama` or any specific provider.
- No support for `_resolve_indirect` in model fields.
- Mapping `GOOGLE` to `google_genai` inside the `Settings` class.
