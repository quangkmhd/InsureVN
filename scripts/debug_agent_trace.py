import asyncio
import os
import sys
import json
from pathlib import Path

# Add project root to PYTHONPATH
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from src.agents.database_agent import DatabaseAgent
from langfuse import get_client

async def run_trace_test():
    print("=== STARTING TRACE TEST ===")
    
    # 1. Initialize Agent
    agent = await DatabaseAgent.create()
    
    # 2. Run a query that triggers a tool call
    # We use a unique session_id to find the trace easily
    session_id = f"test-trace-{os.urandom(4).hex()}"
    print(f"Running query with session_id: {session_id}")
    
    query = "Liệt kê các công ty bảo hiểm đang có trong hệ thống"
    
    # We'll capture the trace by waiting for the flush
    response = await agent.invoke(
        query, 
        config={"session_id": session_id, "user_id": "tester-01"}
    )
    
    print("\n--- AGENT RESPONSE ---")
    print(response)
    print("----------------------\n")

    # 3. Wait for Langfuse to sync
    print("Waiting for Langfuse to sync...")
    get_client().flush()
    await asyncio.sleep(2) # Give it a moment to process

    # 4. Fetch the trace from Langfuse (Optional, if possible)
    # Since we might not have network access to localhost:3000 from here,
    # we'll focus on showing what was logged to the file.
    
    log_file = project_root / "log" / "mcp_database.log"
    if log_file.exists():
        print("\n--- EXTRACTED JSON LOGS (Simulating Trace Output) ---")
        with open(log_file, "r") as f:
            # Get last 5 lines which should be our test
            lines = f.readlines()[-10:]
            for line in lines:
                try:
                    # Parse and re-print for pretty formatting
                    data = json.loads(line)
                    if data.get("session_id") == session_id or data.get("tool"):
                        print(json.dumps(data, indent=2, ensure_ascii=False))
                except json.JSONDecodeError:
                    continue
    else:
        print(f"\nLog file not found at {log_file}")

if __name__ == "__main__":
    asyncio.run(run_trace_test())
