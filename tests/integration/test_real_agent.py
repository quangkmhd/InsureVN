import asyncio
import sys
import os

# Add project root to sys.path to allow importing from src
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from src.agents.database_agent import DatabaseAgent

async def main():
    print("Initializing DatabaseAgent...")
    agent = await DatabaseAgent.create()
    print("Agent initialized successfully.")
    
    query = "Lấy danh sách các bảng trong cơ sở dữ liệu"
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
