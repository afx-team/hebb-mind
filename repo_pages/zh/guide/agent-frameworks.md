---
description: "通过 MCP 工具或 REST API，将 LlamaIndex、CrewAI、AutoGen 和 LangGraph 接入 Hebb Mind 长期记忆。"
---

# Agent 框架集成

Hebb Mind 可以与任何 Python agent 框架配合使用。本文档展示了如何使用 **MCP 工具**或 **REST API** 快速接入 LlamaIndex、CrewAI、AutoGen 和 LangGraph。

所有示例都假设已在本地运行 `hebb service`（地址 `http://localhost:8321`）。

## 前提条件

```bash
pipx install hebb-mind
hebb setup                    # 下载嵌入模型
hebb service install          # 注册后台服务
```

或者直接使用 Python SDK（无需 HTTP 服务器）：

```python
from hebb import HebbMind
hc = HebbMind()  # 进程内运行，无需启动服务
```

---

## LlamaIndex

LlamaIndex 2024+ 原生支持 MCP 工具。也可以通过 REST API 包装为工具使用。

### 使用 MCP 工具（推荐）

```python
from llama_index.core.agent import FunctionCallingAgentWorker
from llama_index.tools.mcp import MCPRemoteToolProvider
import asyncio

async def main():
    # 连接到本地 hebb-mcp 服务
    provider = MCPRemoteToolProvider(
        name="hebb",
        server_url="http://localhost:8321",
        timeout=30,
    )
    tools = await provider.get_tools()
    worker = FunctionCallingAgentWorker(tools=tools, verbose=True)
    agent = worker.as_agent()
    agent.chat("我知道用户关于 UI 偏好的哪些信息？")

asyncio.run(main())
```

### 直接使用 REST API

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
    return f"记忆已保存 (id={resp.json()['id']})"

def search_memory(query: str, top_k: int = 5) -> list[dict]:
    resp = httpx.post(f"{HEBB_URL}/api/v1/search", json={
        "query": query,
        "top_k": top_k,
        "strict_recall": True,
    })
    resp.raise_for_status()
    return resp.json().get("results", [])

# 在 LlamaIndex 工具节点中使用
from llama_index.core.tools import FunctionTool

write_tool = FunctionTool.from_defaults(fn=write_memory)
search_tool = FunctionTool.from_defaults(fn=search_memory)
```

---

## CrewAI

CrewAI 支持自定义工具。将 REST API 或 MCP 工具包装为 CrewAI 工具即可。

### 使用 REST API

```python
import httpx
from crewai import Agent, Task, Crew
from crewai.tools import BaseTool
from typing import Type
from pydantic import BaseModel, Field

class MemorySearchInput(BaseModel):
    query: str = Field(..., description="记忆搜索查询")
    top_k: int = Field(default=5, description="返回结果数量")

class MemorySearchTool(BaseTool):
    name: str = "搜索 Hebb 记忆"
    description: str = "在 Hebb Mind 中搜索相关记忆"
    args_schema: Type[BaseModel] = MemorySearchInput

    def _run(self, query: str, top_k: int = 5) -> str:
        resp = httpx.post("http://localhost:8321/api/v1/search", json={
            "query": query, "top_k": top_k, "strict_recall": True,
        })
        resp.raise_for_status()
        results = resp.json().get("results", [])
        return "\n".join(f"[{r['score']:.2f}] {r['memory']['content']}" for r in results[:top_k])

# 在 Crew 中设置
agent = Agent(role="研究员", backstory="你可以访问长期记忆。", tools=[MemorySearchTool()])
task = Task(description="用户说过关于他们偏好的哪些话？")
crew = Crew(agents=[agent], tasks=[task])
crew.kickoff()
```

### 通过 subprocess 使用 MCP 工具

```python
import subprocess, json
from crewai.tools import BaseTool

class HebbMCPTrait(BaseTool):
    name: str = "Hebb 记忆"
    description: str = "通过 hebb-mcp 写入或搜索记忆"

    def _run(self, action: str, **kwargs) -> str:
        result = subprocess.run(
            ["hebb-mcp", "call", action, json.dumps(kwargs)],
            capture_output=True, text=True
        )
        return result.stdout
```

---

## AutoGen

AutoGen 0.4+ 支持通过 `autogen-ext[mcp]` 连接 MCP 服务器。直接连接到 `hebb-mcp`。

### 使用 MCP 工具

```python
import asyncio
from autogen import Agent, AssistantAgent, UserProxyAgent
from autogen_ext.tools.mcp import McpSession, McpServerConnectionStdio

async def main():
    # 通过 stdio 连接 hebb-mcp
    async with McpSession(McpServerConnectionStdio(command="hebb-mcp")) as session:
        # 列出可用工具
        tools = await session.list_tools()
        print("可用工具:", [t.name for t in tools])

        assistant = AssistantAgent(
            "assistant",
            llm_config={"config_list": [{"model": "gpt-4o", "api_key": "YOUR_KEY"}]},
            system_message="你可以访问 Hebb Mind 记忆。使用 hebb 工具来记住和回忆信息。",
        )
        user = UserProxyAgent("user")

        chat_result = await user.initiate_chat(
            assistant,
            message="我喜欢深色模式。记住这一点。",
            extra_args={"tools": tools},
        )

asyncio.run(main())
```

### 直接使用 REST API

```python
import httpx

def write_memory(content: str, tags: list[str] | None = None) -> str:
    resp = httpx.post("http://localhost:8321/api/v1/memories", json={
        "content": content, "tags": tags or []
    })
    resp.raise_for_status()
    return f"已保存: {resp.json()['id']}"

def search_memories(query: str, top_k: int = 5) -> str:
    resp = httpx.post("http://localhost:8321/api/v1/search", json={
        "query": query, "top_k": top_k
    })
    resp.raise_for_status()
    return "\n".join(r["memory"]["content"] for r in resp.json()["results"])
```

---

## LangGraph

LangGraph 可以与任何工具配合使用。包装 REST API 或 MCP 工具，传入图节点即可。

### 使用 REST API

```python
import httpx
from langgraph.prebuilt import create_react_agent
from langchain_core.tools import tool

@tool
def hebb_write_memory(content: str, tags: list[str] | None = None) -> str:
    """将记忆写入 Hebb Mind。"""
    resp = httpx.post("http://localhost:8321/api/v1/memories", json={
        "content": content, "tags": tags or []
    })
    resp.raise_for_status()
    return f"记忆已保存 (id={resp.json()['id']})"

@tool
def hebb_search_memory(query: str, top_k: int = 5) -> str:
    """在 Hebb Mind 中搜索相关记忆。"""
    resp = httpx.post("http://localhost:8321/api/v1/search", json={
        "query": query, "top_k": top_k, "strict_recall": True
    })
    resp.raise_for_status()
    results = resp.json().get("results", [])
    return "\n".join(f"[{r['score']:.2f}] {r['memory']['content']}" for r in results)

# 构建图
agent = create_react_agent(
    model="gpt-4o",
    tools=[hebb_write_memory, hebb_search_memory],
)

# 使用
result = agent.invoke({"messages": [("user", "我喜欢简约设计。记住这个。")]})
print(result["messages"][-1].content)
```

### 使用 MCP 工具

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

## 总结

| 框架 | 最简单方式 | 关键依赖 |
|------|-----------|---------|
| LlamaIndex | 通过 `llama-index-tools-mcp` 使用 MCP | `llama-index-tools-mcp` |
| CrewAI | 将 REST API 包装为自定义工具 | `httpx` |
| AutoGen | 通过 `autogen_ext[mcp]` 使用 MCP | `autogen-ext[mcp]` |
| LangGraph | 将 REST API 包装为 `@tool` | `langgraph`, `httpx` |

所有示例都使用相同的服务端点：
- **REST API**: `POST /api/v1/memories`（写入）、`POST /api/v1/search`（搜索）
- **MCP 工具**: `write_memory`、`search_memory`、`consolidate`、`ingest_conversation`

参见：[MCP 集成指南](./mcp-integration.md)
