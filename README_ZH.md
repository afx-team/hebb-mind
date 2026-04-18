<p align="center">
  <h1 align="center">Hippocampus 海马体</h1>
  <p align="center">受神经科学启发的 AI Agent 记忆框架</p>
  <p align="center"><a href="README.md">English</a> | <a href="README_ZH.md">中文</a></p>
</p>

<p align="center">
  <a href="https://github.com/afx-team/hippocampus/actions"><img src="https://github.com/afx-team/hippocampus/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="https://pypi.org/project/hippocampus-ai/"><img src="https://img.shields.io/pypi/v/hippocampus-ai" alt="PyPI"></a>
  <a href="https://github.com/afx-team/hippocampus/blob/main/LICENSE"><img src="https://img.shields.io/badge/license-Apache--2.0-blue" alt="License"></a>
  <img src="https://img.shields.io/pypi/pyversions/hippocampus-ai" alt="Python">
</p>

---

Hippocampus 为你的 AI Agent 提供**类脑记忆系统**。正如人类大脑中的海马体将短期经验巩固为长期知识，本框架能自动组织、排序和遗忘记忆，让你的 Agent 始终保持敏锐。

## 为什么选择 Hippocampus？

| 特性 | Mem0 | Letta | Zep | **Hippocampus** |
|------|------|-------|-----|-----------------|
| 记忆巩固 | - | - | - | 自动化 |
| 遗忘/衰减 | - | - | 隐式 | 动态 TTL 公式 |
| 标签知识图谱 | - | - | 部分 | 内置 |
| 零配置部署 | - | - | - | SQLite，一条命令 |
| 向量搜索可选 | - | - | - | 渐进式 |
| 多模型支持 (OpenAI/Claude/Qwen/GLM/Kimi) | 部分 | 部分 | 部分 | 通过 LiteLLM |

## 架构

```
          写入记忆
               |
               v
    +---------------------+
    |    HIPPOCAMPUS       |     工作记忆收件箱
    |    (mem_hippocampus) |     所有新记忆首先落入此处
    +---------------------+
               |
          巩固代理（周期性执行）
          - 召回相关记忆（Agentic RAG）
          - 分类到对应分区
          - 解决冲突
          - 提取标签 -> 知识图谱
               |
      +--------+--------+--------+--------+
      v        v        v        v        v
    语义     情景      偏好     程序性    自定义
   知识/事实  经历/事件 喜好/厌恶 技能/方法  你自己
                                          的分区
      +--------+--------+--------+--------+
               |
          遗忘任务（周期性执行）
          TTL = base * (1 + log(访问次数)) * 重要度 * exp(-衰减率 * 天数)
               |
               v
          过期记忆被清除
```

## 快速开始

```bash
# 安装（需要 Python >= 3.12）
pip install hippocampus-ai

# 初始化项目（创建 hippocampus.json + SQLite 数据库）
hippocampus init

# 配置 LLM API 密钥（记忆巩固功能必需）
hippocampus config set llm_api_key sk-your-key-here

# 启动服务
hippocampus start
```

打开 http://localhost:8321/ 使用 **Web 管理控制台**，或访问 http://localhost:8321/docs 查看 API 文档。

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

## API 使用

### 存储记忆

```bash
curl -X POST http://localhost:8321/api/v1/memories \
  -H "Content-Type: application/json" \
  -d '{
    "content": "用户偏好暗色模式和紧凑布局",
    "tags": ["preference", "ui"],
    "importance_score": 7.5
  }'
```

### 搜索记忆

```bash
curl -X POST http://localhost:8321/api/v1/search \
  -H "Content-Type: application/json" \
  -d '{"query": "UI偏好设置", "top_k": 5}'
```

### 管理分区

```bash
# 列出所有分区
curl http://localhost:8321/api/v1/partitions

# 创建自定义分区
curl -X POST http://localhost:8321/api/v1/partitions \
  -H "Content-Type: application/json" \
  -d '{"id": "mem_project", "name": "项目上下文", "description": "当前项目知识"}'
```

## Web 管理控制台

Hippocampus 内置了一个 Web 管理界面，启动服务后访问 http://localhost:8321/ 即可使用：

- **仪表盘** — 系统统计、分区分布、快捷操作
- **记忆管理** — 浏览、新建、编辑、删除记忆，支持分区筛选和标签过滤
- **语义搜索** — 可调节 Relevance/Importance/Recency 三维权重
- **分区管理** — 创建/启停/删除记忆分区
- **知识图谱** — 力导向图可视化标签关系
- **设置** — 在线编辑 hippocampus.json 配置，即时保存

## 配置说明

所有配置统一在 **`hippocampus.json`** 文件中管理，不需要环境变量。

### CLI 配置管理

```bash
# 查看所有配置
hippocampus config list

# 查看单个配置
hippocampus config get llm_model

# 设置配置（立即写入 hippocampus.json）
hippocampus config set llm_api_key sk-your-key-here
hippocampus config set llm_model openai/gpt-4o
hippocampus config set llm_base_url https://dashscope.aliyuncs.com/compatible-mode/v1
hippocampus config set port 9000
```

也可以直接编辑 `hippocampus.json` 或使用 Web 控制台的 **Settings 页面**。

### hippocampus.json

```json
{
  "storage_type": "sqlite",
  "db_path": "hippocampus.db",
  "embedding_enabled": true,
  "embedding_model": "all-MiniLM-L6-v2",
  "llm_model": "openai/gpt-4o-mini",
  "llm_base_url": null,
  "llm_api_key": "sk-your-key-here",
  "host": "0.0.0.0",
  "port": 8321,
  "consolidation_interval_seconds": 3600,
  "forget_interval_seconds": 1800,
  "base_ttl_hours": 168,
  "decay_factor": 0.693,
  "weight_recency": 1.0,
  "weight_importance": 1.0,
  "weight_relevance": 1.0
}
```

### 主要配置项

| 字段 | 默认值 | 说明 |
|------|--------|------|
| `llm_model` | `openai/gpt-4o-mini` | LLM 模型标识（通过 LiteLLM）|
| `llm_api_key` | `null` | LLM API 密钥（巩固功能必需）|
| `llm_base_url` | `null` | 自定义 LLM API 端点（用于通义千问/GLM/Kimi）|
| `storage_type` | `sqlite` | `sqlite` 或 `postgresql` |
| `embedding_enabled` | `true` | 设为 `false` 禁用向量搜索 |
| `port` | `8321` | 服务端口 |
| `consolidation_interval_seconds` | `3600` | 巩固任务执行间隔（秒）|
| `base_ttl_hours` | `168` | 基础记忆 TTL（小时）|

### 存储后端

**SQLite（默认）** — 零配置，单文件，适合个人使用和开发。

```bash
hippocampus config set storage_type sqlite
```

**PostgreSQL + pgvector** — 生产级，连接池，原生向量类型。

```bash
pip install hippocampus-ai[pg]
hippocampus config set storage_type postgresql
hippocampus config set pg_url postgresql://user:pass@localhost/hippocampus
```

## 记忆生命周期

1. **写入** — 新记忆通过 API 写入 `mem_hippocampus`（工作记忆）分区
2. **巩固** — 周期性代理处理工作记忆：使用 Agentic RAG 召回相关历史记忆，LLM 分类到正确分区，检测并解决冲突，提取标签到知识图谱
3. **检索** — 搜索结合三个信号：**时效性**（指数衰减）、**重要性**（LLM 评分 0-10）、**相关性**（向量余弦相似度）
4. **遗忘** — 周期性任务为每条记忆计算动态 TTL，频繁访问的高重要性记忆存活更久，被忽略的记忆逐渐消失

## 支持的模型

通过 [LiteLLM](https://github.com/BerriAI/litellm)，Hippocampus 支持所有主流 LLM 提供商：

| 提供商 | 模型示例 | 环境变量 |
|--------|----------|----------|
| OpenAI | `openai/gpt-4o-mini` | `OPENAI_API_KEY` |
| Anthropic | `anthropic/claude-3-haiku-20240307` | `ANTHROPIC_API_KEY` |
| 通义千问 | `openai/qwen-plus` | `HIPPOCAMPUS_LLM_API_KEY` + `HIPPOCAMPUS_LLM_BASE_URL` |
| 智谱 GLM | `openai/glm-4` | `HIPPOCAMPUS_LLM_API_KEY` + `HIPPOCAMPUS_LLM_BASE_URL` |
| Kimi (Moonshot) | `openai/moonshot-v1-8k` | `HIPPOCAMPUS_LLM_API_KEY` + `HIPPOCAMPUS_LLM_BASE_URL` |

## 开发

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

详见 [CONTRIBUTING.md](CONTRIBUTING.md) 了解贡献指南。

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
- [ ] MCP Server 集成 Claude Code / OpenClaw
- [ ] 多 Agent 共享记忆
- [ ] 情感标签与记忆重要性学习

## 研究参考

本项目参考了以下研究：

- [Generative Agents](https://arxiv.org/abs/2304.03442) — 时效-重要性-相关性检索
- [MemGPT / Letta](https://arxiv.org/abs/2310.08560) — Agent 驱动的记忆管理
- [CoALA](https://arxiv.org/abs/2309.02427) — 情景/语义/程序性分类体系
- [Zep / Graphiti](https://github.com/getzep/graphiti) — 时序知识图谱

详见 [docs/papers/](docs/papers/) 了解详细调研笔记。

## 许可证

[Apache License 2.0](LICENSE)

---

<p align="center">
  由 <a href="https://github.com/afx-team">afx-team</a> 构建
</p>
