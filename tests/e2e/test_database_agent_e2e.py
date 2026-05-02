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
        assert "companies" in response_lower or "công ty" in response_lower or "bảng" in response_lower
    except Exception as e:
        if "BILLING_DISABLED" in str(e) or "PERMISSION_DENIED" in str(e):
            pytest.skip(f"Skipping E2E test due to GCP billing/permission issue: {e}")
        else:
            raise
