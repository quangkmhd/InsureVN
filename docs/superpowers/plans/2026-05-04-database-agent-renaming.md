# Renaming `graph` to `database_agent` Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rename the internal `graph` variable and attribute to `database_agent` in the `DatabaseAgent` class and update all related tests to ensure clarity and consistency.

**Architecture:** This is a pure refactoring task. We are renaming identifiers in `src/agents/database_agent.py` and its corresponding unit tests in `tests/unit/`.

**Tech Stack:** Python 3.12.3, LangChain, Pytest.

---

### Task 1: Refactor `src/agents/database_agent.py`

**Files:**
- Modify: `src/agents/database_agent.py`

- [ ] **Step 1: Rename `graph` to `database_agent` in `__init__`**
```python
    def __init__(self, database_agent: Any, prompt_version: Optional[int] = None):
        self.database_agent = database_agent
        self.prompt_version = prompt_version
```

- [ ] **Step 2: Rename `graph` to `database_agent` in `create` class method**
```python
        database_agent = create_agent(llm, tools=tools, system_prompt=system_prompt)
        logger.info("DatabaseAgent initialized successfully")
        
        # ... (prompt version logic)

        return cls(database_agent, prompt_version=prompt_version)
```

- [ ] **Step 3: Update `invoke` method to use `self.database_agent`**
```python
            with propagate_attributes(
                trace_name="database-agent-execution",
                user_id=user_id,
                session_id=session_id,
                tags=["database_agent"],
            ):
                result = await self.database_agent.ainvoke(inputs, config=invoke_config)
```

- [ ] **Step 4: Commit changes**
```bash
git add src/agents/database_agent.py
git commit -m "refactor: rename graph to database_agent in DatabaseAgent class"
```

---

### Task 2: Update `tests/unit/test_database_agent.py`

**Files:**
- Modify: `tests/unit/test_database_agent.py`

- [ ] **Step 1: Update `test_database_agent_init`**
```python
@pytest.mark.asyncio
@patch("src.agents.database_agent.get_sqlite_mcp_tools")
async def test_database_agent_init(mock_get_tools, mock_tools):
    mock_get_tools.return_value = mock_tools
    agent = await DatabaseAgent.create()
    assert agent is not None
    assert agent.database_agent is not None
```

- [ ] **Step 2: Update `test_database_agent_invoke`**
```python
@pytest.mark.asyncio
@patch("src.agents.database_agent.get_sqlite_mcp_tools")
async def test_database_agent_invoke(mock_get_tools, mock_tools):
    from langchain_core.messages import AIMessage
    mock_get_tools.return_value = mock_tools
    agent = await DatabaseAgent.create()
    
    # Mock the ainvoke method of the underlying agent
    agent.database_agent.ainvoke = AsyncMock(return_value={"messages": [AIMessage(content="Tables are: companies, documents")]})
    
    result = await agent.invoke("What tables are in the database?")
    assert "Tables are" in result
```

- [ ] **Step 3: Update `test_database_agent_invoke_with_langfuse_callback`**
```python
@pytest.mark.asyncio
async def test_database_agent_invoke_with_langfuse_callback():
    # Setup mock agent
    mock_agent = AsyncMock()
    mock_agent.ainvoke.return_value = {"messages": [MagicMock(content="Answer")]}
    
    agent = DatabaseAgent(database_agent=mock_agent)
    
    # Test invoke without passing explicit config, should inject callbacks
    result = await agent.invoke("Hello")
    
    assert result == "Answer"
    
    # Ensure database_agent.ainvoke was called with the config containing callbacks
    mock_agent.ainvoke.assert_called_once()
    # ...
```

- [ ] **Step 4: Update `test_database_agent_invoke_preserves_caller_config`**
```python
@pytest.mark.asyncio
async def test_database_agent_invoke_preserves_caller_config():
    mock_agent = AsyncMock()
    mock_agent.ainvoke.return_value = {"messages": [MagicMock(content="Answer")]}
    agent = DatabaseAgent(database_agent=mock_agent)
    # ...
    result = await agent.invoke("Hello", config=caller_config)
    # ...
    invoke_config = mock_agent.ainvoke.call_args.kwargs["config"]
    # ...
```

- [ ] **Step 5: Run tests and commit**
```bash
pytest tests/unit/test_database_agent.py -v
git add tests/unit/test_database_agent.py
git commit -m "test: update DatabaseAgent unit tests to use database_agent attribute"
```

---

### Task 3: Update `tests/unit/test_database_agent_config.py`

**Files:**
- Modify: `tests/unit/test_database_agent_config.py`

- [ ] **Step 1: Update `test_database_agent_invoke_strips_thinking`**
```python
@pytest.mark.asyncio
async def test_database_agent_invoke_strips_thinking():
    """Verify that invoke strips thinking tokens from the result."""
    mock_agent = AsyncMock()
    thought_content = "<|channel>thought\nI should query tables.\n<channel|>The tables are companies, documents."
    mock_agent.ainvoke.return_value = {"messages": [MagicMock(content=thought_content)]}
    
    agent = DatabaseAgent(database_agent=mock_agent)
    result = await agent.invoke("What tables?")
    
    assert result == "The tables are companies, documents."
    assert "thought" not in result
    assert "<|channel>" not in result
```

- [ ] **Step 2: Run all tests and commit**
```bash
pytest tests/unit/test_database_agent.py tests/unit/test_database_agent_config.py -v
git add tests/unit/test_database_agent_config.py
git commit -m "test: update DatabaseAgent config tests to use database_agent attribute"
```
