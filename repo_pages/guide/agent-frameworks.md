---
description: "Connect LlamaIndex, CrewAI, AutoGen, and LangGraph to Hebb Mind for long-term AI agent memory using MCP tools or the REST API."
---

# Agent Framework Integrations

Hebb Mind works with any Python agent framework. This page shows copy-paste snippets for **LlamaIndex**, **CrewAI**, **AutoGen**, and **LangGraph** using two approaches:

- **REST API** (no framework dependencies — just `httpx`)
- **MCP Tools** (via the `hebb-mcp` stdio server, for frameworks that support MCP)

All snippets assume a running `hebb service` at `http://localhost:8321`.

## Prerequisites

```bash
pipx install hebb-mind
hebb setup                    # downloads the embedding model
hebb service install          # registers the background service
```

Or use the Python SDK directly (`pip install hebb-mind`):

```python
from hebb import HebbMind
hc = HebbMind()  # in-process, no HTTP server needed
```

---

## LlamaIndex

LlamaIndex supports MCP tools natively via `llama-index-tools-mcp`. Alternatively, use the REST API with a simple wrapper.

### Using MCP Tools (recommended for LlamaIndex 2024+)

```python
from llama_index.core.agent import FunctionCallingAgentWorker
from llama_index.tools.mcp import MCPRemoteToolProvider
import asyncio

async def main():
    # Connect to the local hebb-mcp server
    provider = MCPRemoteToolProvider(
        name="hebb",
        server_url="http://localhost:8321",
        timeout=30,
    )
    tools = await provider.get_tools()
    worker = FunctionCallingAgentWorker(tools=tools, verbose=True)
    agent = worker.as_agent()
    agent.chat("What do I know about the user's UI preferences?")

asyncio.run(main())
```

### Using REST API directly

```python
import httpx

HEBB_URL = "http://localhost:8321"

def write_memory(content: str, tags: list[str] | None = None, importance: float = 5.0) -> str:
    resp = httpx.post(f"{HEBB_URL}/api/v1/memories", json={
        "content": content,
        "tags": tags or [],
        "importance_score": importance,
    })
    resp.raise_for_status()
    return f"Memory saved (id={resp.json()['id']})"

def search_memory(query: str, top_k: int = 5) -> list[dict]:
    resp = httpx.post(f"{HEBB_URL}/api/v1/search", json={
        "query": query,
        "top_k": top_k,
        "strict_recall": True,
    })
    resp.raise_for_status()
    return resp.json().get("results", [])

# Use in a LlamaIndex tool node
from llama_index.core.tools import FunctionTool

write_tool = FunctionTool.from_defaults(fn=write_memory)
search_tool = FunctionTool.from_defaults(fn=search_memory)
```

---

## CrewAI

CrewAI supports custom tools out of the box. Wrap the REST API or MCP tools as CrewAI tools.

### Using REST API

```python
import httpx
from crewai import Agent, Task, Crew
from crewai.tools import BaseTool
from typing import Type
from pydantic import BaseModel, Field

class MemorySearchInput(BaseModel):
    query: str = Field(..., description="Search query for memories")
    top_k: int = Field(default=5, description="Number of results")

class MemorySearchTool(BaseTool):
    name: str = "Search Hebb Memory"
    description: str = "Search for related memories in Hebb Mind"
    args_schema: Type[BaseModel] = MemorySearchInput

    def _run(self, query: str, top_k: int = 5) -> str:
        resp = httpx.post("http://localhost:8321/api/v1/search", json={
            "query": query, "top_k": top_k, "strict_recall": True,
        })
        resp.raise_for_status()
        results = resp.json().get("results", [])
        return "\n".join(f"[{r['score']:.2f}] {r['memory']['content']}" for r in results[:top_k])

# In your crew setup
agent = Agent(role="Researcher", backstory="You have access to long-term memory.", tools=[MemorySearchTool()])
task = Task(description="What did the user say about their preferences?")
crew = Crew(agents=[agent], tasks=[task])
crew.kickoff()
```

### Using MCP Tools via subprocess

```python
import subprocess, json
from crewai.tools import BaseTool

class HebbMCPTrait(BaseTool):
    name: str = "Hebb Memory"
    description: str = "Write or search memory via hebb-mcp"

    def _run(self, action: str, **kwargs) -> str:
        result = subprocess.run(
            ["hebb-mcp", "call", action, json.dumps(kwargs)],
            capture_output=True, text=True
        )
        return result.stdout
```

---

## AutoGen

AutoGen supports MCP servers via `autogen-ext[mcp]`. Connect directly to `hebb-mcp`.

### Using MCP Tools (AutoGen 0.4+)

```python
import asyncio
from autogen import Agent, AssistantAgent, UserProxyAgent
from autogen_ext.tools.mcp import McpSession, McpServerConnectionStdio

async def main():
    # Connect to hebb-mcp via stdio
    async with McpSession(McpServerConnectionStdio(command="hebb-mcp")) as session:
        # List available tools
        tools = await session.list_tools()
        print("Available tools:", [t.name for t in tools])

        assistant = AssistantAgent(
            "assistant",
            llm_config={"config_list": [{"model": "gpt-4o", "api_key": "YOUR_KEY"}]},
            system_message="You have access to Hebb Mind memory. Use the hebb tools to remember and recall.",
        )
        user = UserProxyAgent("user")

        chat_result = await user.initiate_chat(
            assistant,
            message="I prefer dark mode. Remember that.",
            extra_args={"tools": tools},
        )

asyncio.run(main())
```

### Using REST API directly

```python
import httpx

def write_memory(content: str, tags: list[str] | None = None) -> str:
    resp = httpx.post("http://localhost:8321/api/v1/memories", json={
        "content": content, "tags": tags or []
    })
    resp.raise_for_status()
    return f"Saved: {resp.json()['id']}"

def search_memories(query: str, top_k: int = 5) -> str:
    resp = httpx.post("http://localhost:8321/api/v1/search", json={
        "query": query, "top_k": top_k
    })
    resp.raise_for_status()
    return "\n".join(r["memory"]["content"] for r in resp.json()["results"])
```

---

## LangGraph

LangGraph works with any tool. Wrap the REST API or MCP tools and pass them to your graph nodes.

### Using REST API

```python
import httpx
from langgraph.prebuilt import create_react_agent
from langchain_core.tools import tool

@tool
def hebb_write_memory(content: str, tags: list[str] | None = None) -> str:
    """Write a memory to Hebb Mind."""
    resp = httpx.post("http://localhost:8321/api/v1/memories", json={
        "content": content, "tags": tags or []
    })
    resp.raise_for_status()
    return f"Memory saved (id={resp.json()['id']})"

@tool
def hebb_search_memory(query: str, top_k: int = 5) -> str:
    """Search Hebb Mind for relevant memories."""
    resp = httpx.post("http://localhost:8321/api/v1/search", json={
        "query": query, "top_k": top_k, "strict_recall": True
    })
    resp.raise_for_status()
    results = resp.json().get("results", [])
    return "\n".join(f"[{r['score']:.2f}] {r['memory']['content']}" for r in results)

# Build the graph
agent = create_react_agent(
    model="gpt-4o",
    tools=[hebb_write_memory, hebb_search_memory],
)

# Use it
result = agent.invoke({"messages": [("user", "I like minimalist designs. Remember this.")]})
print(result["messages"][-1].content)
```

### Using MCP Tools

```python
from langgraph_prebuilt import create_react_agent
from langchain_mcp_adapters.client import MultiServerMCPClient

async def get_tools():
    client = MultiServerMCPClient({
        "hebb": {"command": "hebb-mcp"}
    })
    return await client.get_tools()

tools = await get_tools()
agent = create_react_agent(model="gpt-4o", tools=tools)
```

---

## Summary

| Framework | Easiest approach | Key dependency |
|-----------|-----------------|----------------|
| LlamaIndex | MCP via `llama-index-tools-mcp` | `llama-index-tools-mcp` |
| CrewAI | REST API as custom tool | `httpx` |
| AutoGen | MCP via `autogen_ext[mcp]` | `autogen-ext[mcp]` |
| LangGraph | REST API as `@tool` | `langgraph`, `httpx` |

All snippets target the same surfaces:
- **REST**: `POST /api/v1/memories` (write), `POST /api/v1/search` (read)
- **MCP**: `write_memory`, `search_memory`, `consolidate`, `ingest_conversation`

See also: [MCP Integration](./mcp-integration.md)
