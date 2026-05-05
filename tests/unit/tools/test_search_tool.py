from unittest.mock import MagicMock, patch

from langchain_core.tools import BaseTool

from src.tools.search_tool import search_web


def test_search_web_is_tool():
    # Verify that search_web is a LangChain tool
    assert isinstance(search_web, BaseTool)
    assert search_web.name == "search_web"
    assert "query" in search_web.args


def test_search_web_function_is_langfuse_observed():
    assert hasattr(search_web.func, "__wrapped__")


def test_search_web_invoke():
    # Verify that invoking the tool calls TavilySearchResults
    with patch("src.tools.search_tool.TavilySearchResults") as mock_tavily_class:
        mock_tavily_instance = MagicMock()
        mock_tavily_instance.invoke.return_value = "Mocked search result"
        mock_tavily_class.return_value = mock_tavily_instance

        result = search_web.invoke({"query": "insurance trends 2024"})

        assert result == "Mocked search result"
        mock_tavily_class.assert_called_once()
        mock_tavily_instance.invoke.assert_called_once_with(
            {"query": "insurance trends 2024"}
        )
