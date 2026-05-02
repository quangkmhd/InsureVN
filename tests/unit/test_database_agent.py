import pytest
from unittest.mock import AsyncMock, patch, MagicMock
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
    from langchain_core.messages import AIMessage
    mock_get_tools.return_value = mock_tools
    agent = await DatabaseAgent.create()
    
    # Mock the ainvoke method of the underlying graph
    agent.graph.ainvoke = AsyncMock(return_value={"messages": [AIMessage(content="Tables are: companies, documents")]})
    
    result = await agent.invoke("What tables are in the database?")
    assert "Tables are" in result

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
