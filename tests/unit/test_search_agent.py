import pytest
from unittest.mock import patch, MagicMock
from src.agents.search_agent import SearchAgent

@pytest.mark.asyncio
async def test_search_agent_creation():
    with patch("src.agents.search_agent.TavilySearchResults") as mock_tavily, \
         patch("src.agents.search_agent.init_chat_model") as mock_init_model, \
         patch("src.agents.search_agent.create_agent") as mock_create_agent:
        
        agent = await SearchAgent.create()
        
        assert agent is not None
        mock_tavily.assert_called_once()
        mock_init_model.assert_called_once()
        mock_create_agent.assert_called_once()

@pytest.mark.asyncio
async def test_search_agent_invoke():
    mock_search_agent_executor = MagicMock()
    # Mock the async invoke response structure from create_agent
    mock_message = MagicMock()
    mock_message.content = "Here is the search result based on Tavily."
    
    from unittest.mock import AsyncMock
    mock_search_agent_executor.ainvoke = AsyncMock(return_value={"messages": [mock_message]})
    
    agent = SearchAgent(search_agent=mock_search_agent_executor)
    
    # We must patch get_client from langfuse to avoid actual network calls during flush
    with patch("src.agents.search_agent.get_client"):
        response = await agent.invoke("What are the best health insurance plans in VN?")
        
    assert response == "Here is the search result based on Tavily."
    mock_search_agent_executor.ainvoke.assert_called_once()
