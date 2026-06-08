<p align="center">
  <h1 align="center"><a href="https://afx-team.github.io/hebb-mind/zh/"><img src="logo.svg" width="40" height="40" alt="Hebb Mind logo" valign="middle"/> Hebb Mind</a></h1>
  <p align="center"><strong>一套受神经科学启发的 AI Agent 记忆框架 </strong></p>
  <p align="center"><em>编码、巩固、激活、遗忘</em></p>
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

Hebb Mind 给 AI Agent 装上一条受神经科学启发的记忆回路 —— **存储 → 激活 → 回放 → 巩固 → 遗忘**。`pipx install` 后一行命令即可在本地拉起 REST + MCP 端点：SQLite 做存储、sentence-transformers 做嵌入、NetworkX 维护标签图谱。**零外部服务**，只有想让巩固阶段"工作"时才需要 LLM Key。

与同类相比，**Hebb Mind 是一个二进制、一条生物学意义上的回路。**

<p align="center">
  <img src="repo_pages/public/architecture-zh.jpg" alt="Hebb Mind 架构 —— 接入层 · hebb CLI · 四阶段记忆回路与 LLM 驱动 7 步巩固 Agent · SQLite + pgvector" width="900">
</p>

## 快速开始

### 约 60 秒上手 — 不需要 API Key

写入和混合检索完全离线运行（基于本地 Embedding 模型）。

```bash
pipx install hebb-mind
hebb setup              # 根据系统语言自动下载一个小型 Embedding 模型
hebb service install    # 注册操作系统后台服务（launchd / systemd / 任务计划程序）
```

`hebb setup` 仅在模型尚未缓存时下载一个小型 Embedding 模型 —— 英文约 90MB
（`all-MiniLM-L6-v2`），多语言约 470MB（`intfloat/multilingual-e5-small`）。
"约 60 秒"指英文 / `--profile fast` 小模型路径；多语言模型下载体积更大。
想要高质量模型？用 `hebb setup --profile best` 拉取 BAAI `bge` 系列（1–2GB+）——
这是可选的高质量档位，默认不下载。

**还没装 `pipx`？** 它是 Python CLI 工具推荐的安装器：隔离 venv、自动配置 PATH、兼容 PEP 668。一次性装好就行：

```bash
# macOS（Homebrew）
brew install pipx && pipx ensurepath

# Linux — Debian / Ubuntu 23.04+
sudo apt install pipx && pipx ensurepath

# Linux — Fedora
sudo dnf install pipx && pipx ensurepath

# Windows / 其他装了 Python 3.10+ 的环境
python -m pip install --user pipx && python -m pipx ensurepath
```

然后**新开一个终端**让 `PATH` 生效，再回来跑 `pipx install hebb-mind`。

更习惯用 `pip`？也可以：`python -m venv .venv && source .venv/bin/activate && pip install -U hebb-mind` —— `hebb` 自动落在 venv 的 `PATH` 上。

Hebb Mind 统一以操作系统后台服务的方式运行 —— 不再需要单独的前台进程，也不再有 `start`/`stop` 命令需要记忆。默认是用户级安装，**不需要管理员权限**；如果需要系统级常驻，可加 `--scope system`。详见 `hebb service --help`。

另开一个终端：

```bash
curl -X POST http://localhost:8321/api/v1/memories \
  -H 'Content-Type: application/json' \
  -d '{"content": "用户偏好深色模式与紧凑布局", "tags": ["preference", "ui"]}'

curl -X POST http://localhost:8321/api/v1/search \
  -H 'Content-Type: application/json' \
  -d '{"query": "UI 偏好", "top_k": 5}'
```

打开 <http://localhost:8321/> 即可使用 Web 控制台。

<p align="center">
  <img src="repo_pages/public/web-console-hero.jpg" alt="Hebb Mind Web 控制台 — 分区记忆与标签图谱" width="760">
</p>

### 完整体验（5 分钟）— 启用 LLM 巩固

记忆巩固、冲突解决、标签提取需要一个 LLM 后端。开关由 `llm_model` 决定 —— 未设置前这些接口为 no-op（详见 [#consolidation-no-op](https://afx-team.github.io/hebb-mind/zh/troubleshooting.html)）。托管 provider 还需要 `llm_api_key`；本地模型（例如通过 `llm_base_url` 接入的 Ollama）则不需要。

```bash
hebb config set llm_model openai/gpt-4o-mini   # 必填 —— 启用巩固
hebb config set llm_api_key sk-...             # 托管 provider 需要
# 通过 LiteLLM 接入通义千问 / GLM / Kimi：
hebb config set llm_base_url https://dashscope.aliyuncs.com/compatible-mode/v1
```

手动触发巩固，或等待每日 18:00 的定时任务：

```bash
curl -X POST http://localhost:8321/api/v1/admin/consolidate
```

## 安装方式

```bash
pipx install hebb-mind                 # 推荐方式（隔离的 CLI 安装）
pipx install 'hebb-mind[pg]'           # 启用 PostgreSQL/pgvector
pipx upgrade hebb-mind                 # 后续升级
hebb claude-code install --scope user  # Claude Code：基于 hooks 的召回 + 回合写入
hebb codex install --scope user        # Codex：MCP 记忆工具
```

Docker、一键脚本、源码安装详见 [安装指南](https://afx-team.github.io/hebb-mind/zh/guide/installation.html)。

## 30 秒 Python SDK

```python
from hebb import HebbMind

mem = HebbMind()  # 按 cwd → $HEBB_HOME → ~/.hebb 顺序解析 hebb.json

mem.add("用户偏好深色模式", tags=["preference", "ui"], importance=7.5)
mem.add("用户使用 VS Code 与 One Dark 主题", tags=["preference", "tools"])

for hit in mem.search("UI 偏好", top_k=5):
    print(hit.score, hit.memory.content)
```

`HebbMind()` 门面在进程内直接运行记忆引擎（存储 + 嵌入 + 图谱 + 混合检索）—— 不启动 HTTP 服务，也无需守护进程。它复用了 REST 服务在启动时构建的同一套组件，只是去掉了网络层。

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
| `POST` | `/api/v1/admin/consolidate` | 立即触发巩固（需配置 `llm_model`） |
| `GET`  | `/api/v1/graph/tags` | 列出知识图谱标签 |
| `GET`  | `/api/v1/graph/neighbors/{tag}?depth=2` | 沿标签图谱游走 |

## 基准测试

**LoCoMo**（10 段多轮对话、共 1,986 题，1,978 道可评分），按 MemPalace 同口径的 session 级 Recall@10。

| 系统 | Embedding | 重排 | R@10 |
|---|---|---|---|
| **Hebb Mind v0.1.6** | bge-large-1024 | bge-reranker-base | **95.75%** |
| **Hebb Mind v0.1.6** | bge-large-1024 | — | **94.14%** |
| MemPalace hybrid | bge-large-1024 | — | 92.40% |
| **Hebb Mind v0.1.6** | MiniLM-384 | bge-reranker-base | **94.69%** |
| MemPalace hybrid | MiniLM-384 | — | 92.63% |
| **Hebb Mind v0.1.6** | MiniLM-384 | — | 91.41% |

同 embedding 档位下：不开重排时 bge-large 领先 +1.74 pp，开重排后 +3.35 pp；本地 cross-encoder 甚至把廉价的 MiniLM-384 抬到 94.69%，超过 MemPalace 调优后的 hybrid。端到端 QA（同一检索 + DeepSeek-V4-Pro judge，完整 1,978 题）：**77.1%**。

**LongMemEval**（500 题，LongMemEval-S）—— session 级 Recall@k（检索，与 MemPalace 同口径）以及端到端 QA（官方 reader + `get_anscheck_prompt` 判分，与 Zep / Mem0 可比）。

| 系统 | 检索 recall@10 | 端到端 QA | 作答 LLM |
|---|---|---|---|
| **Hebb Mind v0.1.6** | **99.4%** | **79.0%** | DeepSeek-V4-Pro（中立官方 prompt） |
| Zep | 95.5% | 71.2% | gpt-4o |
| Mem0 | 未公布 | ~85–94%¹ | gpt-4o（重度调优 prompt） |

检索 R@5 = **99.0%**，在相同的 MiniLM-384 embedding 上追平 MemPalace 最佳「hybrid + 重排」配置（99.4%），远高于其 raw 96.6%。Hebb 在每个检索深度都胜过 Zep（R@1 93.4% vs 75.9%），并在 QA 上以**未调优**的 reader prompt 领先（79.0% vs 71.2%）；与 Mem0 的差距来自 reader prompt 工程，而非记忆 —— Hebb 的检索才是更强的一层。<sup>¹ 随来源/设置而变。</sup>

**MemBench**（ACL 2025；11 类、所有 topic、共 11,996 题）—— 轮次级 Hit@5，对照数据集的 `target_step_id` 指针，与 MemPalace 同口径。Ground truth 是单选题，因此不用 LLM 判分（瞎猜也有 25%）。

| 类别 | Hebb Mind v0.1.6 Hit@5 | MemPalace Hit@5 | Δ |
|---|---|---|---|
| noisy | **79.4%** | 43.4% | +36.0 pp |
| post_processing | **90.3%** | 56.6% | +33.7 pp |
| conditional | **86.0%** | 57.3% | +28.7 pp |
| highlevel_rec | **89.6%** | 76.2% | +13.4 pp |
| **总体（11 类）** | **94.6%** | 80.3% | **+14.3 pp** |

MiniLM-384 + bge-reranker-base。Hebb 在简单类别上与 MemPalace 持平（±4 pp 以内），在全部四个困难类别上大幅领先 —— 干扰项、条件推理、后处理 —— 这些恰恰是「逐字存储 + embedding」检索会崩溃的地方；关键杠杆是本地 cross-encoder 重排。逐类别 k 曲线见文档站。

Hebb Mind 的评测直接调用与生产同一份 Claude Code hook 代码路径（`integrations/claude_code/{recall,stop}.py`）与 `/api/v1/search`，因此上表数字就是用户在生产环境里实际能拿到的数字。完整方法学、分类拆解、benchmark vs production 流水线差异的说明：[hebb-mind.github.io/benchmarks](https://afx-team.github.io/hebb-mind/benchmarks/)。

## 为什么叫 "Hebb Mind"？

1949 年，心理学家 **唐纳德·赫布**（Donald O. Hebb）提出了一条法则，后来被浓缩成一句话：

> **一起放电的神经元，会连到一起（neurons that fire together, wire together）。**

记忆不是"存放的地点"，而是"连接的模式"。共同出现的概念被物理地连成**细胞集群（cell assembly）**，激活其一部分就能唤回全部；重复会强化连接，弃用则任其消退。这条法则 — 赫布学习 — 很大程度影响了记忆系统研究、人工神经网络。

**Hebb Mind 正是跑在这条法则上。** 它的标签知识图谱本身就是一个细胞集群：一起出现的标签之间会建立连边，每共现一次这条边就更强一分。检索沿着连边游走，于是一个局部线索就能补全整个模式。巩固保留被反复强化的部分，遗忘修剪没被强化的部分 — *一起放电就连到一起；无人问津便随之消逝。*

**海马体（hippocampus）** 在这里也有一席之地 — 它是工作记忆分区（`mem_hippocampus`）的名字。在大脑中，海马体正是把新经验暂存、再逐步固化进长期皮层记忆的"门户"；1957 年代号 H.M. 的患者被双侧切除海马体后，再也无法形成新的长期记忆 [(Squire, 1992; Tulving, 2002)](#致谢) — 今天的 AI Agent 就是 H.M.，每一次对话都从零开始。Hebb Mind 要为你的 Agent 补上这条缺失的回路。

## 贡献

环境搭建：`pip install -e ".[dev]" && pytest tests/ -v`。详见 [CONTRIBUTING.md](CONTRIBUTING.md)。

## 致谢

**认知神经科学。** Ebbinghaus, H. (1885). *Über das Gedächtnis*. · **Hebb, D. O. (1949). *The Organization of Behavior*. Wiley** —项目的命名来源，"fire together, wire together" 背后的赫布假说。 · Tulving, E. (1972). Episodic and semantic memory. · Squire, L. R. (1992). Memory and the hippocampus: a synthesis from findings with rats, monkeys, and humans. *Psychological Review*, 99(2). · O'Reilly, R. C., & McClelland, J. L. (1994). Hippocampal conjunctive encoding, storage, and recall. *Hippocampus*, 4(6). · Wilson, M. A., & McNaughton, B. L. (1994). Reactivation of hippocampal ensemble memories during sleep. *Science*, 265(5172). · Tulving, E. (2002). Episodic memory: from mind to brain. *Annual Review of Psychology*, 53. · Buzsáki, G. (2015). Hippocampal sharp wave-ripple. *Hippocampus*, 25(10).

**AI 记忆系统。** [Generative Agents](https://arxiv.org/abs/2304.03442)（评分模型）· [MemGPT / Letta](https://arxiv.org/abs/2310.08560)（Agent 驱动的记忆管理）· [CoALA](https://arxiv.org/abs/2309.02427)（分区分类法）· [Graphiti](https://github.com/getzep/graphiti)（时序知识图谱）。研究笔记见 [`reports/papers/`](reports/papers/)。

> *"记忆是灵魂的书记官。" — 亚里士多德*
> 大脑早已用亿万年解决了这个问题。我们只是在把那条回路移植过来。

## 许可证

[MIT License](LICENSE)
