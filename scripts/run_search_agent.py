import asyncio
import os
import sys

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.agents.search_agent import SearchAgent

async def main():
    print("Initializing SearchAgent...")
    agent = await SearchAgent.create()
    
    print("\nInvoking Agent...")
    response = await agent.invoke(
        query="What are the best health insurance plans in VN?",
        config={
            "user_id": "dev_test_user",
            "session_id": "dev_test_session_001"
        }
    )
    
    print("\n=== Agent Response ===")
    print(response)
    print("======================")
    print("\nCheck your Langfuse dashboard at http://localhost:3000 !")

if __name__ == "__main__":
    asyncio.run(main())
