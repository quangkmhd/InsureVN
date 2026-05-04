import pytest
import re
from unittest.mock import AsyncMock, patch, MagicMock
from src.agents.database_agent import DatabaseAgent

def test_strip_thinking_logic():
    """Verify the logic for stripping thinking tokens."""
    content_with_thought = "<|channel>thought\\nThis is some reasoning.<channel|>The final answer is 42."
    # Standardize the content for testing (handling the escaped newline if it comes like that)
    content_with_thought = content_with_thought.replace("\\n", "\n")
    
    # Regex to match: <|channel>thought\n[Internal reasoning]<channel|>
    # Note: Using re.DOTALL to match across newlines
    stripped = re.sub(r"<\|channel>thought\n.*?<channel\|>", "", content_with_thought, flags=re.DOTALL)
    assert stripped.strip() == "The final answer is 42."

    content_with_empty_thought = "<|channel>thought\n<channel|>The final answer is 43."
    stripped_empty = re.sub(r"<\|channel>thought\n.*?<channel\|>", "", content_with_empty_thought, flags=re.DOTALL)
    assert stripped_empty.strip() == "The final answer is 43."

@pytest.mark.asyncio
@patch("src.agents.database_agent.get_sqlite_mcp_tools")
@patch("src.agents.database_agent.init_chat_model")
@patch("src.agents.database_agent.get_client")
async def test_database_agent_config_parameters(mock_langfuse_client, mock_init_chat, mock_get_tools):
    """Verify that the agent initializes with the correct sampling parameters and prepends <|think|>."""
    mock_get_tools.return_value = []
    mock_init_chat.return_value = MagicMock()
    
    # Mock Langfuse prompt
    mock_prompt = MagicMock()
    mock_prompt.compile.return_value = "System prompt from Langfuse"
    mock_prompt.version = 1
    mock_langfuse_client.return_value.get_prompt.return_value = mock_prompt
    
    # We need to mock create_agent because it's used in DatabaseAgent.create
    with patch("src.agents.database_agent.create_agent") as mock_create_agent:
        await DatabaseAgent.create()
        
        # Check init_chat_model call
        _, kwargs = mock_init_chat.call_args
        assert kwargs["temperature"] == 1.0
        assert kwargs["top_p"] == 0.95
        assert kwargs["top_k"] == 64
        
        # Check create_agent call for system_prompt
        _, agent_kwargs = mock_create_agent.call_args
        assert agent_kwargs["system_prompt"].startswith("<|think|>")
        assert "System prompt from Langfuse" in agent_kwargs["system_prompt"]

@pytest.mark.asyncio
async def test_database_agent_invoke_strips_thinking():
    """Verify that invoke strips thinking tokens from the result."""
    mock_agent_executor = AsyncMock()
    thought_content = "<|channel>thought\nI should query tables.\n<channel|>The tables are companies, documents."
    mock_agent_executor.ainvoke.return_value = {"messages": [MagicMock(content=thought_content)]}
    
    agent = DatabaseAgent(database_agent=mock_agent_executor)
    result = await agent.invoke("What tables?")
    
    assert result == "The tables are companies, documents."
    assert "thought" not in result
    assert "<|channel>" not in result
