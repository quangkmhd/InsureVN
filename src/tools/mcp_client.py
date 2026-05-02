import os
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_core.tools import BaseTool

async def get_sqlite_mcp_tools() -> list[BaseTool]:
    """Connect to the local SQLite MCP server and return LangChain tools."""
    # Assuming server.py is in src/mcp_servers/sqlite/
    server_script = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "mcp_servers", "sqlite", "server.py")
    )
    
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    
    client = MultiServerMCPClient(
        {
            "insurevn_sqlite": {
                "transport": "stdio",
                "command": "python",
                "args": [server_script],
                "env": {**os.environ, "PYTHONPATH": project_root}
            }
        }
    )
    
    tools = await client.get_tools()
    return tools
