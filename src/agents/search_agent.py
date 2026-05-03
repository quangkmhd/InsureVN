from __future__ import annotations
import re
import os
from typing import Any, Optional
from dotenv import load_dotenv

from langchain.agents import create_agent
from langchain.chat_models import init_chat_model
from langchain_community.tools.tavily_search import TavilySearchResults

from src.core.logger import get_logger
from src.core.config import settings
from langfuse import propagate_attributes, get_client
from langfuse.langchain import CallbackHandler

# Load environment variables from .env
load_dotenv()
os.environ.setdefault("LANGFUSE_HOST", getattr(settings, "LANGFUSE_HOST", "https://cloud.langfuse.com"))

logger = get_logger(__name__)

class SearchAgent:
    def __init__(self, graph: Any):
        self.graph = graph
        
    @classmethod
    async def create(cls) -> SearchAgent:
        """Factory method to initialize the search agent asynchronously."""
        logger.info("Initializing SearchAgent")
        
        # Verify Tavily API key is present
        if not os.getenv("TAVILY_API_KEY"):
            logger.warning("TAVILY_API_KEY is not set. The search tool will fail.")

        # Initialize the Tavily Search tool
        # max_results can be tweaked based on needs
        search_tool = TavilySearchResults(max_results=50)
        tools = [search_tool]
        
        model_name = os.getenv("LLM_MODEL")
        model_provider = os.getenv("LLM_PROVIDER")
        api_key = os.getenv("LLM_API_KEY")
        base_url = os.getenv("LLM_BASE_URL")
        
        init_kwargs: dict[str, Any] = {
            "temperature": 0.7,  # slightly lower for factual search tasks
            "top_p": 0.95,
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
        graph = create_agent(llm, tools=tools, system_prompt=system_prompt)
        logger.info("SearchAgent initialized successfully")
        return cls(graph)
        
    async def invoke(self, query: str, config: Optional[dict] = None) -> str:
        """Invoke the search agent with a query."""
        run_config = dict(config or {})
        user_id = run_config.pop("user_id", "unknown")
        session_id = run_config.pop("session_id", "unknown")
        
        metadata = {
            "query": query,
            "user_id": user_id,
            "session_id": session_id,
            "agent_type": "SearchAgent"
        }

        logger.info(f"Invoking SearchAgent", extra=metadata)

        inputs = {"messages": [("user", query)]}
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
                result = await self.graph.ainvoke(inputs, config=invoke_config)

            content = result["messages"][-1].content
            
            # Remove thinking blocks if present
            content = re.sub(
                r"<\|channel>thought\n.*?<channel\|>", "", content, flags=re.DOTALL
            )
            
            logger.info("SearchAgent invocation successful", extra={**metadata, "status": "success"})
            return content.strip()
        except Exception as e:
            logger.error(
                f"Error during SearchAgent invocation: {str(e)}", 
                extra={**metadata, "status": "error", "error_type": type(e).__name__},
                exc_info=True
            )
            raise
        finally:
            get_client().flush()
