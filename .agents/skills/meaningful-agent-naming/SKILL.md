---
name: meaningful-agent-naming
description: Use when creating new agents, class variables, or local identifiers within an agentic system to ensure identifiers are descriptive and domain-specific rather than generic.
---

# Meaningful Agent Naming

## Overview
Identifiers in an agentic system should reflect their specific role, domain, and functionality. Avoid generic terms like `graph`, `agent`, or `executor` when more descriptive, domain-specific names are available.

## When to Use
- Creating new agent classes or modules.
- Defining internal attributes that hold compiled graphs or executors.
- Naming local variables in factory methods (like `create()`).
- Naming tools or utility functions used by agents.

### Symptoms of Poor Naming
- Multiple agents in the same context all using the variable name `graph`.
- Ambiguity about which specific agent is being invoked (e.g., `self.agent.invoke` vs `self.policy_agent.invoke`).
- "Leakage" of framework-specific terms (like `graph` from LangGraph) into domain-level code.

## Core Pattern
Always prefer **[Domain] + [Role]** naming.

### Before (Generic)
```python
class DatabaseAgent:
    def __init__(self, graph: Any):
        self.graph = graph

    @classmethod
    async def create(cls):
        graph = create_agent(...)
        return cls(graph)
```

### After (Meaningful)
```python
class DatabaseAgent:
    def __init__(self, database_agent: Any):
        self.database_agent = database_agent

    @classmethod
    async def create(cls):
        database_agent = create_agent(...)
        return cls(database_agent)
```

## Quick Reference
| Context | Avoid | Prefer |
|---------|-------|--------|
| Attribute holding the agent | `self.graph`, `self.agent` | `self.database_agent`, `self.policy_executor` |
| Parameter in `__init__` | `graph`, `executor` | `database_agent`, `claim_graph` |
| Local variable in factory | `g`, `ag`, `res` | `db_agent`, `policy_agent` |
| Domain objects | `data`, `obj` | `insurance_policy`, `claim_request` |

## Common Mistakes
- **Framework Overload**: Using `graph` everywhere just because you're using LangGraph.
- **Redundancy**: `self.database_agent_instance` (too long) vs `self.database_agent`.
- **Inconsistency**: Naming the parameter `db_agent` but the attribute `self.graph`.

## Red Flags - STOP and Rename
- You used `graph` as a variable name.
- You used `agent` as a variable name in a multi-agent system.
- The name doesn't tell you *which* agent or *what* data it handles.
