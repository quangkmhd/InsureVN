from __future__ import annotations
from typing import Any, List, Optional
from langchain.agents import create_agent
from src.tools.mcp_client import get_sqlite_mcp_tools
import os
from dotenv import load_dotenv
from langchain.chat_models import init_chat_model

# Load environment variables from .env
load_dotenv()

class DatabaseAgent:
    def __init__(self, graph: Any):
        self.graph = graph
        
    @classmethod
    async def create(cls) -> DatabaseAgent:
        """Factory method to initialize the agent asynchronously."""

        tools = await get_sqlite_mcp_tools()
        model_name = os.getenv("LLM_MODEL")
        model_provider = os.getenv("LLM_PROVIDER")
        api_key = os.getenv("LLM_API_KEY")
        base_url = os.getenv("LLM_BASE_URL")
        
        # Build initialization parameters
        # init_chat_model handles provider-specific configuration via kwargs
        init_kwargs: dict[str, Any] = {
            "temperature": 0,
        }
        
        if api_key:
            init_kwargs["api_key"] = api_key
        if base_url:
            init_kwargs["base_url"] = base_url
        
        # Robust handling for Ollama with Auth (e.g., via proxy or cloud service)
        # We only inject headers if it's an Ollama-based model and an API key is provided
        # This approach is robust to both explicit model_provider and 'provider:model' syntax
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
        return cls(graph)
        
    async def invoke(self, query: str) -> str:
        """Invoke the agent with a query."""
        inputs = {"messages": [("user", query)]}
        result = await self.graph.ainvoke(inputs)
        return result["messages"][-1].content
