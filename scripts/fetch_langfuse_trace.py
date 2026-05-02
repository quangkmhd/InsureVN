import asyncio
import os
import sys
import json
from pathlib import Path
from dotenv import load_dotenv

# Add project root to PYTHONPATH
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from langfuse import Langfuse
from src.core.config import settings

# Load .env
load_dotenv(dotenv_path=project_root / ".env")

async def fetch_latest_trace_content():
    print("=== FETCHING LATEST TRACE CONTENT FROM LANGFUSE API ===")
    
    # Initialize Langfuse Client
    langfuse = Langfuse(
        public_key=os.getenv("LANGFUSE_PUBLIC_KEY"),
        secret_key=os.getenv("LANGFUSE_SECRET_KEY"),
        host=os.getenv("LANGFUSE_HOST", "http://localhost:3000")
    )
    
    # 1. Fetch latest traces via API client
    print("Fetching traces...")
    traces = langfuse.api.trace.list(limit=5)
    
    if not traces.data:
        print("No traces found on Langfuse server.")
        return

    # Find the most recent database-agent-execution trace
    target_trace = None
    for t in traces.data:
        if t.name == "database-agent-execution":
            target_trace = t
            break
    
    if not target_trace:
        print("Could not find a 'database-agent-execution' trace.")
        target_trace = traces.data[0] # Fallback to latest
        print(f"Falling back to latest trace: {target_trace.name}")

    print(f"\nAnalyzing Trace ID: {target_trace.id}")
    print(f"Timestamp: {target_trace.timestamp}")
    
    # 2. Fetch detailed trace data including observations
    full_trace = langfuse.api.trace.get(target_trace.id)
    
    print("\n--- TRACE OBSERVATIONS (Generations/Thinking) ---")
    
    # Filter for Generations
    generations = [obs for obs in full_trace.observations if obs.type == "GENERATION"]
    
    if not generations:
        print("No GENERATION observations found in this trace.")
        print(f"Observation types found: {[obs.type for obs in full_trace.observations]}")
    
    for i, gen in enumerate(generations):
        print(f"\n[Generation {i+1}: {gen.name}]")
        print(f"Model: {gen.model}")
        
        print("\n>> FULL INPUT (System Prompt + History + Tools):")
        # Pretty print the input JSON
        print(json.dumps(gen.input, indent=2, ensure_ascii=False))
        
        print("\n>> OUTPUT (Thinking + Tool Call Decision):")
        # Output contains the text and any tool calls the model wants to make
        print(gen.output)
        
        if hasattr(gen, "usage"):
            print(f"\nUsage: {gen.usage}")

    # Tool calls
    tools = [obs for obs in full_trace.observations if obs.type == "TOOL"]
    for i, tool in enumerate(tools):
        print(f"\n[Tool Execution {i+1}: {tool.name}]")
        print(f"Input: {json.dumps(tool.input, indent=2, ensure_ascii=False)}")
        print(f"Output: {json.dumps(tool.output, indent=2, ensure_ascii=False)}")

if __name__ == "__main__":
    asyncio.run(fetch_latest_trace_content())
