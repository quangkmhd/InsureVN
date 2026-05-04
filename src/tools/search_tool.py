import os
from typing import Any

from langchain_community.tools.tavily_search import TavilySearchResults
from langchain_core.tools import tool

from core.config import settings
from core.logger import get_logger

logger = get_logger(__name__)


@tool
def search_web(query: str) -> Any:
    """Search the web for accurate information regarding insurance, competitors, 
    market trends, or any other query.

    Use this when you need live web data (market sentiment, competitor info, news).

    Args:
        query: The search query to investigate.
    """
    logger.info(f"Executing web search tool for query: {query}")

    # Ensure Tavily API key is set in environment for the tool
    if settings.SEARCH_TAVILY_API_KEY:
        os.environ["TAVILY_API_KEY"] = settings.SEARCH_TAVILY_API_KEY

    # Initialize the Tavily Search tool
    search_tool = TavilySearchResults(max_results=settings.SEARCH_MAX_RESULTS)

    try:
        # Note: In a real system you might want to use the current session's 
        # tracing context, but for simplicity we're just executing the tool 
        # directly.
        result = search_tool.invoke({"query": query})
        logger.info("Search tool executed successfully")
        return result
    except Exception as e:
        logger.error(f"Error during search tool execution: {str(e)}", exc_info=True)
        raise
