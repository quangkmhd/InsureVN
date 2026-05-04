from __future__ import annotations
import re
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
model_name = os.getenv("LLM_MODEL")
model_provider = os.getenv("LLM_PROVIDER")
api_key = os.getenv("LLM_API_KEY")
base_url = os.getenv("LLM_BASE_URL")
logger = get_logger(__name__)

class DatabaseAgent:
    def __init__(self, database_agent: Any, prompt_version: Optional[int] = None):
        self.database_agent = database_agent
        self.prompt_version = prompt_version
        
    @classmethod
    async def create(cls) -> DatabaseAgent:
        """Factory method to initialize the agent asynchronously."""
        logger.info("Initializing DatabaseAgent")
        
        tools = await get_sqlite_mcp_tools()
        
        init_kwargs: dict[str, Any] = {
            "temperature": 1.0,
            "top_p": 0.95,
            "top_k": 64,
        }
        
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
            "You are the DatabaseAgent for the InsureVN system.\n"
            "Your sole responsibility is to query the SQLite database using the provided tools "
            "to answer the user's question accurately.\n\n"
            "GUIDELINES:\n"
            "1. THINK STEP-BY-STEP: Before calling any tool or providing a final answer, "
            "always explain your reasoning. What data do you need? Which tool is best? "
            "How will you use the results?\n"
            "2. DATA DRIVEN: Only answer based on the data returned by the tools. "
            "If no data is found, state that clearly. Do not make up facts.\n"
            "3. ACCURACY: If the user's question is ambiguous, query for broad information first "
            "before narrowing down."
        )
        try:
            prompt = get_client().get_prompt("database-agent-system", label="production")
            system_prompt = prompt.compile()
            logger.info(f"Loaded prompt from Langfuse: database-agent-system v{prompt.version}")
        except Exception as e:
            logger.warning(f"Failed to fetch prompt from Langfuse, using fallback: {e}")
            system_prompt = FALLBACK_PROMPT

        # Trigger Thinking: Include <|think|> token at the start of the system prompt
        if not system_prompt.startswith("<|think|>"):
            system_prompt = f"<|think|>\n{system_prompt}"

        database_agent = create_agent(llm, tools=tools, system_prompt=system_prompt)
        logger.info("DatabaseAgent initialized successfully")
        
        # Get version if loaded from Langfuse
        prompt_version = None
        try:
            prompt_version = get_client().get_prompt("database-agent-system", label="production").version
        except Exception:
            pass

        return cls(database_agent, prompt_version=prompt_version)
        
    async def invoke(self, query: str, config: Optional[dict] = None) -> str:
        """Invoke the agent with a query."""
        run_config = dict(config or {})
        user_id = run_config.pop("user_id", "unknown")
        session_id = run_config.pop("session_id", "unknown")
        
        metadata = {
            "query": query,
            "user_id": user_id,
            "session_id": session_id,
            "agent_type": "DatabaseAgent",
            "prompt_version": self.prompt_version
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
                result = await self.database_agent.ainvoke(inputs, config=invoke_config)

            content = result["messages"][-1].content
            # No Thinking Content in History: Strip thought blocks from the response
            # Pattern: <|channel>thought\n[Internal reasoning]<channel|>
            content = re.sub(
                r"<\|channel>thought\n.*?<channel\|>", "", content, flags=re.DOTALL
            )
            
            logger.info("DatabaseAgent invocation successful", extra={**metadata, "status": "success"})
            return content.strip()
        except Exception as e:
            logger.error(
                f"Error during DatabaseAgent invocation: {str(e)}", 
                extra={**metadata, "status": "error", "error_type": type(e).__name__},
                exc_info=True
            )
            raise
        finally:
            get_client().flush()
