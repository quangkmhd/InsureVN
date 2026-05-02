import asyncio
from src.tools.mcp_client import get_sqlite_mcp_tools

async def main():
    tools = await get_sqlite_mcp_tools()
    print("Tools:", tools)
    print("Testing tool:", tools[0].name)
    try:
        res = await tools[0].ainvoke({})
        print("Result:", res)
    except Exception as e:
        print("Exception:", e)

asyncio.run(main())
