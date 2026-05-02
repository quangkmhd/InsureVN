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
    from langchain_core.messages import AIMessage
    mock_get_tools.return_value = mock_tools
    agent = await DatabaseAgent.create()
    
    # Mock the ainvoke method of the underlying graph
    agent.graph.ainvoke = AsyncMock(return_value={"messages": [AIMessage(content="Tables are: companies, documents")]})
    
    result = await agent.invoke("What tables are in the database?")
    assert "Tables are" in result
