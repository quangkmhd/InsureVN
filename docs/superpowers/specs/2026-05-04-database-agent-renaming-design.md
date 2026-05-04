# Design Doc: Renaming `graph` to `database_agent` in `DatabaseAgent`

## 1. Objective
The goal of this change is to improve the clarity and maintainability of the `DatabaseAgent` class by renaming the internal `graph` variable (which holds the compiled LangChain agent) to `database_agent`. This more accurately reflects its role and follows the user's preference for descriptive naming related to the database agent.

## 2. Scope
This change is limited to `src/agents/database_agent.py`.

## 3. Architecture & Data Flow
No architectural changes are being made. The data flow remains identical; only the identifiers used to refer to the agent instance are being updated.

## 4. Components
### `DatabaseAgent` Class
- **`__init__`**:
    - Rename `graph` parameter to `database_agent`.
    - Rename `self.graph` attribute to `self.database_agent`.
- **`create` (Class Method)**:
    - Rename local variable `graph` (the result of `create_agent`) to `database_agent`.
    - Update instantiation call: `return cls(database_agent, ...)` instead of `return cls(graph, ...)`.
- **`invoke` (Instance Method)**:
    - Update invocation: `await self.database_agent.ainvoke(...)` instead of `await self.graph.ainvoke(...)`.

## 5. Error Handling
No changes to error handling logic.

## 6. Testing
### Verification Steps
1.  Verify that all instances of `graph` (parameter, local variable, and attribute) have been replaced with `database_agent`.
2.  Run existing tests for `DatabaseAgent` to ensure no regressions in functionality.
3.  Perform a manual check to ensure the code still compiles and runs without errors.
