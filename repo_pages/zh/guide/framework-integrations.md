---
description: "用约 10 行代码把 LlamaIndex、CrewAI、AutoGen、LangGraph 接入 Hebb Mind —— 通过 MCP 服务或 REST API 写入与召回智能体长期记忆。"
---

# 在 Python Agent 框架中使用 Hebb Mind

Hebb Mind 目前对外提供两套接口，任何 Python agent 框架都能直接调用，无需安装原生适配包：

- **MCP stdio 服务**（`hebb-mcp`），暴露 `write_memory` / `search_memory` /
  `consolidate` / `ingest_conversation` 四个工具（见 [MCP 集成](./mcp-integration.md)）。
- **REST API**，地址 `http://localhost:8321` —— `POST /api/v1/search`（body
  `{"query": ..., "top_k": ...}`）与 `POST /api/v1/memories`。

下面每个框架给一段可直接复制运行的示例，均假设本地 Hebb Mind 服务已在
`http://localhost:8321` 运行。

::: tip 先把服务跑起来
每个示例都假设 Hebb Mind 后台服务在 `http://localhost:8321` 可达。如果还没装：

```bash
pipx install hebb-mind
hebb setup            # 首次使用 —— 下载一个小型 embedding 模型
hebb service install  # 注册后台服务（默认用户级，无需管理员权限）
```

用 `curl -X POST http://localhost:8321/api/v1/search -H 'Content-Type: application/json' -d '{"query":"ping","top_k":1}'` 验证是否通。
:::

::: tip 关于 `command` 路径
下面的 MCP 示例为简洁起见写的是裸 `hebb-mcp`。如果你的框架 MCP 客户端不继承 shell 的
`PATH`，请用 `which hebb-mcp` 查出**绝对路径**再填入 —— 否则服务会静默启动失败。
:::

---

## LlamaIndex

LlamaIndex 通过 `llama-index-tools-mcp` 连接 MCP 服务。我们启动 `hebb-mcp` stdio 服务，
加载其工具，然后交给一个能写入与召回记忆的 agent。

```bash
pip install llama-index llama-index-tools-mcp llama-index-llms-openai
```

```python
import asyncio
from llama_index.tools.mcp import McpToolSpec, BasicMCPClient

async def main():
    # 1. 连接 hebb-mcp stdio 服务（用 `which hebb-mcp` 取绝对路径）
    client = BasicMCPClient(command_or_url="hebb-mcp")
    tools = await McpToolSpec(client).to_tool_list_async()      # -> [write_memory, search_memory, ...]
    search = next(t for t in tools if t.metadata.name == "search_memory")

    # 2. 写一条记忆，再通过加载的工具召回
    write = next(t for t in tools if t.metadata.name == "write_memory")
    print(await write.acall(content="用户偏好深色模式与紧凑布局",
                            tags=["preference", "ui"], importance=7.5))
    print(await search.acall(query="UI 偏好", top_k=5))

asyncio.run(main())
```

想用 REST？`POST /api/v1/search` 返回 `{"results": [{"memory": {...}, "score": ...}]}` ——
包成一个自定义 `BaseRetriever`，即可接入任意 `RetrieverQueryEngine`。

---

## CrewAI

CrewAI 通过 `crewai-tools` 的 `MCPServerAdapter` 加载 MCP 工具。我们拉起 `hebb-mcp` stdio
服务，暴露其工具，再分配给一个 agent。

```bash
pip install crewai crewai-tools
```

```python
from crewai import Agent, Task, Crew
from crewai.tools import MCPServerAdapter

# 1. 启动 hebb-mcp stdio 服务并加载其工具
with MCPServerAdapter({"command": "hebb-mcp"}) as tools:        # -> [write_memory, search_memory, ...]
    recall = next(t for t in tools if t.name == "search_memory")

    # 2. 把召回工具交给 agent，跑一个单步任务
    agent = Agent(role="记忆助手", goal="召回已存储的用户偏好",
                  backstory="一个由 Hebb Mind 长期记忆支撑的助手。",
                  tools=[recall], llm="gpt-4o-mini")
    crew = Crew(agents=[agent], tasks=[Task(description="用户偏好什么 UI？",
                                            expected_output="一句话简述。", agent=agent)])
    print(crew.kickoff())
```

想用 REST？用 `requests` 直接打 `POST /api/v1/memories` / `POST /api/v1/search`，包在一个
`crewai.tools.BaseTool` 子类里即可。

---

## AutoGen

AutoGen **0.4+**（`autogen-agentchat` / `autogen-ext[mcp]` 包）通过 `mcp_server_tools` 加载
MCP 工具。我们经 stdio 连接 `hebb-mcp`，把工具交给一个 `ToolUseAssistant`。

```bash
pip install "autogen-agentchat==0.4.*" "autogen-ext[openai,mcp]"
```

```python
import asyncio
from autogen_agentchat.agents import AssistantAgent
from autogen_ext.models.openai import OpenAIChatCompletionClient
from autogen_ext.tools.mcp import StdioServerParams, mcp_server_tools

async def main():
    # 1. 经 stdio 发现 hebb-mcp 的工具
    params = StdioServerParams(command="hebb-mcp", args=[], read_transport="stdio", write_transport="stdio")
    tools = await mcp_server_tools(params)                      # -> [write_memory, search_memory, ...]

    # 2. 把工具挂到 agent 上，跑一个召回任务
    agent = AssistantAgent("memory", model_client=OpenAIChatCompletionClient(model="gpt-4o-mini"),
                           tools=tools, reflect_on_tool_use=True)
    print(await agent.run(task="在 Hebb Mind 里搜索用户的 UI 偏好。"))

asyncio.run(main())
```

::: warning 锁定 AutoGen 版本
AutoGen 0.2（旧版）与 0.4+ 的 API 不兼容。上面的示例面向 **0.4+**；若用 0.2，请改用
`autogen.ConversableAgent`，通过 `register_function` 注册一个调用 REST API 的函数。
:::

想用 REST？`POST /api/v1/search` 可直接调用 —— 包成一个 AutoGen 工具函数
（`async def search_hebb(query: str) -> str`）即可。

---

## LangGraph

LangGraph 通过 `langchain-mcp-adapters` 加载 MCP 工具。我们经 stdio 启动 `hebb-mcp`，加载
工具，再把它们绑定到一个 ReAct 风格的图节点。

```bash
pip install langgraph langchain-mcp-adapters langchain-openai
```

```python
import asyncio
from langchain_mcp_adapters.client import MultiServerMCPClient

async def main():
    # 1. 从 stdio 服务加载 hebb-mcp 工具
    client = MultiServerMCPClient({"hebb": {"command": "hebb-mcp", "transport": "stdio"}})
    tools = await client.get_tools()                            # -> [write_memory, search_memory, ...]

    # 2. 绑定到 chat 模型，做一次写入 + 召回往返
    from langchain_openai import ChatOpenAI
    llm = ChatOpenAI(model="gpt-4o-mini").bind_tools(tools)
    write = next(t for t in tools if t.name == "write_memory")
    print(await write.ainvoke({"content": "用户偏好深色模式", "tags": ["ui"], "importance": 7.5}))
    print(await llm.ainvoke("用户偏好什么 UI？用你的 Hebb Mind 工具查一下。"))

asyncio.run(main())
```

::: tip 不要去补那个 WIP 骨架
`examples/05_langchain_adapter.py` 是一个 `NotImplementedError` 骨架，目标是原生
`BaseRetriever` / `BaseChatMessageHistory`。本页是低成本的"复制即用"过渡桥 —— 原生适配器是
独立的后续任务。
:::

---

## 该选哪套接口？

| 框架 | 摩擦最低的路径 | 原因 |
|------|--------------|------|
| LlamaIndex | MCP（`MCPClient`） | 一等公民 `MCPClient` + 工具 → agent 流程 |
| CrewAI | MCP（`MCPServerAdapter`） | `Agent` 的 `tools=[...]` 是惯用写法 |
| AutoGen 0.4+ | MCP（`mcp_server_tools`） | `StdioServerParams` 是受支持的加载器 |
| LangGraph | MCP（`langchain-mcp-adapters`） | `get_tools()` 可直接绑进图节点 |

只有当一个框架没有 MCP 适配器、或你需要 MCP 工具折叠成文本摘要之前的完整响应结构
（`results` + 图谱扩展的 `related`）时，才改用 **REST API**。

## 工作原理

```
LlamaIndex / CrewAI / AutoGen / LangGraph
        │ (stdio)
        v
  hebb-mcp（MCP 服务）  ──或──  httpx/requests ──>  REST API
        │ (HTTP)                                      │ (端口 8321)
        v                                             v
  hebb 服务（端口 8321 的 REST API，由 OS 后台服务运行）
        │
  存储 / Embedding / 检索器 / 标签图谱
```

MCP 服务只是一个薄封装，把工具调用翻译成对 Hebb Mind 服务的 HTTP 请求 —— 所以两条路径
最终都命中同一套存储、embedding 与混合检索引擎。