from __future__ import annotations
from typing import Any, Optional
from langchain.agents import create_agent
from src.tools.mcp_client import get_sqlite_mcp_tools
import os
from dotenv import load_dotenv
from langchain.chat_models import init_chat_model
from src.core.logger import get_logger
from src.core.config import settings
from langfuse import propagate_attributes, get_client
from langfuse.langchain import CallbackHandler

# Load environment variables from .env
load_dotenv()
os.environ.setdefault("LANGFUSE_HOST", settings.LANGFUSE_HOST)

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

        # Prompt Management: fetch from Langfuse with fallback
        FALLBACK_PROMPT = (
            "You are the DatabaseAgent for the InsureVN system. "
            "Your sole responsibility is to query the SQLite database using the provided tools "
            "and answer the user's question accurately based on the returned data. "
            "Do not guess or make up data."
        )
        try:
            prompt = get_client().get_prompt("database-agent-system", label="production")
            system_prompt = prompt.compile()
            logger.info(f"Loaded prompt from Langfuse: database-agent-system v{prompt.version}")
        except Exception as e:
            logger.warning(f"Failed to fetch prompt from Langfuse, using fallback: {e}")
            system_prompt = FALLBACK_PROMPT

        graph = create_agent(llm, tools=tools, system_prompt=system_prompt)
        logger.info("DatabaseAgent initialized successfully")
        return cls(graph)
        
    async def invoke(self, query: str, config: Optional[dict] = None) -> str:
        """Invoke the agent with a query."""
        run_config = dict(config or {})
        user_id = run_config.pop("user_id", "unknown")
        session_id = run_config.pop("session_id", "unknown")
        
        metadata = {
            "query": query,
            "user_id": user_id,
            "session_id": session_id,
            "agent_type": "DatabaseAgent"
        }

        logger.info(f"Invoking DatabaseAgent", extra=metadata)

        inputs = {"messages": [("user", query)]}
        langfuse_handler = CallbackHandler()
        callbacks = list(run_config.pop("callbacks", []))
        callbacks.append(langfuse_handler)

        invoke_config = {
            "callbacks": callbacks,
            "run_name": run_config.pop("run_name", "database-agent-execution"),
            **run_config,
        }

        try:
            with propagate_attributes(
                trace_name="database-agent-execution",
                user_id=user_id,
                session_id=session_id,
                tags=["database_agent"],
            ):
                result = await self.graph.ainvoke(inputs, config=invoke_config)

            logger.info("DatabaseAgent invocation successful", extra={**metadata, "status": "success"})
            return result["messages"][-1].content
        except Exception as e:
            logger.error(
                f"Error during DatabaseAgent invocation: {str(e)}", 
                extra={**metadata, "status": "error", "error_type": type(e).__name__},
                exc_info=True
            )
            raise
        finally:
            get_client().flush()
