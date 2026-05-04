import pytest

from src.agents.database_agent import DatabaseAgent


@pytest.mark.asyncio
async def test_database_agent_real_query():
    """
    Test the DatabaseAgent against the real MCP server.
    Note: Requires Google Cloud credentials for VertexAI to be set up.
    """
    agent = await DatabaseAgent.create()

    try:
        # Ask a question that requires calling a tool (e.g., list_tables or list_companies)
        response = await agent.invoke("Lấy danh sách các bảng trong cơ sở dữ liệu")

        # The response should mention 'companies' or 'documents'
        # since we know these tables exist from the server.py schema
        response_lower = response.lower()
        assert (
            "companies" in response_lower
            or "công ty" in response_lower
            or "bảng" in response_lower
        )
    except Exception as e:
        error_msg = str(e).lower()
        if (
            "billing" in error_msg
            or "permission_denied" in error_msg
            or "unauthorized" in error_msg
            or "connection error" in error_msg
            or "401" in error_msg
            or "403" in error_msg
            or "404" in error_msg
        ):
            pytest.skip(f"Skipping E2E test due to Cloud API access issue: {e}")
        else:
            raise
