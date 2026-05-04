import os
import sys

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from src.tools.search_tool import search_web


def main():
    print("Testing search_web tool...")

    query = "Xu hướng thị trường bảo hiểm sức khỏe tại Việt Nam năm 2024"
    print(f"User Query: {query}")

    print("Invoking tool...")
    try:
        # Note: TavilySearchResults might need a real API key in the environment to work
        response = search_web.invoke({"query": query})
        print("\n--- Search Results ---")
        print(response)
        print("-------------------")
    except Exception as e:
        print(f"Error during invocation: {e}")


if __name__ == "__main__":
    main()
