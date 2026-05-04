import pytest

from src.tools.mcp_client import get_sqlite_mcp_tools


@pytest.mark.asyncio
async def test_get_sqlite_mcp_tools():
    tools = await get_sqlite_mcp_tools()
    assert len(tools) > 0
    tool_names = [t.name for t in tools]
    assert "list_tables" in tool_names
    assert "execute_query" in tool_names
