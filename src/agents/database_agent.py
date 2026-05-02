from __future__ import annotations
from typing import Any, List, Optional
from langchain.agents import create_agent
from src.tools.mcp_client import get_sqlite_mcp_tools
import os
from dotenv import load_dotenv
from langchain.chat_models import init_chat_model
from src.core.logger import get_logger
from langfuse.langchain import CallbackHandler

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
        
        # Initialize Langfuse CallbackHandler for tracing
        langfuse_handler = CallbackHandler()
        
        run_config = config or {}
        
        # Best practice: use a descriptive run name
        if "run_name" not in run_config:
            run_config["run_name"] = "database_agent_execution"
        
        # Best practice: use metadata for dynamic tracing attributes
        if "metadata" not in run_config:
            run_config["metadata"] = {}
            
        # Best practice: add tags to traces
        if "langfuse_tags" not in run_config["metadata"]:
            run_config["metadata"]["langfuse_tags"] = ["database_agent"]
            
        # Map user_id or session_id to langfuse keys if passed in run_config
        if "user_id" in run_config:
            run_config["metadata"]["langfuse_user_id"] = run_config.pop("user_id")
        if "session_id" in run_config:
            run_config["metadata"]["langfuse_session_id"] = run_config.pop("session_id")
            
        if "callbacks" not in run_config:
            run_config["callbacks"] = []
            
        run_config["callbacks"].append(langfuse_handler)
        
        try:
            result = await self.graph.ainvoke(inputs, config=run_config)
            logger.info("DatabaseAgent invocation successful")
            return result["messages"][-1].content
        except Exception as e:
            logger.error(f"Error during DatabaseAgent invocation: {str(e)}", exc_info=True)
            raise
        finally:
            # Best practice: flush traces to avoid losing data in scripts/serverless
            if hasattr(langfuse_handler, 'flush'):
                langfuse_handler.flush()
            elif hasattr(langfuse_handler, 'langfuse'):
                langfuse_handler.langfuse.flush()
            elif hasattr(langfuse_handler, 'auth_check'):
                langfuse_handler.auth_check() # fallback if flush not explicitly needed here
            elif hasattr(langfuse_handler, 'client'):
                langfuse_handler.client.flush()
