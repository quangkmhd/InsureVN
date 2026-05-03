import asyncio
import sys
import os

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from src.agents.search_agent import SearchAgent

async def main():
    print("Initializing SearchAgent...")
    agent = await SearchAgent.create()
    print("Agent initialized successfully.")
    
    query = "Xu hướng thị trường bảo hiểm sức khỏe tại Việt Nam năm 2024"
    print(f"User Query: {query}")
    
    print("Invoking agent...")
    try:
        response = await agent.invoke(query)
        print("\n--- AI Response ---")
        print(response)
        print("-------------------")
    except Exception as e:
        print(f"Error during invocation: {e}")

if __name__ == "__main__":
    asyncio.run(main())
