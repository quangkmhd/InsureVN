from __future__ import annotations
import re
from typing import Any, Optional
from langchain.agents import create_agent
from src.tools.mcp_client import get_sqlite_mcp_tools
from langchain.chat_models import init_chat_model
from src.core.logger import get_logger
from src.core.config import settings
from langfuse import propagate_attributes, get_client
from langfuse.langchain import CallbackHandler

# Langfuse Trace metadata
logger = get_logger(__name__)

class DatabaseAgent:
    def __init__(self, database_agent: Any, prompt_version: Optional[int] = None):
        self.database_agent = database_agent
        self.prompt_version = prompt_version
        
    @classmethod
    async def create(cls) -> DatabaseAgent:
        """Factory method to initialize the agent asynchronously."""
        logger.info("Initializing DatabaseAgent")
        
        sqlite_mcp_tools = await get_sqlite_mcp_tools()
        
        init_kwargs: dict[str, Any] = {
            "temperature": settings.DATABASE_LLM_TEMPERATURE,
            "top_p": settings.DATABASE_LLM_TOP_P,
            "top_k": settings.DATABASE_LLM_TOP_K,
        }
        
        if settings.DATABASE_LLM_API_KEY:
            init_kwargs["api_key"] = settings.DATABASE_LLM_API_KEY
        if settings.DATABASE_LLM_BASE_URL:
            init_kwargs["base_url"] = settings.DATABASE_LLM_BASE_URL
            
        is_ollama = (settings.DATABASE_LLM_PROVIDER == "ollama") or (settings.DATABASE_LLM_MODEL and "ollama" in settings.DATABASE_LLM_MODEL.lower())
        if is_ollama and settings.DATABASE_LLM_API_KEY:
            init_kwargs["client_kwargs"] = {"headers": {"Authorization": f"Bearer {settings.DATABASE_LLM_API_KEY}"}}
            
        database_agent_llm = init_chat_model(settings.DATABASE_LLM_MODEL, model_provider=settings.DATABASE_LLM_PROVIDER, **init_kwargs)


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

        database_agent = create_agent(database_agent_llm, tools=sqlite_mcp_tools, system_prompt=system_prompt)
        logger.info("DatabaseAgent initialized successfully")
        
        # Get version if loaded from Langfuse
        prompt_version = None
        try:
            prompt_version = get_client().get_prompt("database-agent-system", label="production").version
        except Exception:
            pass

        return cls(database_agent, prompt_version=prompt_version)
        
    async def invoke(self, user_query: str, config: Optional[dict] = None) -> str:
        """Invoke the agent with a query."""
        run_config = dict(config or {})
        user_id = run_config.pop("user_id", "unknown")
        session_id = run_config.pop("session_id", "unknown")
        
        metadata = {
            "query": user_query,
            "user_id": user_id,
            "session_id": session_id,
            "agent_type": "DatabaseAgent",
            "prompt_version": self.prompt_version
        }

        logger.info(f"Invoking DatabaseAgent", extra=metadata)

        agent_execution_inputs = {"messages": [("user", user_query)]}
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
                agent_execution_result = await self.database_agent.ainvoke(agent_execution_inputs, config=invoke_config)

            agent_response_content = agent_execution_result["messages"][-1].content
            # No Thinking Content in History: Strip thought blocks from the response
            # Pattern: <|channel>thought\n[Internal reasoning]<channel|>
            agent_response_content = re.sub(
                r"<\|channel>thought\n.*?<channel\|>", "", agent_response_content, flags=re.DOTALL
            )
            
            logger.info("DatabaseAgent invocation successful", extra={**metadata, "status": "success"})
            return agent_response_content.strip()
        except Exception as e:
            logger.error(
                f"Error during DatabaseAgent invocation: {str(e)}", 
                extra={**metadata, "status": "error", "error_type": type(e).__name__},
                exc_info=True
            )
            raise
        finally:
            get_client().flush()
