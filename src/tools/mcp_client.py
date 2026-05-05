import os
from pathlib import Path

from langchain_core.tools import BaseTool
from langchain_mcp_adapters.client import MultiServerMCPClient
from langfuse import observe

from core.config import settings


@observe(name="get-sqlite-mcp-tools")
async def get_sqlite_mcp_tools() -> list[BaseTool]:
    """Connect to the local SQLite MCP server and return LangChain tools."""
    server_script_path = (
        Path(__file__).resolve().parents[1] / "mcp_servers" / "sqlite" / "server.py"
    )

    project_root = Path(__file__).resolve().parents[2]

    sqlite_mcp_environment = {
        **os.environ,
        "PYTHONPATH": str(project_root),
        "LANGFUSE_BASE_URL": settings.LANGFUSE_BASE_URL,
        "LANGFUSE_HOST": settings.LANGFUSE_BASE_URL,
    }

    sqlite_mcp_client = MultiServerMCPClient(
        {
            "insurevn_sqlite": {
                "transport": "stdio",
                "command": "python",
                "args": [str(server_script_path)],
                "env": sqlite_mcp_environment,
            }
        }
    )

    return await sqlite_mcp_client.get_tools()
