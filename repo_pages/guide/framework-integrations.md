---
description: "Connect LlamaIndex, CrewAI, AutoGen, and LangGraph to Hebb Mind in ~10 lines — write and recall long-term agent memory over the MCP server or REST API."
---

# Use Hebb Mind from a Python Agent Framework

Hebb Mind ships two surfaces any Python agent framework can talk to today — no
native adapter package required:

- **MCP stdio server** (`hebb-mcp`) exposing `write_memory` / `search_memory` /
  `consolidate` / `ingest_conversation` (see [MCP Integration](./mcp-integration.md)).
- **REST API** at `http://localhost:8321` — `POST /api/v1/search` with
  `{"query": ..., "top_k": ...}` and `POST /api/v1/memories`.

Each snippet below wraps one of these surfaces for a popular framework. They are
copy-paste runnable against a locally running Hebb Mind service.

::: tip Start the service first
Every snippet assumes the Hebb Mind background service is reachable on
`http://localhost:8321`. If you haven't installed it yet:

```bash
pipx install hebb-mind
hebb setup            # first time only — downloads a small embedding model
hebb service install  # registers the OS background service (no admin needed)
```

Verify with `curl -X POST http://localhost:8321/api/v1/search -H 'Content-Type: application/json' -d '{"query":"ping","top_k":1}'`.
:::

::: tip Use the absolute path to `hebb-mcp`
The MCP snippets show `command="hebb-mcp"` for brevity. If your framework's MCP
client doesn't inherit your shell `PATH`, run `which hebb-mcp` and pass the
**absolute path** instead — otherwise the server silently fails to start.
:::

---

## LlamaIndex

LlamaIndex talks to MCP servers through `llama-index-tools-mcp`. We start the
`hebb-mcp` stdio server, load its tools, and hand them to an agent that can now
write and recall memories.

```bash
pip install llama-index llama-index-tools-mcp llama-index-llms-openai
```

```python
import asyncio
from llama_index.tools.mcp import McpToolSpec, BasicMCPClient

async def main():
    # 1. Connect to the hebb-mcp stdio server (use `which hebb-mcp` for the absolute path)
    client = BasicMCPClient(command_or_url="hebb-mcp")
    tools = await McpToolSpec(client).to_tool_list_async()      # -> [write_memory, search_memory, ...]
    search = next(t for t in tools if t.metadata.name == "search_memory")

    # 2. Write a memory, then recall it through the loaded tool
    write = next(t for t in tools if t.metadata.name == "write_memory")
    print(await write.acall(content="User prefers dark mode and compact layout",
                            tags=["preference", "ui"], importance=7.5))
    print(await search.acall(query="UI preferences", top_k=5))

asyncio.run(main())
```

Prefer REST? `POST /api/v1/search` returns `{"results": [{"memory": {...}, "score": ...}]}` —
wrap it in a custom `BaseRetriever` and plug into any `RetrieverQueryEngine`.

---

## CrewAI

CrewAI loads MCP tools via `crewai-tools`' `MCPServerAdapter`. We spin up the
`hebb-mcp` stdio server, expose its tools, and assign them to an agent.

```bash
pip install crewai crewai-tools
```

```python
from crewai import Agent, Task, Crew
from crewai.tools import MCPServerAdapter

# 1. Start the hebb-mcp stdio server and load its tools
with MCPServerAdapter({"command": "hebb-mcp"}) as tools:        # -> [write_memory, search_memory, ...]
    recall = next(t for t in tools if t.name == "search_memory")

    # 2. Give an agent the recall tool and run a one-step task
    agent = Agent(role="Memory Assistant", goal="Recall stored user preferences",
                  backstory="A helpful agent backed by Hebb Mind long-term memory.",
                  tools=[recall], llm="gpt-4o-mini")
    crew = Crew(agents=[agent], tasks=[Task(description="What UI does the user prefer?",
                                            expected_output="A short sentence.", agent=agent)])
    print(crew.kickoff())
```

Prefer REST? Hit `POST /api/v1/memories` / `POST /api/v1/search` with `requests`
inside a `crewai.tools.BaseTool` subclass.

---

## AutoGen

AutoGen **0.4+** (the `autogen-agentchat` / `autogen-ext[mcp]` packages) loads
MCP tools with `mcp_server_tools`. We connect to `hebb-mcp` over stdio and give
the tools to a `ToolUseAssistant`.

```bash
pip install "autogen-agentchat==0.4.*" "autogen-ext[openai,mcp]"
```

```python
import asyncio
from autogen_agentchat.agents import AssistantAgent
from autogen_ext.models.openai import OpenAIChatCompletionClient
from autogen_ext.tools.mcp import StdioServerParams, mcp_server_tools

async def main():
    # 1. Discover the hebb-mcp tools over stdio
    params = StdioServerParams(command="hebb-mcp", args=[], read_transport="stdio", write_transport="stdio")
    tools = await mcp_server_tools(params)                      # -> [write_memory, search_memory, ...]

    # 2. Attach them to an agent and run a recall task
    agent = AssistantAgent("memory", model_client=OpenAIChatCompletionClient(model="gpt-4o-mini"),
                           tools=tools, reflect_on_tool_use=True)
    print(await agent.run(task="Search Hebb Mind for the user's UI preferences."))

asyncio.run(main())
```

::: warning Pin the AutoGen version
AutoGen 0.2 (legacy) and 0.4+ have incompatible APIs. The snippet above targets
**0.4+**; on 0.2 use `autogen.ConversableAgent` with a custom `register_function`
that calls the REST API instead.
:::

Prefer REST? `POST /api/v1/search` works directly — wrap it in an AutoGen tool
function (`async def search_hebb(query: str) -> str`).

---

## LangGraph

LangGraph loads MCP tools through `langchain-mcp-adapters`. We start `hebb-mcp`
over stdio, load the tools, and bind them into a ReAct-style graph node.

```bash
pip install langgraph langchain-mcp-adapters langchain-openai
```

```python
import asyncio
from langchain_mcp_adapters.client import MultiServerMCPClient

async def main():
    # 1. Load hebb-mcp tools from the stdio server
    client = MultiServerMCPClient({"hebb": {"command": "hebb-mcp", "transport": "stdio"}})
    tools = await client.get_tools()                            # -> [write_memory, search_memory, ...]

    # 2. Bind them to a chat model and do a write + recall round-trip
    from langchain_openai import ChatOpenAI
    llm = ChatOpenAI(model="gpt-4o-mini").bind_tools(tools)
    write = next(t for t in tools if t.name == "write_memory")
    print(await write.ainvoke({"content": "User prefers dark mode", "tags": ["ui"], "importance": 7.5}))
    print(await llm.ainvoke("What UI does the user prefer? Use your Hebb Mind tool."))

asyncio.run(main())
```

::: tip Don't extend the WIP skeleton
`examples/05_langchain_adapter.py` is a `NotImplementedError` skeleton for a
native `BaseRetriever` / `BaseChatMessageHistory`. This page is the low-cost
"paste a snippet" bridge — a native adapter is a separate follow-up.
:::

---

## Which surface should I pick?

| Framework | Lowest-friction path | Why |
|-----------|---------------------|-----|
| LlamaIndex | MCP (`MCPClient`) | First-class `MCPClient` + tool → agent flow |
| CrewAI | MCP (`MCPServerAdapter`) | `tools=[...]` on `Agent` is idiomatic |
| AutoGen 0.4+ | MCP (`mcp_server_tools`) | `StdioServerParams` is the supported loader |
| LangGraph | MCP (`langchain-mcp-adapters`) | `get_tools()` binds straight into graph nodes |

Reach for the **REST API** only when a framework has no MCP adapter, or when you
need the full response shape (`results` + graph-expanded `related`) that the MCP
tool collapses into a text summary.

## How it works

```
LlamaIndex / CrewAI / AutoGen / LangGraph
        │ (stdio)
        v
  hebb-mcp (MCP server)  ──or──  httpx/requests ──>  REST API
        │ (HTTP)                                        │ (port 8321)
        v                                               v
  hebb service (REST API on 8321, OS background service)
        │
  Storage / Embedder / Searcher / Tag graph
```

The MCP server is a thin wrapper translating tool calls into HTTP requests to
the running Hebb Mind service — so both paths hit the same storage, embedding,
and hybrid-search engine.