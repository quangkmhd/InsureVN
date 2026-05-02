# Langfuse Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Migrate the tracing solution from LangSmith to Langfuse, a self-hostable open-source alternative.

**Architecture:** We will remove LangSmith environment variables from `src/core/config.py` and replace them with Langfuse variables (`LANGFUSE_SECRET_KEY`, `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_HOST`). In `src/agents/database_agent.py`, we will initialize the `langfuse.langchain.CallbackHandler` and pass it to the LangGraph execution via the `config` dictionary's `callbacks` list.

**Tech Stack:** Python `logging`, LangChain (LangGraph), Langfuse (`langfuse` package).

---

### Task 1: Update Environment Configuration

**Files:**
- Modify: `src/core/config.py`
- Modify: `tests/unit/test_config.py`

- [ ] **Step 1: Write the failing test**

```python
# Modify tests/unit/test_config.py
import os
from src.core.config import settings

def test_langfuse_settings_loaded(monkeypatch):
    # Mock environment variables
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk-lf-test")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk-lf-test")
    monkeypatch.setenv("LANGFUSE_HOST", "http://localhost:3000")
    
    # Re-evaluate the properties or ensure they are present
    assert hasattr(settings, "LANGFUSE_PUBLIC_KEY")
    assert hasattr(settings, "LANGFUSE_SECRET_KEY")
    assert hasattr(settings, "LANGFUSE_HOST")
    
    # Ensure LangSmith variables are removed
    assert not hasattr(settings, "LANGCHAIN_TRACING_V2")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_config.py -v`
Expected: FAIL due to missing Langfuse attributes and presence of LangSmith attributes.

- [ ] **Step 3: Write minimal implementation**

```python
# Modify src/core/config.py
import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env file
env_path = Path(__file__).parent.parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

class Settings:
    PROJECT_NAME: str = "InsureVN"
    
    # Database
    SQLITE_DB_PATH: str = os.getenv("SQLITE_DB_PATH", "database/insurevn.db")
    
    # Langfuse Tracing
    LANGFUSE_PUBLIC_KEY: str = os.getenv("LANGFUSE_PUBLIC_KEY", "")
    LANGFUSE_SECRET_KEY: str = os.getenv("LANGFUSE_SECRET_KEY", "")
    LANGFUSE_HOST: str = os.getenv("LANGFUSE_HOST", "http://localhost:3000")
    
    @property
    def DATABASE_URL(self) -> str:
        return f"sqlite:///{self.SQLITE_DB_PATH}"

settings = Settings()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_config.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/core/config.py tests/unit/test_config.py
git commit -m "refactor: replace LangSmith config with Langfuse config"
```

### Task 2: Install Langfuse Dependency

- [ ] **Step 1: Install langfuse package**

Run: `pip install langfuse`

- [ ] **Step 2: Update requirements if available**
*(We skip modifying a requirements file as none were found in the standard format, but we ensure the package is installed in the local environment).*

### Task 3: Integrate Langfuse CallbackHandler into Database Agent

**Files:**
- Modify: `src/agents/database_agent.py`
- Modify: `tests/unit/test_database_agent.py`

- [ ] **Step 1: Write the failing test for DatabaseAgent invoke config**

```python
# Modify tests/unit/test_database_agent.py (Update test_database_agent_invoke_with_config)
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from src.agents.database_agent import DatabaseAgent

@pytest.mark.asyncio
async def test_database_agent_invoke_with_langfuse_callback():
    # Setup mock graph
    mock_graph = AsyncMock()
    mock_graph.ainvoke.return_value = {"messages": [MagicMock(content="Answer")]}
    
    agent = DatabaseAgent(graph=mock_graph)
    
    # Test invoke without passing explicit config, should inject callbacks
    result = await agent.invoke("Hello")
    
    assert result == "Answer"
    
    # Ensure graph.ainvoke was called with the config containing callbacks
    mock_graph.ainvoke.assert_called_once()
    call_args = mock_graph.ainvoke.call_args[1]
    
    config_arg = call_args.get("config")
    assert config_arg is not None
    assert "callbacks" in config_arg
    # Note: We won't strictly check the type of the callback here to keep the test simple, 
    # but we ensure the 'callbacks' key is present and is a list.
    assert isinstance(config_arg["callbacks"], list)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_database_agent.py::test_database_agent_invoke_with_langfuse_callback -v`
Expected: FAIL because `callbacks` are not injected by default.

- [ ] **Step 3: Write minimal implementation**

```python
# Modify src/agents/database_agent.py
from __future__ import annotations
from typing import Any, List, Optional
from langchain.agents import create_agent
from src.tools.mcp_client import get_sqlite_mcp_tools
import os
from dotenv import load_dotenv
from langchain.chat_models import init_chat_model
from src.core.logger import get_logger
from langfuse.langchain import CallbackHandler

# Load environment variables from .env
load_dotenv()

logger = get_logger(__name__)

class DatabaseAgent:
    def __init__(self, graph: Any):
        self.graph = graph
        
    @classmethod
    async def create(cls) -> DatabaseAgent:
        """Factory method to initialize the agent asynchronously."""
        logger.info("Initializing DatabaseAgent")
        
        tools = await get_sqlite_mcp_tools()
        model_name = os.getenv("LLM_MODEL")
        model_provider = os.getenv("LLM_PROVIDER")
        api_key = os.getenv("LLM_API_KEY")
        base_url = os.getenv("LLM_BASE_URL")
        
        init_kwargs: dict[str, Any] = {"temperature": 0}
        
        if api_key:
            init_kwargs["api_key"] = api_key
        if base_url:
            init_kwargs["base_url"] = base_url
            
        is_ollama = (model_provider == "ollama") or (model_name and "ollama" in model_name.lower())
        if is_ollama and api_key:
            init_kwargs["client_kwargs"] = {"headers": {"Authorization": f"Bearer {api_key}"}}
            
        llm = init_chat_model(model_name, model_provider=model_provider, **init_kwargs)

        system_prompt = (
            "You are the DatabaseAgent for the InsureVN system. "
            "Your sole responsibility is to query the SQLite database using the provided tools "
            "and answer the user's question accurately based on the returned data. "
            "Do not guess or make up data."
        )
        graph = create_agent(llm, tools=tools, system_prompt=system_prompt)
        logger.info("DatabaseAgent initialized successfully")
        return cls(graph)
        
    async def invoke(self, query: str, config: Optional[dict] = None) -> str:
        """Invoke the agent with a query."""
        logger.info(f"Invoking DatabaseAgent with query: {query}")
        
        inputs = {"messages": [("user", query)]}
        
        # Initialize Langfuse CallbackHandler for tracing
        langfuse_handler = CallbackHandler()
        
        run_config = config or {}
        if "callbacks" not in run_config:
            run_config["callbacks"] = []
            
        run_config["callbacks"].append(langfuse_handler)
        
        try:
            result = await self.graph.ainvoke(inputs, config=run_config)
            logger.info("DatabaseAgent invocation successful")
            return result["messages"][-1].content
        except Exception as e:
            logger.error(f"Error during DatabaseAgent invocation: {str(e)}", exc_info=True)
            raise
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_database_agent.py::test_database_agent_invoke_with_langfuse_callback -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/agents/database_agent.py tests/unit/test_database_agent.py
git commit -m "feat: integrate Langfuse CallbackHandler into DatabaseAgent tracing"
```
