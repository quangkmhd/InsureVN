import asyncio
from src.agents.database_agent import DatabaseAgent

async def main():
    agent = await DatabaseAgent.create()
    print(type(agent.graph))
    
asyncio.run(main())
