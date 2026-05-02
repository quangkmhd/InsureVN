# Database Agent & MCP Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Integrate the existing SQLite MCP server into the LangGraph multi-agent architecture as a dedicated DatabaseAgent to avoid tool bloat and ensure single responsibility.

**Architecture:** We will create an MCP client wrapper (`mcp_client.py`) using `langchain-mcp-adapters` to connect via stdio to the existing `server.py`. Then, we will create a `database_agent.py` that acts as a LangGraph ReAct agent, exclusively possessing these SQL tools to answer database-related queries.

**Tech Stack:** Python 3.12, LangChain, LangGraph, langchain-mcp-adapters, langchain-google-vertexai.

---

### Task 1: Setup MCP Client Wrapper

**Files:**
- Create: `src/tools/mcp_client.py`
- Test: `tests/integration/test_mcp_client.py`

- [ ] **Step 1: Write the failing test**

```python
import pytest
from src.tools.mcp_client import get_sqlite_mcp_tools

@pytest.mark.asyncio
async def test_get_sqlite_mcp_tools():
    tools = await get_sqlite_mcp_tools()
    assert len(tools) > 0
    tool_names = [t.name for t in tools]
    assert "list_tables" in tool_names
    assert "execute_query" in tool_names
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/integration/test_mcp_client.py -v`
Expected: FAIL with ModuleNotFoundError for `src.tools.mcp_client`

- [ ] **Step 3: Write minimal implementation**

```python
import os
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_core.tools import BaseTool

async def get_sqlite_mcp_tools() -> list[BaseTool]:
    """Connect to the local SQLite MCP server and return LangChain tools."""
    # Assuming server.py is in src/mcp_servers/sqlite/
    server_script = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "mcp_servers", "sqlite", "server.py")
    )
    
    client = MultiServerMCPClient(
        {
            "insurevn_sqlite": {
                "transport": "stdio",
                "command": "python",
                "args": [server_script]
            }
        }
    )
    
    tools = await client.get_tools()
    return tools
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/integration/test_mcp_client.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/integration/test_mcp_client.py src/tools/mcp_client.py
git commit -m "feat: add mcp client wrapper for sqlite tools"
```

### Task 2: Create Database Agent Component

**Files:**
- Create: `src/agents/database_agent.py`
- Test: `tests/unit/test_database_agent.py`

- [ ] **Step 1: Write the failing test**

```python
import pytest
from unittest.mock import AsyncMock, patch
from src.agents.database_agent import DatabaseAgent

@pytest.fixture
def mock_tools():
    from langchain_core.tools import tool
    @tool
    def list_tables() -> list[str]:
        """Return a list of all tables"""
        return ["companies", "documents"]
    return [list_tables]

@pytest.mark.asyncio
@patch("src.agents.database_agent.get_sqlite_mcp_tools")
async def test_database_agent_init(mock_get_tools, mock_tools):
    mock_get_tools.return_value = mock_tools
    agent = await DatabaseAgent.create()
    assert agent is not None
    assert agent.graph is not None

@pytest.mark.asyncio
@patch("src.agents.database_agent.get_sqlite_mcp_tools")
async def test_database_agent_invoke(mock_get_tools, mock_tools):
    mock_get_tools.return_value = mock_tools
    agent = await DatabaseAgent.create()
    
    # Mock the ainvoke method of the underlying graph
    agent.graph.ainvoke = AsyncMock(return_value={"messages": [{"role": "assistant", "content": "Tables are: companies, documents"}]})
    
    result = await agent.invoke("What tables are in the database?")
    assert "Tables are" in result
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_database_agent.py -v`
Expected: FAIL with ModuleNotFoundError for `src.agents.database_agent`

- [ ] **Step 3: Write minimal implementation**

```python
from langgraph.prebuilt import create_react_agent
from langchain_google_vertexai import ChatVertexAI
from src.tools.mcp_client import get_sqlite_mcp_tools

class DatabaseAgent:
    def __init__(self, graph):
        self.graph = graph
        
    @classmethod
    async def create(cls):
        """Factory method to initialize the agent asynchronously."""
        # 1. Get MCP Tools
        tools = await get_sqlite_mcp_tools()
        
        # 2. Initialize LLM (Gemini 1.5 Pro)
        llm = ChatVertexAI(model="gemini-1.5-pro")
        
        # 3. System Prompt
        system_prompt = (
            "You are the DatabaseAgent for the InsureVN system. "
            "Your sole responsibility is to query the SQLite database using the provided tools "
            "and answer the user's question accurately based on the returned data. "
            "Do not guess or make up data."
        )
        
        # 4. Create ReAct Agent Graph
        graph = create_react_agent(llm, tools=tools, state_modifier=system_prompt)
        
        return cls(graph)
        
    async def invoke(self, query: str) -> str:
        """Invoke the agent with a query."""
        inputs = {"messages": [("user", query)]}
        result = await self.graph.ainvoke(inputs)
        return result["messages"][-1].content
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_database_agent.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/unit/test_database_agent.py src/agents/database_agent.py
git commit -m "feat: create database agent using langgraph react pattern"
```

### Task 3: Create E2E Integration Test for Database Agent

**Files:**
- Create: `tests/e2e/test_database_agent_e2e.py`

- [ ] **Step 1: Write the E2E test**

```python
import pytest
from src.agents.database_agent import DatabaseAgent

@pytest.mark.asyncio
async def test_database_agent_real_query():
    """
    Test the DatabaseAgent against the real MCP server.
    Note: Requires Google Cloud credentials for VertexAI to be set up.
    """
    agent = await DatabaseAgent.create()
    
    # Ask a question that requires calling a tool (e.g., list_tables or list_companies)
    response = await agent.invoke("Lấy danh sách các bảng trong cơ sở dữ liệu")
    
    # The response should mention 'companies' or 'documents' 
    # since we know these tables exist from the server.py schema
    response_lower = response.lower()
    assert "companies" in response_lower or "công ty" in response_lower or "bảng" in response_lower
```

- [ ] **Step 2: Run test to verify it works (or skips gracefully)**

Run: `pytest tests/e2e/test_database_agent_e2e.py -v`
Note: This test might require Vertex AI credentials. If it fails due to auth, you can mock the LLM or skip it in CI, but it should pass if local auth is configured.

- [ ] **Step 3: Commit**

```bash
git add tests/e2e/test_database_agent_e2e.py
git commit -m "test: add e2e test for database agent"
```