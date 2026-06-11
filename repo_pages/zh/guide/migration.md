---
description: "把 mem0、Letta、Zep 的 Agent 记忆迁移到 Hebb Mind：概念与 API 映射、迁移前后代码对照、数据导入步骤，并如实标注能力差距。"
---

# 从 mem0 / Letta / Zep 迁移

本页把三个最常被问到的 Agent 记忆框架的概念和 API 映射到 Hebb Mind 上，并演示如何把数据搬过来。Hebb Mind 比这三者都年轻；我们如实指出差距，方便你判断今天这一搬是否划算。

所有 Python 片段都使用公开门面（facade）：

```python
from hebb import HebbMind

mem = HebbMind()  # 在进程内直接运行引擎（存储 + Embedding + 图谱 + 检索）
```

门面在**进程内**直接运行整套引擎（存储、embedder、图谱、检索），它**不是** HTTP 服务的客户端，也无需后台服务在运行。它默认从 cwd 起最近的 `hebb.json` 加载配置（找不到则回退 `~/.hebb/hebb.json`）。

---

## 从 mem0 迁移

[mem0ai/mem0](https://github.com/mem0ai/mem0) 是形态最接近的同类：围绕向量库的 REST 风格 add/search/update/delete API，可选图谱和 LLM 驱动的事实抽取。

### 概念映射

| mem0 | Hebb Mind | 说明 |
|---|---|---|
| `Memory` | `Memory` | 同一个概念 —— 一条被记住的文本。 |
| `user_id` / `agent_id` / `run_id` | `partition`（分区） | Hebb Mind 用一个正交的命名空间；用分隔符把你的多个 ID 拼起来即可（如 `f"{user}:{agent}"`）。 |
| `categories`（自动抽取） | `tags`（由巩固抽取） | Hebb Mind 的标签由巩固代理抽取，而非写入时。 |
| `metadata`（自由字典） | `metadata`（自由字典） | 一一对应。 |
| `add()` 经 LLM 抽取事实 | `POST /api/v1/ingest` 抽取事实；`POST /api/v1/memories`（或 `mem.add()`）原样存储 | Hebb Mind 有两条路径；要 mem0 那种「给我一轮对话、帮我抽取记忆」的行为，选 `ingest`（REST）或 MCP 的 `ingest_conversation`。 |
| 托管版「Mem0 Platform」 | 无 —— 当前仅本地 | 见 [FAQ](../faq.md#有托管版吗)。 |
| 图谱记忆（可选 Neo4j） | 内置的标签 / 共现知识图谱 | 模型不同。mem0 的图谱是实体-关系，我们的是标签-边。见 [知识图谱](../concepts/knowledge-graph.md)。 |

### 代码：迁移前后

**之前（mem0）：**

```python
from mem0 import Memory

m = Memory()
m.add("I'm allergic to peanuts", user_id="alice", metadata={"source": "chat"})
results = m.search("food allergies", user_id="alice", limit=5)
```

**之后（Hebb Mind）：**

```python
from hebb import HebbMind

mem = HebbMind()
mem.add(
    "I'm allergic to peanuts",
    partition="alice",
    metadata={"source": "chat"},
)
results = mem.search("food allergies", partition_ids=["alice"], top_k=5)
for hit in results:
    print(hit.score, hit.memory.content)
```

`search()` 返回 `list[MemorySearchResult]`，命中文本通过 `hit.memory.content` 读取（不是命中对象的顶层属性）。

### 数据导入

我们暂时还没有一键导入 mem0 dump 的工具。两边的 schema 足够接近，用 mem0 的 `get_all()` 配合一个循环逐条调用 Hebb Mind 的 `mem.add()`，30 行左右的脚本就能搬走大部分数据；一等公民的导入器在 [issue #TBD](https://github.com/afx-team/hebb-mind/issues) 上跟踪。欢迎 PR。

### 当前我们落后 mem0 的地方

- 没有托管 / 云端版 —— 你自己跑这个二进制。
- 没有官方 Neo4j 图谱后端（我们有内置的标签图谱；更丰富的实体-关系抽取在 roadmap 上）。
- mem0 的 SDK 面更广（TypeScript、更多集成）。我们有 Python + REST + MCP。

---

## 从 Letta 迁移

[letta-ai/letta](https://github.com/letta-ai/letta)（前身 MemGPT）是一个带记忆层的有状态 Agent 框架，而不是纯记忆框架。迁移的问题是：「我能不能在保留自己 Agent 循环的同时，用 Hebb Mind 作为 Letta 的记忆？」基本可以。

### 概念映射

| Letta | Hebb Mind | 说明 |
|---|---|---|
| Agent（带持久化状态） | 无 —— 自带你的 Agent 循环 | Hebb Mind 只存记忆，不运行 Agent。 |
| 核心记忆（上下文内的块） | 无 | 继续用 Letta 的块；每轮从 Hebb Mind 拉取补充。 |
| 召回记忆（完整对话历史） | 每轮 `POST /api/v1/ingest` | 用 Hebb Mind 的 ingest 替换 Letta 的召回存储。 |
| 归档记忆（向量库） | `HebbMind.add` + `HebbMind.search` | 直接替换。 |
| `archival_memory_search(query)` 工具 | 包一层 `mem.search(query)` 暴露成你的工具 | 一行垫片。 |
| Sources / 数据摄取 | `POST /api/v1/memories`（批量）或 `ingest`（对话） | — |

### 代码：迁移前后

**之前（Letta 归档记忆工具）：**

```python
# Letta agent 内部
agent.memory.archival_memory_insert("User prefers dark mode")
hits = agent.memory.archival_memory_search("UI preferences", count=5)
```

**之后（Hebb Mind，作为 Letta 的归档存储）：**

```python
from hebb import HebbMind

mem = HebbMind()
mem.add("User prefers dark mode", partition=agent_id, importance=7.5)
hits = mem.search("UI preferences", partition_ids=[agent_id], top_k=5)
for hit in hits:
    print(hit.memory.content)
```

把它注册成一个 Letta 工具，Agent 循环的其余部分都不用改。

### 数据导入

Letta 把归档记忆存在 PostgreSQL（或 SQLite）里。最简单的路径是对 Letta 的 `archival_passage` 表做一次 SELECT，再在一个小脚本里逐行 `mem.add()`。暂无官方导入器 —— 见 [issue #TBD](https://github.com/afx-team/hebb-mind/issues)。

### 当前我们落后 Letta 的地方

- 没有 Agent 运行时、没有工具调用循环、没有模型抽象层。Hebb Mind 只是存储那一半。
- 没有「核心 / 召回 / 归档」三级层次和自动淘汰策略 —— 我们是单一存储，上面叠了巩固 / 遗忘。
- 没有多 Agent 编排原语。

如果你要的是一个自带记忆的完整 Agent 框架，那就留在 Letta，把 Hebb Mind 当作可替换的归档后端。

---

## 从 Zep 迁移

[getzep/zep](https://github.com/getzep/zep)（及开源的 [graphiti](https://github.com/getzep/graphiti)）以基于对话历史的知识图谱推理见长。Zep Cloud 额外提供会话级记忆和检索。

### 概念映射

| Zep | Hebb Mind | 说明 |
|---|---|---|
| `Session` | `partition` | 把 Zep 的 session id 当作分区用。 |
| `Message` | 经 `/ingest` 摄入的一条 `Memory` | Zep 既存原始消息也存合成事实；Hebb Mind 经 `ingest` 同时做到。 |
| `Fact`（LLM 合成） | 由巩固代理写入的 `Memory` | 概念相当；我们是周期性巩固，而非每条消息都合成。 |
| Graphiti 知识图谱（实体 + 时序边） | 标签 / 共现图谱 | **Zep 的图谱更丰富。** 见下方差距。 |
| `memory.search()` | `HebbMind.search()` | API 相似。 |
| Zep Cloud / 托管 | 无 | 仅本地。 |

### 代码：迁移前后

**之前（Zep Python SDK）：**

```python
from zep_python import ZepClient
from zep_python.memory import Memory, Message

zep = ZepClient(base_url="https://api.getzep.com", api_key="...")
zep.memory.add_memory(
    session_id="alice",
    memory=Memory(messages=[Message(role="user", content="I run a vegan bakery")]),
)
results = zep.memory.search_memory("alice", text="user occupation", limit=5)
```

**之后（Hebb Mind）：**

门面没有 `ingest()` 方法 —— 批量 / 逐轮摄入走 REST `POST /api/v1/ingest` 或 MCP 的 `ingest_conversation`。逐条迁移时直接循环调用 `mem.add()`：

```python
from hebb import HebbMind

mem = HebbMind()
messages = [{"role": "user", "content": "I run a vegan bakery"}]
for msg in messages:
    mem.add(msg["content"], partition="alice", metadata={"role": msg["role"]})

results = mem.search("user occupation", partition_ids=["alice"], top_k=5)
for hit in results:
    print(hit.score, hit.memory.content)
```

要 LLM 驱动的事实抽取（Zep 那种合成事实），把整段对话作为 `content` 发给 REST 接口（接口会自动识别 Claude Code JSONL / ChatGPT JSON / 纯文本格式，可用 `format_hint` 强制指定）：

```bash
curl -X POST http://localhost:8321/api/v1/ingest \
  -H 'Content-Type: application/json' \
  -d '{"content": "user: I run a vegan bakery", "format_hint": "plain", "partition_id": "alice"}'
```

### 数据导入

Zep 暴露 `GET /sessions/{id}/messages` 和 `GET /sessions/{id}/facts`。拉取这些再逐条 `mem.add()`（或对原始消息走 REST `/ingest`）就能覆盖常见场景。暂无官方导入器 —— [issue #TBD](https://github.com/afx-team/hebb-mind/issues)。

### 当前我们落后 Zep 的地方

- **图谱推理。** Graphiti 建模实体以及它们之间*带时间范围*的关系（「Alice 在 2022-01 到 2024-07 期间任职于 Bakery」）。我们的图谱是带频次权重的标签-边 —— 召回很强，但对显式的时序-关系查询较弱。
- **事实合成节奏。** Zep 每条消息都抽取事实；我们在定时巩固时抽取。Zep 的事实更新鲜，Hebb Mind 的 LLM 成本更低。
- **托管服务和 SLA。** Zep 有，我们没有。

如果你的场景今天就重度依赖实体-时序图谱查询，Zep / Graphiti 仍是更强的选择。如果你要的是本地优先、单一二进制、原生 MCP、带神经科学风味遗忘的记忆，Hebb Mind 更契合。

---

## 三种迁移的通用要点

- **先在一个全新分区里试。** 批量导入前，先迁移一个 user / agent / session。
- **导入后重新巩固。** `curl -X POST http://localhost:8321/api/v1/admin/consolidate` 会对新记忆跑一遍巩固代理 —— 标签抽取和去重都需要它。需要配置 `llm_model`；见 [故障排查](../troubleshooting.md#consolidate-返回-processed-0-或冲突一直没被解决)。
- **用 Web 控制台核对。** 打开 <http://localhost:8321/>，扫一眼「记忆」标签页，确认导入落到了你预期的地方。见 [Web 控制台](./web-console.md)。
- **一开始就选对 Embedding 维度。** 摄入后再换 `embedding_model` 会强制重新计算向量。先想清楚目标语言，参考 [切换 Embedding 模型](./switch-embedding-model.md)。
