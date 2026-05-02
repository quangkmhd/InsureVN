import asyncio
from src.tools.mcp_client import get_sqlite_mcp_tools
import psutil
import os

async def main():
    print(f"Initial processes: {len([p for p in psutil.process_iter(['name', 'cmdline']) if 'server.py' in ' '.join(p.info['cmdline'] or [])])}")
    
    # Call 3 times
    for _ in range(3):
        tools = await get_sqlite_mcp_tools()
        await tools[0].ainvoke({})
    
    # Check processes
    procs = [p for p in psutil.process_iter(['name', 'cmdline']) if 'server.py' in ' '.join(p.info['cmdline'] or [])]
    print(f"Final processes: {len(procs)}")

asyncio.run(main())
