# LangSmith and Logging Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement LangSmith tracing for the database agent and a standard Python logger for system-level errors.

**Architecture:** We will create a central logger configuration in `src/core/logger.py` using standard `logging`. We will update `src/core/config.py` to hold LangSmith environment settings. Finally, we will update `src/agents/database_agent.py` to utilize both the local logger for system events and LangChain's config block for explicit tracing tags.

**Tech Stack:** Python `logging` module, LangChain (LangGraph) tracing, Python `dotenv`.

---

### Task 1: Create Centralized Logger

**Files:**
- Create: `src/core/logger.py`
- Test: `tests/unit/test_logger.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_logger.py
import logging
from src.core.logger import get_logger

def test_logger_creation():
    logger = get_logger("test_module")
    assert isinstance(logger, logging.Logger)
    assert logger.name == "test_module"
    assert logger.level == logging.INFO
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_logger.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'src.core.logger'"

- [ ] **Step 3: Write minimal implementation**

```python
# src/core/logger.py
import logging
import sys

def get_logger(name: str) -> logging.Logger:
    """Returns a configured logger instance."""
    logger = logging.getLogger(name)
    
    if not logger.handlers:
        logger.setLevel(logging.INFO)
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
        
    return logger
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_logger.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/unit/test_logger.py src/core/logger.py
git commit -m "feat: add centralized system logger"
```

### Task 2: Integrate Logger into Database Agent and Update Run Tags

**Files:**
- Modify: `src/agents/database_agent.py`
- Modify: `tests/unit/test_database_agent.py`

- [ ] **Step 1: Write the failing test for DatabaseAgent invoke tags**

Note: This step requires updating `test_database_agent.py` to verify that `ainvoke` passes `config` parameters appropriately, or at least handles them. Since testing LangGraph internals is complex, we will focus on ensuring the new signature `invoke(self, query: str, config: Optional[dict] = None)` is accepted.

```python
# In tests/unit/test_database_agent.py, add/modify a test:
import pytest
from unittest.mock import AsyncMock, MagicMock
from src.agents.database_agent import DatabaseAgent

@pytest.mark.asyncio
async def test_database_agent_invoke_with_config():
    # Setup mock graph
    mock_graph = AsyncMock()
    mock_graph.ainvoke.return_value = {"messages": [MagicMock(content="Answer")]}
    
    agent = DatabaseAgent(graph=mock_graph)
    
    # Test invoke with config
    config = {"tags": ["test_tag"], "run_name": "test_run"}
    result = await agent.invoke("Hello", config=config)
    
    assert result == "Answer"
    # Ensure graph.ainvoke was called with the config
    mock_graph.ainvoke.assert_called_once()
    call_args = mock_graph.ainvoke.call_args[1]
    assert call_args.get("config") == config
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_database_agent.py::test_database_agent_invoke_with_config -v`
Expected: FAIL because `invoke` does not accept `config` argument.

- [ ] **Step 3: Write minimal implementation**

```python
# src/agents/database_agent.py (Modify imports and class methods)
from __future__ import annotations
from typing import Any, List, Optional
from langchain.agents import create_agent
from src.tools.mcp_client import get_sqlite_mcp_tools
import os
from dotenv import load_dotenv
from langchain.chat_models import init_chat_model
from src.core.logger import get_logger

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
        
        # Define default tracing config if none provided
        run_config = config or {"tags": ["database_agent"], "run_name": "Database_MCP_Execution"}
        
        try:
            result = await self.graph.ainvoke(inputs, config=run_config)
            logger.info("DatabaseAgent invocation successful")
            return result["messages"][-1].content
        except Exception as e:
            logger.error(f"Error during DatabaseAgent invocation: {str(e)}", exc_info=True)
            raise
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_database_agent.py::test_database_agent_invoke_with_config -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/agents/database_agent.py tests/unit/test_database_agent.py
git commit -m "feat: integrate system logger and LangSmith tracing tags into DatabaseAgent"
```

### Task 3: Update Environment Configuration

**Files:**
- Modify: `src/core/config.py`
- Modify: `tests/unit/test_config.py` (if it exists, else create)

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_config.py
import os
from src.core.config import settings

def test_langsmith_settings_loaded(monkeypatch):
    # Mock environment variables
    monkeypatch.setenv("LANGCHAIN_TRACING_V2", "true")
    monkeypatch.setenv("LANGCHAIN_PROJECT", "TestProject")
    
    # Re-evaluate the properties or ensure they are present
    assert hasattr(settings, "LANGCHAIN_TRACING_V2")
    assert hasattr(settings, "LANGCHAIN_PROJECT")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_config.py -v`
Expected: FAIL due to missing attributes.

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
    
    # LangSmith Tracing
    LANGCHAIN_TRACING_V2: str = os.getenv("LANGCHAIN_TRACING_V2", "false")
    LANGCHAIN_PROJECT: str = os.getenv("LANGCHAIN_PROJECT", "InsureVN")
    LANGCHAIN_ENDPOINT: str = os.getenv("LANGCHAIN_ENDPOINT", "https://api.smith.langchain.com")
    
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
git commit -m "feat: add LangSmith config variables to settings"
```
