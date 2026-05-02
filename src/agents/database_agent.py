from langchain.agents import create_agent
from langchain_google_vertexai import ChatVertexAI
from src.tools.mcp_client import get_sqlite_mcp_tools

class DatabaseAgent:
    def __init__(self, graph):
        self.graph = graph
        
    @classmethod
    async def create(cls):
        """Factory method to initialize the agent asynchronously."""
        # 1. Get MCP Tools
        tools = await get_sqlite_mcp_tools()
        
        # 2. Initialize LLM
        import os
        from google.oauth2 import service_account
        
        credentials_path = "/home/quangnhvn34/service-account.json"
        credentials = None
        if os.path.exists(credentials_path):
            credentials = service_account.Credentials.from_service_account_file(credentials_path)
            
        llm = ChatVertexAI(
            model="gemini-3-flash-preview",
            credentials=credentials
        )
        
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
