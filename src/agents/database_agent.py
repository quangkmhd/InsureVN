from langchain.agents import create_agent
from src.tools.mcp_client import get_sqlite_mcp_tools

class DatabaseAgent:
    def __init__(self, graph):
        self.graph = graph
        
    @classmethod
    async def create(cls):
        """Factory method to initialize the agent asynchronously."""
        # 1. Get MCP Tools
        tools = await get_sqlite_mcp_tools()
        
        # 2. Initialize LLM Dynamically
        import os
        from dotenv import load_dotenv
        from langchain.chat_models import init_chat_model
        
        # Load environment variables from .env
        load_dotenv()
        
        # Read the preferred model from the environment (defaulting to ollama if not specified)
        # Examples: "ollama:gemma4:31b-cloud", "openai:gpt-4o", "google_genai:gemini-3-flash-preview"
        model_name = os.environ.get("LLM_MODEL", "ollama:gemma4:31b-cloud")
        
        # Dynamic kwargs for specific providers
        kwargs = {}
        if model_name.startswith("ollama:"):
            ollama_url = os.environ.get("OLLAMA_API_URL", "https://ollama.com")
            ollama_api_key = os.environ.get("OLLAMA_API_KEY", "")
            if ollama_api_key:
                kwargs["client_kwargs"] = {"headers": {"Authorization": f"Bearer {ollama_api_key}"}}
            kwargs["base_url"] = ollama_url
            
        llm = init_chat_model(model_name, **kwargs)
        
        # 3. System Prompt
        system_prompt = (
            "You are the DatabaseAgent for the InsureVN system. "
            "Your sole responsibility is to query the SQLite database using the provided tools "
            "and answer the user's question accurately based on the returned data. "
            "Do not guess or make up data."
        )
        
        # 4. Create ReAct Agent Graph
        graph = create_agent(llm, tools=tools, system_prompt=system_prompt)
        
        return cls(graph)
        
    async def invoke(self, query: str) -> str:
        """Invoke the agent with a query."""
        inputs = {"messages": [("user", query)]}
        result = await self.graph.ainvoke(inputs)
        return result["messages"][-1].content
