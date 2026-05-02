import pytest
from mcp.server.fastmcp import FastMCP

def test_server_initialization():
    from src.mcp_servers.sqlite.server import mcp
    assert isinstance(mcp, FastMCP)
    assert mcp.name == "insurevn-db"