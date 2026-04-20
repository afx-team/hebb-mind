<p align="center">
  <h1 align="center">Hippocampus 海马体</h1>
  <p align="center">受神经科学启发的 AI Agent 记忆框架</p>
  <p align="center"><a href="README.md">English</a> | <a href="README_ZH.md">中文</a></p>
</p>

<p align="center">
  <a href="https://github.com/afx-team/hippocampus/actions"><img src="https://github.com/afx-team/hippocampus/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="https://pypi.org/project/afx-hippocampus/"><img src="https://img.shields.io/pypi/v/afx-hippocampus" alt="PyPI"></a>
  <a href="https://github.com/afx-team/hippocampus/blob/main/LICENSE"><img src="https://img.shields.io/badge/license-Apache--2.0-blue" alt="License"></a>
  <img src="https://img.shields.io/pypi/pyversions/afx-hippocampus" alt="Python">
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

<div align="center">

<table>
<tr>
<td align="center" colspan="5" style="padding:4px 12px; background:#1a1a2e; border-radius:8px; color:#e0e0e0; font-weight:600;">
API · MCP · CLI
</td>
</tr>
<tr><td align="center" colspan="5" style="font-size:18px; color:#555;">▼</td></tr>
<tr>
<td align="center" colspan="5" style="padding:8px 16px; background:#16213e; border-radius:8px;">
<b style="color:#00d2ff; font-size:15px;">HIPPOCAMPUS</b><br/>
<span style="color:#888; font-size:12px;">工作记忆收件箱</span>
</td>
</tr>
<tr><td align="center" colspan="5" style="font-size:14px; color:#555;">▼&nbsp; 巩固代理 <span style="color:#666; font-size:11px;">(Agentic RAG · 分类 · 冲突解决 · 标签提取)</span></td></tr>
<tr>
<td align="center" style="padding:6px 10px; background:#1b4332; border-radius:6px; min-width:90px;">
<b style="color:#52b788;">语义</b><br/><span style="color:#888; font-size:11px;">知识/事实</span>
</td>
<td align="center" style="padding:6px 10px; background:#3c1642; border-radius:6px; min-width:90px;">
<b style="color:#c77dff;">情景</b><br/><span style="color:#888; font-size:11px;">经历/事件</span>
</td>
<td align="center" style="padding:6px 10px; background:#6b2d5b; border-radius:6px; min-width:90px;">
<b style="color:#ff6b6b;">偏好</b><br/><span style="color:#888; font-size:11px;">喜好/厌恶</span>
</td>
<td align="center" style="padding:6px 10px; background:#2d3a4a; border-radius:6px; min-width:90px;">
<b style="color:#4ecdc4;">程序性</b><br/><span style="color:#888; font-size:11px;">技能/方法</span>
</td>
<td align="center" style="padding:6px 10px; background:#3d3d3d; border-radius:6px; min-width:90px;">
<b style="color:#aaa;">自定义</b><br/><span style="color:#888; font-size:11px;">你的分区</span>
</td>
</tr>
<tr><td align="center" colspan="5" style="font-size:14px; padding-top:4px;">
<span style="color:#555;">▼</span>&nbsp;
<span style="color:#666; font-size:12px;">混合检索</span>
<span style="color:#555;">&nbsp;⟷&nbsp;</span>
<span style="color:#666; font-size:12px;">知识图谱</span>
<span style="color:#555;">&nbsp;⟷&nbsp;</span>
<span style="color:#666; font-size:12px;">动态遗忘 (TTL)</span>
</td></tr>
</table>

</div>

## 快速开始

```bash
pip install afx-hippocampus      # 安装
hippocampus init                  # 初始化（创建 hippocampus.json + SQLite 数据库）
hippocampus config set llm_api_key sk-your-key-here  # 配置 LLM 密钥
hippocampus start                 # 启动服务 → http://localhost:8321/
```

打开 http://localhost:8321/ 使用 **Web 管理控制台**，或访问 http://localhost:8321/docs 查看 API 文档。

<details>
<summary><b>其他安装方式</b></summary>

**Docker 部署：**

```bash
git clone https://github.com/afx-team/hippocampus.git && cd hippocampus
docker compose -f docker/docker-compose.yml up
```

**一键安装：**

```bash
curl -fsSL https://raw.githubusercontent.com/afx-team/hippocampus/main/scripts/install.sh | sh

# 交互模式（选择 PostgreSQL 后端等）
curl -fsSL https://raw.githubusercontent.com/afx-team/hippocampus/main/scripts/install.sh | sh -s -- --interactive
```
</details>

<details>
<summary><b>30 秒体验</b></summary>

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
</details>

## 工作原理

记忆经历四个阶段 — 模拟人类海马体将短期经验巩固为长期知识的过程：

| 阶段 | 发生了什么 | 触发方式 |
|------|-----------|---------|
| **写入** | 新记忆进入工作记忆收件箱 (`mem_hippocampus`) | API 写入 |
| **巩固** | 代理分类到分区、解决冲突、提取标签 → 知识图谱 | 周期性 / 手动 |
| **检索** | 三路混合搜索（向量 + 关键词 + 图谱），结合时效/重要性/相关性评分 | API 搜索 |
| **遗忘** | 动态 TTL：`base × (1 + log(访问次数)) × 重要度 × exp(-衰减率 × 天数)` — 常用记忆存活，被忽略的自然消失 | 周期性 |

> 详细说明：[记忆生命周期](docs/zh/concepts/memory-lifecycle.md) · [记忆巩固](docs/zh/concepts/consolidation.md) · [混合检索](docs/zh/concepts/hybrid-search.md) · [动态遗忘](docs/zh/concepts/forgetting.md)

## 配置

所有配置统一在 **`hippocampus.json`** 文件中管理，不需要环境变量。

```bash
hippocampus config list                    # 查看所有配置
hippocampus config set llm_model openai/gpt-4o  # 切换模型
hippocampus config set llm_base_url https://dashscope.aliyuncs.com/compatible-mode/v1  # 通义千问/GLM/Kimi
```

| 字段 | 默认值 | 说明 |
|------|--------|------|
| `llm_model` | `openai/gpt-4o-mini` | LLM 模型标识（通过 LiteLLM）|
| `llm_api_key` | `null` | LLM API 密钥（巩固功能必需）|
| `llm_base_url` | `null` | 自定义 LLM API 端点（用于通义千问/GLM/Kimi）|
| `storage_type` | `sqlite` | `sqlite` 或 `postgresql` |
| `embedding_enabled` | `true` | 设为 `false` 禁用向量搜索 |
| `port` | `8321` | 服务端口 |
| `consolidation_interval_seconds` | `3600` | 巩固任务执行间隔 |
| `base_ttl_hours` | `168` | 基础记忆 TTL |

<details>
<summary><b>存储后端</b></summary>

**SQLite（默认）** — 零配置，单文件，适合个人使用和开发。

**PostgreSQL + pgvector** — 生产级，连接池，原生向量类型。

```bash
pip install afx-hippocampus[pg]
hippocampus config set storage_type postgresql
hippocampus config set pg_url postgresql://user:pass@localhost/hippocampus
```
</details>

> 完整配置参考：[配置指南](docs/zh/guide/configuration.md)

## 支持的模型

通过 [LiteLLM](https://github.com/BerriAI/litellm)，Hippocampus 支持所有主流 LLM 提供商：

| 提供商 | 模型示例 | 配置方式 |
|--------|----------|----------|
| OpenAI | `openai/gpt-4o-mini` | `llm_api_key` |
| Anthropic | `anthropic/claude-3-haiku-20240307` | `llm_api_key` |
| 通义千问 | `openai/qwen-plus` | `llm_api_key` + `llm_base_url` |
| 智谱 GLM | `openai/glm-4` | `llm_api_key` + `llm_base_url` |
| Kimi (Moonshot) | `openai/moonshot-v1-8k` | `llm_api_key` + `llm_base_url` |

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
- [x] MCP Server 集成 Claude Code / OpenClaw
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