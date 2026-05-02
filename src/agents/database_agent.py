from __future__ import annotations
from typing import Any, List, Optional
from langchain.agents import create_agent
from src.tools.mcp_client import get_sqlite_mcp_tools
import os
from dotenv import load_dotenv
from langchain.chat_models import init_chat_model
from src.core.logger import get_logger

# Load environment variables from .env
load_dotenv()

logger = get_logger(__name__)

class DatabaseAgent:
    def __init__(self, graph: Any):
        self.graph = graph
        
    @classmethod
    async def create(cls) -> DatabaseAgent:
        """Factory method to initialize the agent asynchronously."""
        logger.info("Initializing DatabaseAgent")
        
        tools = await get_sqlite_mcp_tools()
        model_name = os.getenv("LLM_MODEL")
        model_provider = os.getenv("LLM_PROVIDER")
        api_key = os.getenv("LLM_API_KEY")
        base_url = os.getenv("LLM_BASE_URL")
        
        init_kwargs: dict[str, Any] = {"temperature": 0}
        
        if api_key:
            init_kwargs["api_key"] = api_key
        if base_url:
            init_kwargs["base_url"] = base_url
            
        is_ollama = (model_provider == "ollama") or (model_name and "ollama" in model_name.lower())
        if is_ollama and api_key:
            init_kwargs["client_kwargs"] = {"headers": {"Authorization": f"Bearer {api_key}"}}
            
        llm = init_chat_model(model_name, model_provider=model_provider, **init_kwargs)

        system_prompt = (
            "You are the DatabaseAgent for the InsureVN system. "
            "Your sole responsibility is to query the SQLite database using the provided tools "
            "and answer the user's question accurately based on the returned data. "
            "Do not guess or make up data."
        )
        graph = create_agent(llm, tools=tools, system_prompt=system_prompt)
        logger.info("DatabaseAgent initialized successfully")
        return cls(graph)
        
    async def invoke(self, query: str, config: Optional[dict] = None) -> str:
        """Invoke the agent with a query."""
        logger.info(f"Invoking DatabaseAgent with query: {query}")
        
        inputs = {"messages": [("user", query)]}
        
        # Define default tracing config if none provided
        run_config = config or {"tags": ["database_agent"], "run_name": "Database_MCP_Execution"}
        
        try:
            result = await self.graph.ainvoke(inputs, config=run_config)
            logger.info("DatabaseAgent invocation successful")
            return result["messages"][-1].content
        except Exception as e:
            logger.error(f"Error during DatabaseAgent invocation: {str(e)}", exc_info=True)
            raise
