import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from src.agents.database_agent import DatabaseAgent

@pytest.fixture
def mock_sqlite_mcp_tools():
    from langchain_core.tools import tool
    @tool
    def list_tables() -> list[str]:
        """Return a list of all tables"""
        return ["companies", "documents"]
    return [list_tables]

@pytest.mark.asyncio
@patch("src.agents.database_agent.get_sqlite_mcp_tools")
async def test_database_agent_init(mock_get_sqlite_tools, mock_sqlite_mcp_tools):
    mock_get_sqlite_tools.return_value = mock_sqlite_mcp_tools
    agent = await DatabaseAgent.create()
    assert agent is not None
    assert agent.database_agent is not None

@pytest.mark.asyncio
@patch("src.agents.database_agent.get_sqlite_mcp_tools")
async def test_database_agent_invoke(mock_get_sqlite_tools, mock_sqlite_mcp_tools):
    from langchain_core.messages import AIMessage
    mock_get_sqlite_tools.return_value = mock_sqlite_mcp_tools
    agent = await DatabaseAgent.create()
    
    # Mock the ainvoke method of the underlying database_agent
    agent.database_agent.ainvoke = AsyncMock(return_value={"messages": [AIMessage(content="Tables are: companies, documents")]})
    
    result = await agent.invoke("What tables are in the database?")
    assert "Tables are" in result

@pytest.mark.asyncio
async def test_database_agent_invoke_with_langfuse_callback():
    # Setup mock agent
    mock_agent_executor = AsyncMock()
    mock_agent_executor.ainvoke.return_value = {"messages": [MagicMock(content="Answer")]}
    
    agent = DatabaseAgent(database_agent=mock_agent_executor)
    
    # Test invoke without passing explicit config, should inject callbacks
    result = await agent.invoke("Hello")
    
    assert result == "Answer"
    
    # Ensure database_agent.ainvoke was called with the config containing callbacks
    mock_agent_executor.ainvoke.assert_called_once()
    call_args = mock_agent_executor.ainvoke.call_args[1]
    
    config_arg = call_args.get("config")
    assert config_arg is not None
    assert "callbacks" in config_arg
    assert isinstance(config_arg["callbacks"], list)

@pytest.mark.asyncio
async def test_database_agent_invoke_preserves_caller_config():
    mock_agent_executor = AsyncMock()
    mock_agent_executor.ainvoke.return_value = {"messages": [MagicMock(content="Answer")]}
    agent = DatabaseAgent(database_agent=mock_agent_executor)
    caller_callback = MagicMock()
    caller_config = {
        "callbacks": [caller_callback],
        "run_name": "custom-run",
        "user_id": "user-1",
        "session_id": "session-1",
        "configurable": {"thread_id": "thread-1"},
    }

    result = await agent.invoke("Hello", config=caller_config)

    assert result == "Answer"
    assert caller_config == {
        "callbacks": [caller_callback],
        "run_name": "custom-run",
        "user_id": "user-1",
        "session_id": "session-1",
        "configurable": {"thread_id": "thread-1"},
    }
    invoke_config = mock_agent_executor.ainvoke.call_args.kwargs["config"]
    assert invoke_config["callbacks"][0] is caller_callback
    assert len(invoke_config["callbacks"]) == 2
    assert invoke_config["run_name"] == "custom-run"
    assert invoke_config["configurable"] == {"thread_id": "thread-1"}
