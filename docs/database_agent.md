# DatabaseAgent Documentation

## Overview
The `DatabaseAgent` is a specialized agent within the InsureVN system designed to interact with the SQLite database. It translates natural language queries into database actions using the Model Context Protocol (MCP) and returns accurate information based on the structured data available in the system.

## Core Responsibility
- **Structured Data Retrieval**: Querying insurance benefits, premiums, hospital networks, and user profiles.
- **Accurate Answering**: Providing answers strictly based on database results without hallucination.

## Implementation Details

### Technology Stack
- **Framework**: LangChain & LangGraph.
- **LLM Initialization**: Uses `init_chat_model` for flexible provider support.
- **Tooling**: Leverages `get_sqlite_mcp_tools` to connect with the SQLite database via MCP.

### Key Class Methods

#### `create()` (Async Class Method)
Initializes the agent by:
1.  Loading environment variables.
2.  Fetching SQLite MCP tools.
3.  Configuring the LLM based on environment settings (`LLM_MODEL`, `LLM_PROVIDER`, etc.).
4.  Setting up the system prompt to define the agent's persona.
5.  Creating the agent graph.

#### `invoke(query: str)` (Async Method)
Sends a user query to the agent and returns the textual response.
- **Input**: A string containing the user's question.
- **Output**: A string containing the answer derived from the database.

## Configuration (Environment Variables)
The agent requires the following environment variables to be set in the `.env` file:

| Variable | Description | Example |
| :--- | :--- | :--- |
| `LLM_MODEL` | The name of the model to use. | `gemini-1.5-flash` or `ollama/llama3` |
| `LLM_PROVIDER` | (Optional) The provider name. | `google`, `ollama`, `openai` |
| `LLM_API_KEY` | API key for the chosen provider. | `your-api-key` |
| `LLM_BASE_URL` | (Optional) Custom base URL for the LLM. | `https://api.openrouter.ai/v1` |

## Example Usage

```python
import asyncio
from src.agents.database_agent import DatabaseAgent

async def main():
    # Create the agent
    agent = await DatabaseAgent.create()
    
    # Query the database
    response = await agent.invoke("Danh sách các bệnh viện bảo lãnh tại Hà Nội là gì?")
    print(f"Agent Response: {response}")

if __name__ == "__main__":
    asyncio.run(main())
```

## Persona & Constraints
The agent is governed by a strict system prompt:
- **Persona**: "DatabaseAgent for the InsureVN system."
- **Constraint**: Must answer strictly based on returned data.
- **Constraint**: Must not guess or make up data.
