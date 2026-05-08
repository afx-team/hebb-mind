<p align="center">
  <h1 align="center"><a href="https://afx-team.github.io/hippocampus/zh/">海马体 Hippocampus</a></h1>
  <p align="center">受神经科学启发的 AI Agent 记忆框架</p>
  <p align="center"><a href="https://afx-team.github.io/hippocampus/zh/">📖 文档</a> · <a href="README.md">English</a> | <a href="README_ZH.md">中文</a></p>
</p>

<p align="center">
  <a href="https://afx-team.github.io/hippocampus/zh/"><img src="https://img.shields.io/badge/docs-afx--team.github.io-blue" alt="Documentation"></a>
  <a href="https://github.com/afx-team/hippocampus/actions"><img src="https://github.com/afx-team/hippocampus/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="https://pypi.org/project/afx-hippocampus/"><img src="https://img.shields.io/pypi/v/afx-hippocampus" alt="PyPI"></a>
  <a href="https://github.com/afx-team/hippocampus/blob/main/LICENSE"><img src="https://img.shields.io/badge/license-MIT-blue" alt="License"></a>
  <img src="https://img.shields.io/pypi/pyversions/afx-hippocampus" alt="Python">
</p>

---

Hippocampus 为你的 AI Agent 提供**类脑记忆系统**。正如人类大脑中的海马体将短期经验巩固为长期知识，本框架能自动组织、排序和遗忘记忆，让你的 Agent 始终保持敏锐。

## 目录

- [背景与动机](#背景与动机)
- [特性](#特性)
- [快速开始](#快速开始)
- [安装说明](#安装说明)
- [使用方法](#使用方法)
- [API 文档](#api-文档)
- [配置](#配置)
- [支持的模型](#支持的模型)
- [贡献指南](#贡献指南)
- [路线图](#路线图)
- [致谢](#致谢)
- [许可证](#许可证)

## 背景与动机

当前的 AI Agent 将每次对话视为无状态——每次会话后遗忘一切。虽然已有记忆解决方案，但都存在明显局限：

- **Mem0** 仅添加记忆，从不巩固或解决冲突
- **Letta** 需要独立的"睡眠代理"和外部数据库
- **Zep** 依赖 PostgreSQL + Neo4j，部署复杂

Hippocampus 借鉴神经科学，通过**零配置、自动化的记忆生命周期**解决这些问题。人类海马体不仅存储记忆——它还分类、巩固和修剪记忆。本框架将同样的智能带给 AI Agent。

| 特性 | Mem0 | Letta | Zep | **Hippocampus** |
|------|------|-------|-----|-----------------|
| 多模型支持 | Yes | Yes | Yes | 通过 [LiteLLM](https://github.com/BerriAI/litellm) |
| 知识图谱 | Partial | No | Yes | 基于标签 |
| Web 管理界面 | Yes | Cloud only | Cloud only | 内置 SPA |
| [MCP](https://modelcontextprotocol.io/) Server | Yes | Consumer only | Yes | 内置，自动启动 |
| 记忆巩固 | 仅添加 | Sleeptime Agent | 冲突解决 | **自动 + 冲突解决** |
| 遗忘/衰减 | No | No | 时间失效 | **动态 TTL** |
| 零配置部署 | API key required | API key + DB | Postgres + Neo4j | **SQLite + 本地嵌入** |

## 特性

- **类脑记忆分区** — 语义、情景、偏好、程序性和自定义分区，基于认知科学（[CoALA 框架](https://arxiv.org/abs/2309.02427)）
- **自动巩固** — Agentic RAG 管道自动分类、解决冲突、提取标签到知识图谱
- **动态遗忘** — 基于 TTL 的衰减：常用记忆存活，被忽略的自然消失
- **混合检索** — 三路搜索（向量 + 关键词 + 图谱），结合时效/重要性/相关性评分
- **零配置设置** — SQLite + 本地嵌入，无需外部服务
- **多模型支持** — 通过 LiteLLM 支持 OpenAI、Anthropic、通义千问、GLM、Kimi 等 100+ 提供商
- **内置 Web 控制台** — 记忆增删改查、搜索和图谱可视化
- **MCP Server** — 原生集成 Claude Code 及其他 MCP 兼容客户端
- **Claude Code Hooks** — 跨会话自动记忆：每轮对话自动写入，会话开始时自动召回

## 快速开始

```bash
pip install afx-hippocampus      # 安装
hippocampus init                  # 初始化（创建 hippocampus.json + SQLite 数据库）
hippocampus config set llm_api_key sk-your-key-here  # 配置 LLM 密钥
hippocampus start                 # 启动服务 → http://localhost:8321/
```

打开 http://localhost:8321/ 使用 **Web 管理控制台**，或访问 http://localhost:8321/docs 查看 API 文档。

## 安装说明

### pip（推荐）

```bash
pip install afx-hippocampus
```

### Claude Code（自动记忆）

让 Claude Code 拥有跨会话持久记忆 — 三条命令：

```bash
pip install afx-hippocampus
hippocampus init
hippocampus cc install
```

重启 Claude Code 即可。Hippocampus 会自动在会话开始时召回跨会话记忆，每条用户消息自动写入记忆，会话结束时触发巩固。

详见 [Claude Code 集成](https://afx-team.github.io/hippocampus/zh/advanced/claude-code.html)。

### Docker 部署

```bash
git clone https://github.com/afx-team/hippocampus.git && cd hippocampus
docker compose -f docker/docker-compose.yml up
```

### 一键安装

```bash
curl -fsSL https://raw.githubusercontent.com/afx-team/hippocampus/main/scripts/install.sh | sh

# 交互模式（选择 PostgreSQL 后端等）
curl -fsSL https://raw.githubusercontent.com/afx-team/hippocampus/main/scripts/install.sh | sh -s -- --interactive
```

### PostgreSQL 后端（生产环境）

```bash
pip install afx-hippocampus[pg]
hippocampus config set storage_type postgresql
hippocampus config set pg_url postgresql://user:pass@localhost/hippocampus
```

## 使用方法

### 存储和搜索记忆

```bash
# 存储记忆
curl -X POST http://localhost:8321/api/v1/memories \
  -H "Content-Type: application/json" \
  -d '{"content": "用户偏好暗色模式", "tags": ["preference", "ui"], "importance_score": 7.5}'

# 搜索记忆
curl -X POST http://localhost:8321/api/v1/search \
  -H "Content-Type: application/json" \
  -d '{"query": "UI偏好设置", "top_k": 5}'

# 手动触发巩固
curl -X POST http://localhost:8321/api/v1/admin/consolidate

# 探索知识图谱
curl http://localhost:8321/api/v1/graph/tags
curl http://localhost:8321/api/v1/graph/neighbors/python?depth=2
```

### 工作原理

记忆经历四个阶段 — 模拟人类海马体将短期经验巩固为长期知识的过程：

| 阶段 | 发生了什么 | 触发方式 |
|------|-----------|---------|
| **写入** | 新记忆进入工作记忆收件箱 (`mem_hippocampus`) | API 写入 |
| **巩固** | 代理分类到分区、解决冲突、提取标签 → 知识图谱 | 周期性 / 手动 |
| **检索** | 三路混合搜索（向量 + 关键词 + 图谱），结合时效/重要性/相关性评分 | API 搜索 |
| **遗忘** | 动态 TTL：`base × (1 + log(访问次数)) × 重要度 × exp(-衰减率 × 天数)` — 常用记忆存活，被忽略的自然消失 | 周期性 |

> 详细说明：[记忆生命周期](https://afx-team.github.io/hippocampus/zh/concepts/memory-lifecycle.html) · [记忆巩固](https://afx-team.github.io/hippocampus/zh/concepts/consolidation.html) · [混合检索](https://afx-team.github.io/hippocampus/zh/concepts/hybrid-search.html) · [动态遗忘](https://afx-team.github.io/hippocampus/zh/concepts/forgetting.html)

### 架构

```mermaid
flowchart TB
    subgraph Interface["接口层"]
        direction LR
        A1["REST API"]
        A2["MCP Server"]
        A3["CLI"]
        A4["Web Console"]
    end

    subgraph Core["Hippocampus 核心"]
        B1["工作记忆收件箱"]
        B2["巩固代理"]
        B3["回忆代理 · Agentic RAG"]
        B4["调度器 · APScheduler"]
    end

    subgraph Engine["处理引擎"]
        direction LR
        C1["混合检索\n向量 · 全文 · 图谱"]
        C2["知识图谱\n标签图谱 · NetworkX"]
        C3["评分引擎\n时效性 · 重要性 · 相关性"]
        C4["动态遗忘\n艾宾浩斯 TTL 衰减"]
    end

    subgraph Infra["基础设施"]
        direction LR
        D1["存储\nSQLite + sqlite-vec\nPostgreSQL + pgvector"]
        D2["嵌入\n本地 · sentence-transformers\nAPI · LiteLLM"]
        D3["LLM\n100+ 提供商\nvia LiteLLM"]
    end

    subgraph Parts["记忆分区"]
        direction LR
        E1["语义"]
        E2["情景"]
        E3["偏好"]
        E4["程序性"]
        E5["自定义"]
    end

    Interface --> Core
    Core --> Engine
    Engine --> Infra
    Infra --> Parts
```

## API 文档

Hippocampus 提供 RESTful API 用于记忆管理：

- **交互式文档**：http://localhost:8321/docs（Swagger UI）
- **完整 API 参考**：[API 文档](https://afx-team.github.io/hippocampus/api/)

主要端点：

| 方法 | 端点 | 说明 |
|------|------|------|
| `POST` | `/api/v1/memories` | 存储新记忆 |
| `GET` | `/api/v1/memories/{id}` | 按 ID 获取记忆 |
| `DELETE` | `/api/v1/memories/{id}` | 删除记忆 |
| `POST` | `/api/v1/search` | 混合搜索 |
| `POST` | `/api/v1/admin/consolidate` | 触发巩固 |
| `GET` | `/api/v1/graph/tags` | 列出知识图谱标签 |
| `GET` | `/api/v1/graph/neighbors/{tag}` | 探索标签关系 |

## 配置

所有配置统一在 **`hippocampus.json`** 文件中管理，不需要环境变量。

```bash
hippocampus config list                    # 查看所有配置
hippocampus config set llm_model openai/gpt-4o  # 切换模型
hippocampus config set llm_base_url https://dashscope.aliyuncs.com/compatible-mode/v1  # 通义千问/GLM/Kimi
```

| 字段 | 默认值 | 说明 |
|------|--------|------|
| `llm_model` | `openai/gpt-4o-mini` | LLM 模型标识（通过 [LiteLLM](https://github.com/BerriAI/litellm)）|
| `llm_api_key` | `null` | LLM API 密钥（巩固功能必需）|
| `llm_base_url` | `null` | 自定义 LLM API 端点（用于通义千问/GLM/Kimi）|
| `storage_type` | `sqlite` | `sqlite` 或 `postgresql` |
| `embedding_enabled` | `true` | 设为 `false` 禁用向量搜索 |
| `port` | `8321` | 服务端口 |
| `consolidation_time` | `18:00` | 每日巩固时间（`HH:MM`） |
| `base_ttl_hours` | `168` | 基础记忆 TTL |

> 完整配置参考：[配置指南](https://afx-team.github.io/hippocampus/zh/guide/configuration.html)

## 支持的模型

通过 [LiteLLM](https://github.com/BerriAI/litellm)，Hippocampus 支持所有主流 LLM 提供商：

| 提供商 | 模型示例 | 配置方式 |
|--------|----------|----------|
| OpenAI | `openai/gpt-4o-mini` | `llm_api_key` |
| Anthropic | `anthropic/claude-3-haiku-20240307` | `llm_api_key` |
| 通义千问 | `openai/qwen-plus` | `llm_api_key` + `llm_base_url` |
| 智谱 GLM | `openai/glm-4` | `llm_api_key` + `llm_base_url` |
| Kimi (Moonshot) | `openai/moonshot-v1-8k` | `llm_api_key` + `llm_base_url` |

## 贡献指南

欢迎贡献！详见 [CONTRIBUTING.md](CONTRIBUTING.md) 了解开发环境搭建、测试和 PR 流程。

### 开发环境搭建

```bash
git clone https://github.com/afx-team/hippocampus.git
cd hippocampus
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# 运行测试
pytest tests/ -v

# 代码检查
ruff check src/

# 类型检查
mypy src/hippocampus/
```

## 路线图

- [x] 5 个类脑记忆分区的核心模型
- [x] SQLite + sqlite-vec 存储后端
- [x] PostgreSQL + pgvector 存储后端
- [x] 记忆巩固代理（Agentic RAG）
- [x] 指数衰减动态遗忘
- [x] 标签知识图谱
- [x] FastAPI REST API
- [x] CLI 工具 + Docker 部署
- [x] 内置 Web 管理控制台
- [x] 评估基准测试（LoCoMo、LongMemEval、ConvoMem、PersonaMem）
- [x] MCP Server 集成 Claude Code / OpenClaw
- [x] Claude Code Hooks — 跨会话自动记忆
- [ ] 多 Agent 共享记忆
- [ ] 情感标签与记忆重要性学习

## 致谢

本项目参考了以下研究：

- [Generative Agents](https://arxiv.org/abs/2304.03442) — 时效-重要性-相关性检索评分
- [MemGPT / Letta](https://arxiv.org/abs/2310.08560) — Agent 驱动的记忆管理
- [CoALA](https://arxiv.org/abs/2309.02427) — 情景/语义/程序性分类体系
- [Zep / Graphiti](https://github.com/getzep/graphiti) — 时序知识图谱

详见[研究笔记](https://github.com/afx-team/hippocampus/tree/main/repo_pages/papers/)了解详细调研。

## 许可证

[MIT License](LICENSE)
