from __future__ import annotations
import re
import os
from typing import Any, Optional

from langchain.agents import create_agent
from langchain.chat_models import init_chat_model
from langchain_community.tools.tavily_search import TavilySearchResults

from src.core.logger import get_logger
from src.core.config import settings
from langfuse import propagate_attributes, get_client
from langfuse.langchain import CallbackHandler

# Langfuse Trace metadata
logger = get_logger(__name__)

class SearchAgent:
    def __init__(self, search_agent: Any, prompt_version: Optional[int] = None):
        self.search_agent = search_agent
        self.prompt_version = prompt_version
        
    @classmethod
    async def create(cls) -> SearchAgent:
        """Factory method to initialize the search agent asynchronously."""
        logger.info("Initializing SearchAgent")
        
        # Ensure Tavily API key is set in environment for the tool
        if settings.SEARCH_TAVILY_API_KEY:
            os.environ["TAVILY_API_KEY"] = settings.SEARCH_TAVILY_API_KEY
        
        # Initialize the Tavily Search tool
        search_tool = TavilySearchResults(max_results=settings.SEARCH_MAX_RESULTS)
        search_tools = [search_tool]
        
        init_kwargs: dict[str, Any] = {
            "temperature": settings.SEARCH_LLM_TEMPERATURE,
            "top_p": settings.SEARCH_LLM_TOP_P,
            "top_k": settings.SEARCH_LLM_TOP_K,
        }
        
        if settings.SEARCH_LLM_API_KEY:
            init_kwargs["api_key"] = settings.SEARCH_LLM_API_KEY
        if settings.SEARCH_LLM_BASE_URL:
            init_kwargs["base_url"] = settings.SEARCH_LLM_BASE_URL
            
        is_ollama = (settings.SEARCH_LLM_PROVIDER == "ollama") or (settings.SEARCH_LLM_MODEL and "ollama" in settings.SEARCH_LLM_MODEL.lower())
        if is_ollama and settings.SEARCH_LLM_API_KEY:
            init_kwargs["client_kwargs"] = {"headers": {"Authorization": f"Bearer {settings.SEARCH_LLM_API_KEY}"}}
            
        search_agent_llm = init_chat_model(settings.SEARCH_LLM_MODEL, model_provider=settings.SEARCH_LLM_PROVIDER, **init_kwargs)

        # Prompt Management: fetch from Langfuse with fallback
        FALLBACK_PROMPT = (
            "You are the Web Search Agent for the InsureVN system.\n"
            "Your responsibility is to search the web for accurate and up-to-date information "
            "regarding insurance, competitors, market trends, or any other query the user has.\n\n"
            "GUIDELINES:\n"
            "1. THINK STEP-BY-STEP: Before searching, identify the key terms.\n"
            "2. CITE SOURCES: When providing an answer based on search results, mention the sources or URLs.\n"
            "3. BE CONCISE: Synthesize the information clearly. Do not just dump raw search results."
        )
        try:
            prompt = get_client().get_prompt("search-agent-system", label="production")
            system_prompt = prompt.compile()
            logger.info(f"Loaded prompt from Langfuse: search-agent-system v{prompt.version}")
        except Exception as e:
            logger.warning(f"Failed to fetch prompt from Langfuse, using fallback: {e}")
            system_prompt = FALLBACK_PROMPT

        # Trigger Thinking if needed by the model
        if not system_prompt.startswith("<|think|>"):
            system_prompt = f"<|think|>\n{system_prompt}"

        # Create the agent using the langchain-fundamentals skill approach
        search_agent = create_agent(search_agent_llm, tools=search_tools, system_prompt=system_prompt)
        logger.info("SearchAgent initialized successfully")
        
        # Get version if loaded from Langfuse
        prompt_version = None
        try:
            prompt_version = get_client().get_prompt("search-agent-system", label="production").version
        except Exception:
            pass

        return cls(search_agent, prompt_version=prompt_version)
        
    async def invoke(self, user_query: str, config: Optional[dict] = None) -> str:
        """Invoke the search agent with a query."""
        run_config = dict(config or {})
        user_id = run_config.pop("user_id", "unknown")
        session_id = run_config.pop("session_id", "unknown")
        
        metadata = {
            "query": user_query,
            "user_id": user_id,
            "session_id": session_id,
            "agent_type": "SearchAgent",
            "prompt_version": self.prompt_version
        }

        logger.info(f"Invoking SearchAgent", extra=metadata)

        agent_execution_inputs = {"messages": [("user", user_query)]}
        langfuse_handler = CallbackHandler()
        callbacks = list(run_config.pop("callbacks", []))
        callbacks.append(langfuse_handler)

        invoke_config = {
            "callbacks": callbacks,
            "run_name": run_config.pop("run_name", "search-agent-execution"),
            **run_config,
        }

        try:
            with propagate_attributes(
                trace_name="search-agent-execution",
                user_id=user_id,
                session_id=session_id,
                tags=["search_agent"],
            ):
                agent_execution_result = await self.search_agent.ainvoke(agent_execution_inputs, config=invoke_config)

            agent_response_content = agent_execution_result["messages"][-1].content
            
            # Remove thinking blocks if present
            agent_response_content = re.sub(
                r"<\|channel>thought\n.*?<channel\|>", "", agent_response_content, flags=re.DOTALL
            )
            
            logger.info("SearchAgent invocation successful", extra={**metadata, "status": "success"})
            return agent_response_content.strip()
        except Exception as e:
            logger.error(
                f"Error during SearchAgent invocation: {str(e)}", 
                extra={**metadata, "status": "error", "error_type": type(e).__name__},
                exc_info=True
            )
            raise
        finally:
            get_client().flush()
