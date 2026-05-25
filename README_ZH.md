<p align="center">
  <h1 align="center"><a href="https://afx-team.github.io/hebb-mind/zh/">Hebb Mind</a></h1>
  <p align="center"><strong>一套受神经科学启发的 AI Agent 记忆框架 — 以神经心理学家唐纳德·赫布命名，建立在他给出的法则之上：一起放电的神经元，会连到一起。</strong></p>
  <p align="center"><em>编码、回放、巩固、遗忘。沿着大脑走过的路径。</em></p>
  <p align="center"><a href="https://afx-team.github.io/hebb-mind/zh/">文档</a> · <a href="README.md">English</a> | <a href="README_ZH.md">中文</a></p>
</p>

<p align="center">
  <a href="https://afx-team.github.io/hebb-mind/zh/"><img src="https://img.shields.io/badge/docs-afx--team.github.io-blue" alt="Documentation"></a>
  <a href="https://github.com/afx-team/hebb-mind/actions"><img src="https://github.com/afx-team/hebb-mind/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="https://pypi.org/project/hebb-mind/"><img src="https://img.shields.io/pypi/v/hebb-mind" alt="PyPI"></a>
  <a href="https://github.com/afx-team/hebb-mind/blob/main/LICENSE"><img src="https://img.shields.io/badge/license-MIT-blue" alt="License"></a>
  <img src="https://img.shields.io/pypi/pyversions/hebb-mind" alt="Python">
</p>

---

1957 年，神经外科医生为治疗一位代号 H.M. 的癫痫患者切除了他双侧的海马体。手术让发作停止了，但他从此再也无法形成新的长期记忆 — 每一顿饭、每一张面孔，对他来说都是初见。半个多世纪的认知神经科学研究 [(Squire, 1992; Tulving, 2002)](#致谢) 由此一步步揭开了海马体的工作方式：它**编码**当下的经验片段、在静息时**回放**这些片段 [(Wilson & McNaughton, 1994)](#致谢)、把重要的部分**巩固**为长期知识、并**任由其余消退** [(Ebbinghaus, 1885)](#致谢)。

今天的 AI Agent 就是 H.M. — 它们每一次对话都从零开始。

**Hebb Mind** 这个项目要为你的 Agent 补上这条缺失的回路。`pip install` 后一行命令即可在本地拉起 REST + MCP 端点，跑同样的四阶段循环：编码 → 回放 → 巩固 → 遗忘。SQLite 充当存储，sentence-transformers 充当"皮层"做嵌入，NetworkX 维护标签图谱。**零外部服务。** 只有当你希望巩固阶段真正"工作"时，才需要配置一个 LLM Key。

与同类相比：`mem0` 是云优先、只追加；`letta` 需要外部数据库 + 独立的 sleeptime agent；`zep` 依赖 Postgres + Neo4j。Hebb Mind 是一个二进制、一条生物学意义上的回路。

<!-- TODO(asset): screenshot of /index.html web console with sample memories -->
<p align="center">
  <img src="repo_pages/public/web-console-hero.png" alt="Hebb Mind Web 控制台 — 分区记忆与标签图谱" width="760">
</p>

## 快速开始

### 60 秒上手 — 不需要 API Key

写入和混合检索完全离线运行（基于内置的本地 Embedding 模型）。

```bash
pip install -U hebb-mind
hebb setup        # 根据系统语言选择 Embedding 模型
hebb start        # 服务地址 http://localhost:8321/
```

另开一个终端：

```bash
curl -X POST http://localhost:8321/api/v1/memories \
  -H 'Content-Type: application/json' \
  -d '{"content": "用户偏好深色模式与紧凑布局", "tags": ["preference", "ui"]}'

curl -X POST http://localhost:8321/api/v1/search \
  -H 'Content-Type: application/json' \
  -d '{"query": "UI 偏好", "top_k": 5}'
```

打开 <http://localhost:8321/> 即可使用 Web 控制台。<!-- TODO(asset): repo_pages/public/quickstart-cast.gif (asciinema of the 60-second path) -->

<p align="center">
  <img src="repo_pages/public/quickstart-cast.gif" alt="Asciinema 演示：60 秒完成安装、setup、启动、写入、检索" width="720">
</p>

### 完整体验（5 分钟）— 启用 LLM 巩固

记忆巩固、冲突解决、标签提取需要一个 LLM 后端。**未配置 Key 时这些接口为静默 no-op**（这是 v0.1.1 已知问题，详见 [#consolidation-no-op](https://afx-team.github.io/hebb-mind/zh/troubleshooting.html)）。

```bash
hebb config set llm_api_key sk-...
hebb config set llm_model openai/gpt-4o-mini
# 通过 LiteLLM 接入通义千问 / GLM / Kimi：
hebb config set llm_base_url https://dashscope.aliyuncs.com/compatible-mode/v1
```

手动触发巩固，或等待每日 18:00 的定时任务：

```bash
curl -X POST http://localhost:8321/api/v1/admin/consolidate
```

## 为什么叫 "Hebb Mind"？

1949 年，加拿大心理学家 **唐纳德·O·赫布（Donald O. Hebb，1904–1985）** 出版《行为的组织》（*The Organization of Behavior*），提出了一条奠定我们对大脑学习方式认知的法则：当一个神经元持续参与激发另一个神经元时，两者之间的连接就会增强。半个多世纪后，它被浓缩成一句话：

> **一起放电的神经元，会连到一起（neurons that fire together, wire together）。**

赫布的洞见是：记忆不是一个"存放的地点"，而是一种"连接的模式"。共同出现的概念会被物理地连成**细胞集群（cell assembly）**，激活其中一部分就能唤回全部。重复会强化连接，弃用则任其消退。这条法则 — 赫布学习（Hebbian learning）— 是此后一切人工神经网络与联想记忆系统的源头。

**Hebb Mind 正是跑在这条法则上。** 它的标签**知识图谱**本身就是一个细胞集群：一起出现的标签之间会建立连边，每共现一次，这条边就更强一分。检索沿着这些连边游走，于是一个局部线索就能补全整个模式。巩固保留被反复强化的部分，遗忘修剪没被强化的部分 — *一起放电就连到一起；无人问津便随之消逝。*

**海马体（hippocampus）** 在这里也有一席之地 —— 它是工作记忆分区（`mem_hippocampus`）的名字：每条新记忆在巩固之前最先落入的收件箱。这个名字名副其实：在大脑中，海马体正是把新经验暂存、再逐步固化进长期皮层记忆的"门户"，而这个分区做的正是同一件事。

## 受大脑启发（不止于名字）

系统中的每一块都对应着认知神经科学已经研究了五十年的某个机制。我们的目标不是对生物学的精确复刻 — 而是大脑早已解决了"该保留哪些记忆、何时巩固、如何凭只言片语唤回"这些问题。我们沿用它的答案。

| 大脑机制 | 大脑做了什么 | Hebb Mind 怎么做 |
|---|---|---|
| **尖波涟漪与记忆回放** [(Wilson & McNaughton, 1994; Buzsáki, 2015)](#致谢) | 慢波睡眠期间，海马体回放白天的经历，将其转录到新皮层。 | 每日 18:00 的巩固任务"回放"工作记忆收件箱，将每条记忆归类到分区、解决冲突、把标签写入知识图谱。 |
| **多重记忆系统** [(Tulving, 1972; Squire, 1992)](#致谢) | 情景记忆、语义记忆、程序记忆分布在不同的子系统中。 | 五种命名分区 — `episodic` / `semantic` / `preference` / `procedural` / `custom` — 设计参照 [CoALA](https://arxiv.org/abs/2309.02427) 认知架构。 |
| **遗忘曲线** [(Ebbinghaus, 1885)](#致谢) | 未经回顾的记忆按指数衰减；回顾会让曲线变平。 | TTL 公式：`base × (1 + log(访问次数)) × 重要度 × exp(-衰减率 × 天数)`。常用的记忆留下，被忽略的自然消退。 |
| **模式分离与模式补全** [(O'Reilly & McClelland, 1994)](#致谢) | DG 区分相似记忆，CA3 凭部分线索补全完整记忆。 | 混合检索同时运行向量相似度（分离）、关键词匹配、标签图谱游走（补全）— 三条路径，一个综合分数。 |

为什么这件事在工程上重要：一个**只追加**的系统永远解决不了矛盾；一个**永不遗忘**的系统会被自己的噪声淹没。大脑两边都解决了。我们也是。

## 为什么选择 Hebb Mind？（工程视角）

- **零外部服务** — `sqlite-vec` 存向量、NetworkX 存标签图谱、sentence-transformers 算 Embedding。无需 Postgres、Neo4j、Redis。详见 [存储后端](https://afx-team.github.io/hebb-mind/zh/advanced/storage-backends.html)。
- **诚实的遗忘** — 上面那条 Ebbinghaus 公式，通过周期性任务执行。详见 [动态遗忘](https://afx-team.github.io/hebb-mind/zh/concepts/forgetting.html)。
- **巩固时解决冲突** — 巩固代理不只是追加，会合并重复、覆盖过时事实。详见 [记忆巩固](https://afx-team.github.io/hebb-mind/zh/concepts/consolidation.html)。
- **Claude Code 即插即用** — 三行命令为 Claude Code 启用基于 hooks 的跨会话记忆；一行命令为 Codex 注入相同能力的 MCP 工具。详见 [Claude Code 集成](https://afx-team.github.io/hebb-mind/zh/guide/claude-code.html)。

## 基准测试

v0.1.1 在 [LoCoMo](https://github.com/snap-research/LoCoMo) 长对话基准上的单次结果：

| 指标 | 数值 |
|---|---|
| 准确率 | **37.6%**（187 / 497） |
| 平均时延 | 102 ms / 查询 |
| 最佳类别 | 对抗类 66.1% |
| 最弱类别 | 多跳推理 5.6% |

基于标签图谱的多跳推理是当前的明显短板。完整数据、方法学与分类细节见 [Benchmarks](https://afx-team.github.io/hebb-mind/zh/benchmarks.html)。这是一个仍在迭代中的结果 — 与 `mem0` / `zep` 的对照实验跟踪在 [#TBD]。

## 30 秒 Python SDK

<!-- requires v0.1.2 facade — see PR #N -->

```python
from hebb import HebbMind

mem = HebbMind()  # 使用 ~/.hebb/hebb.json

mem.add("用户偏好深色模式", tags=["preference", "ui"], importance=7.5)
mem.add("用户使用 VS Code 与 One Dark 主题", tags=["preference", "tools"])

for hit in mem.search("UI 偏好", top_k=5):
    print(hit.score, hit.content)
```

`HebbMind()` 门面封装了上述 REST 接口；当本地未运行守护进程时，会自动在进程内拉起一个服务实例。

## 安装方式

```bash
pip install -U hebb-mind               # pip
pip install -U hebb-mind[pg]           # 启用 PostgreSQL/pgvector
hebb cc install --scope user          # Claude Code：基于 hooks 的自动记忆
hebb codex install --scope user       # Codex：MCP 记忆工具
```

Docker、一键脚本、源码安装详见 [安装指南](https://afx-team.github.io/hebb-mind/zh/guide/installation.html)。

## 记忆回路

每天，按照大脑大致相同的顺序运行同样四个阶段：

| 阶段 | 大脑对应 | 在 Hebb Mind 里发生了什么 | 触发方式 |
|------|---------|---------------------------|---------|
| **编码** | 海马体 CA1 捕捉当下 | 新记忆进入工作记忆收件箱（`mem_hippocampus`） | API 写入 |
| **回放与巩固** | 慢波睡眠中的尖波涟漪 | 巩固代理分类到分区、解决冲突、把标签写入知识图谱 | 每日 18:00 / 手动 |
| **检索** | CA3 的模式补全 | 三路混合搜索（向量 + 关键词 + 图谱），按时效 / 重要性 / 相关性综合评分 | API 搜索 |
| **遗忘** | 突触修剪 + 遗忘曲线 | 基于访问频率与重要性的动态 TTL — 被忽略的记忆自然消退 | 周期性 |

详细说明：[记忆生命周期](https://afx-team.github.io/hebb-mind/zh/concepts/memory-lifecycle.html) · [混合检索](https://afx-team.github.io/hebb-mind/zh/concepts/hybrid-search.html) · [架构图](https://afx-team.github.io/hebb-mind/zh/#架构)

## 横向对比

简洁版本；完整对比表见 [文档站](https://afx-team.github.io/hebb-mind/zh/#为什么选-hebb-mind)。

| 特性 | Mem0 | Letta | Zep | **Hebb Mind** |
|---|---|---|---|---|
| 自托管 Web UI | 仅云端（[相关讨论](https://github.com/mem0ai/mem0/discussions/3599)） | 仅云端 | 仅云端 | **内置 SPA** |
| 知识图谱 | 可插拔（[v3 已移除](https://docs.mem0.ai/migration/oss-v2-to-v3)） | 无 | 有（Graphiti） | 标签图谱（NetworkX） |
| 记忆巩固 | 仅追加 | Sleeptime Agent | 矛盾解决 | **自动 + 冲突解决** |
| 遗忘 / 衰减 | 无 | 无 | 时序失效 | **动态 TTL** |
| 零配置本地部署 | 需 API Key | 需 API Key + DB | 需 Postgres + Neo4j | **SQLite + 本地嵌入** |

## 配置

所有配置统一在 `hebb.json` 中管理。常用命令：

```bash
hebb config list
hebb config set llm_model openai/gpt-4o-mini
hebb config set storage_type postgresql
hebb config set pg_url postgresql://user:pass@localhost/hebb
```

完整字段参考 [配置指南](https://afx-team.github.io/hebb-mind/zh/guide/configuration.html)。

## API

服务启动后访问 `http://localhost:8321/docs` 查看完整 REST 文档。主要端点：

| 方法 | 端点 | 说明 |
|------|------|------|
| `POST` | `/api/v1/memories` | 写入记忆 |
| `POST` | `/api/v1/search` | 混合搜索 |
| `POST` | `/api/v1/admin/consolidate` | 立即触发巩固（需配置 `llm_api_key`） |
| `GET`  | `/api/v1/graph/tags` | 列出知识图谱标签 |
| `GET`  | `/api/v1/graph/neighbors/{tag}?depth=2` | 沿标签图谱游走 |

## 贡献

环境搭建：`pip install -e ".[dev]" && pytest tests/ -v`。详见 [CONTRIBUTING.md](CONTRIBUTING.md)。

## 致谢

**认知神经科学。** Ebbinghaus, H. (1885). *Über das Gedächtnis*. · **Hebb, D. O. (1949). *The Organization of Behavior*. Wiley** —项目的命名来源，"fire together, wire together" 背后的赫布假说。 · Tulving, E. (1972). Episodic and semantic memory. · Squire, L. R. (1992). Memory and the hippocampus: a synthesis from findings with rats, monkeys, and humans. *Psychological Review*, 99(2). · O'Reilly, R. C., & McClelland, J. L. (1994). Hippocampal conjunctive encoding, storage, and recall. *Hippocampus*, 4(6). · Wilson, M. A., & McNaughton, B. L. (1994). Reactivation of hippocampal ensemble memories during sleep. *Science*, 265(5172). · Tulving, E. (2002). Episodic memory: from mind to brain. *Annual Review of Psychology*, 53. · Buzsáki, G. (2015). Hippocampal sharp wave-ripple. *Hippocampus*, 25(10).

**AI 记忆系统。** [Generative Agents](https://arxiv.org/abs/2304.03442)（评分模型）· [MemGPT / Letta](https://arxiv.org/abs/2310.08560)（Agent 驱动的记忆管理）· [CoALA](https://arxiv.org/abs/2309.02427)（分区分类法）· [Graphiti](https://github.com/getzep/graphiti)（时序知识图谱）。研究笔记见 [`reports/papers/`](reports/papers/)。

> *"记忆是灵魂的书记官。" — 亚里士多德*
> 大脑早已用亿万年解决了这个问题。我们只是在把那条回路移植过来。

## 许可证

[MIT License](LICENSE)
