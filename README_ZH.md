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

Hebb Mind 给 AI Agent 装上一条受神经科学启发的记忆回路 —— **编码 → 回放 → 巩固 → 遗忘**。`pipx install` 后一行命令即可在本地拉起 REST + MCP 端点：SQLite 做存储、sentence-transformers 做嵌入、NetworkX 维护标签图谱。**零外部服务**，只有想让巩固阶段"工作"时才需要 LLM Key。

与同类相比：`mem0` 云优先、只追加；`letta` 需外部 DB + 独立 sleeptime agent；`zep` 依赖 Postgres + Neo4j。**Hebb Mind 是一个二进制、一条生物学意义上的回路。**

## 快速开始

### 60 秒上手 — 不需要 API Key

写入和混合检索完全离线运行（基于内置的本地 Embedding 模型）。

```bash
pipx install hebb-mind
hebb setup              # 根据系统语言选择 Embedding 模型
hebb service install    # 注册操作系统后台服务（launchd / systemd / 任务计划程序）
```

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

## 安装方式

```bash
pipx install hebb-mind                 # 推荐方式（隔离的 CLI 安装）
pipx install 'hebb-mind[pg]'           # 启用 PostgreSQL/pgvector
pipx upgrade hebb-mind                 # 后续升级
hebb claude-code install --scope user  # Claude Code：基于 hooks 的自动记忆
hebb codex install --scope user        # Codex：MCP 记忆工具
```

Docker、一键脚本、源码安装详见 [安装指南](https://afx-team.github.io/hebb-mind/zh/guide/installation.html)。

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

## 基准测试

LoCoMo（10 段多轮对话、共 1,986 题），按 MemPalace 同口径的 session 级 Recall@10。两组都基于完整的 1,978 道可评分题目（剔除 8 道 evidence 缺失/不可解析的 adversarial 题）。

| 系统 | Embedding | R@10 |
|---|---|---|
| **Hebb Mind v0.1.2** | bge-large-1024 | **93.3%** |
| MemPalace bge-large hybrid | bge-large-1024 | 92.4% |
| **Hebb Mind v0.1.2** | MiniLM-384 | **89.7%** |
| MemPalace hybrid v5 | MiniLM-384 | 88.9% |

同 embedding 档位下稳定领先 ~+0.9 pp。端到端 QA（同一检索 + Kimi-K2.5 judge with thinking，完整 1,978 题）：**76.0%** — 检索能找到正确 session 的概率约 90%，LLM 将其转化为正确答案的概率约 76%，这中间的差距来自 per-utterance 入库下的跨记忆综合成本。

Hebb Mind 的评测直接调用与生产同一份 Claude Code hook 代码路径（`integrations/claude_code/{write,stop}.py`）与 `/api/v1/search`，因此上表数字就是用户在生产环境里实际能拿到的数字。完整方法学、分类拆解、benchmark vs production 流水线差异的说明：[hebb-mind.github.io/benchmarks](https://afx-team.github.io/hebb-mind/benchmarks/)。

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
