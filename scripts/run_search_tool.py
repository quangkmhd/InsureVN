import asyncio
import os
import sys

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.tools.search_tool import search_web

def main():
    print("Testing search_web tool...")
    
    query="What are the best health insurance plans in VN?"
    print(f"User Query: {query}")
    
    print("\nInvoking Tool...")
    # Using normal invoke since the tool now is synchronous/basic wrapper
    response = search_web.invoke({"query": query})
    
    print("\n=== Tool Response ===")
    print(response)
    print("======================")

if __name__ == "__main__":
    main()
