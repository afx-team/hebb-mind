---
description: "60 秒上手 AI Agent 记忆框架：pipx 安装、无需 API Key，本地离线运行向量 + 关键词混合检索，再按需开启 LLM 巩固与 MCP 编辑器集成。"
---

# 快速开始

两条路径。60 秒路径**不需要 API Key**；5 分钟路径额外开启 LLM 巩固。

## 路径 A — 60 秒，无需 API Key

写入和混合检索完全离线运行（基于内置的本地 Embedding 模型）。

### 1. 安装

```bash
pipx install hebb-mind
```

需要 **Python >= 3.10**。SQLite 内置，无需外部数据库。

**还没装 `pipx`？** 它是 Python CLI 工具的标准安装器：隔离 venv、自动配置 PATH、兼容 PEP 668。一次性装好就行：

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

新开一个终端让 `PATH` 生效，再回来跑 `pipx install hebb-mind`。

更习惯 `pip`？也可以：`python -m venv .venv && source .venv/bin/activate && pip install -U hebb-mind` —— `hebb` 自动落在 venv 的 `PATH` 上。

### 2. Setup

```bash
hebb setup
```

在工作目录下生成 `hebb.json` 与 `hebb.db`，根据系统语言选择 Embedding 模型，并在本地尚无缓存时下载。**首次运行会下载一个小模型**（英文约 90MB / 多语言约 470MB），仅当模型尚未缓存时才下载；已缓存则直接复用，不会重复下载。英文 / `--profile fast` 的小模型路径通常在 60 秒左右完成，多语言模型略久。`language`、`region`、`profile` 是相互独立的参数：

```bash
hebb setup --language en --region cn      # 英文小模型（~90MB），国内镜像
hebb setup --language zh --region global  # 多语言小模型（~470MB），HuggingFace 官方源
hebb setup --profile fast                 # 最小模型 all-MiniLM-L6-v2（~90MB）
```

需要更高质量的检索时，再用高质量档（仅在需要时下载，1–2GB 以上）：

```bash
hebb setup --profile best                 # 英文 bge-large-en-v1.5 / 中文多语言 bge-m3
```

### 3. 安装后台服务

```bash
hebb service install
```

该命令把 Hebb Mind 注册为系统级服务并立即启动：macOS 用 launchd，Linux 用 systemd，Windows 用任务计划程序。默认是**用户级**安装，不需要 `sudo` 或管理员权限；如需系统级常驻，请加 `--scope system`。

打开 <http://localhost:8321/> 进入 Web 控制台，或访问 <http://localhost:8321/docs> 查看 OpenAPI 页。运行 `hebb config get workspace` 可查看数据存放位置。

<!-- TODO(asset): 将 60 秒演示存为 repo_pages/public/quickstart-cast.gif，然后取消下面块的注释。 -->
<!--
<p align="center">
  <img src="/quickstart-cast.gif" alt="Asciinema 演示：60 秒完成安装、setup、启动、写入、检索" width="720">
</p>
-->

### 4. 写入与搜索

```bash
curl -X POST http://localhost:8321/api/v1/memories \
  -H 'Content-Type: application/json' \
  -d '{
    "content": "用户偏好深色模式与紧凑布局",
    "tags": ["preference", "ui"],
    "importance_score": 7.5
  }'

curl -X POST http://localhost:8321/api/v1/search \
  -H 'Content-Type: application/json' \
  -d '{"query": "UI 偏好", "top_k": 5}'
```

到这一步，向量 + 关键词 + 标签图谱的三路混合检索已完全在本地运行，无任何外部调用。

## 路径 B - 5 分钟，启用 LLM 巩固

巩固、冲突解决、标签提取需要 LLM。巩固的开关门槛是 `llm_model`：**未设置它时，相关接口会静默返回空结果**（详见 [故障排查](./troubleshooting.md#consolidate-返回-processed-0-或冲突一直没被解决)）。本地或代理模型只需模型名；托管厂商还需要额外配置 `llm_api_key`。

### 1. 配置 LLM

```bash
hebb config set llm_model openai/gpt-4o-mini
hebb config set llm_api_key sk-your-key      # 托管厂商需要
```

通过 [LiteLLM](https://github.com/BerriAI/litellm) 切换提供商：

```bash
# Anthropic
hebb config set llm_model anthropic/claude-3-haiku-20240307

# 通义千问 / GLM / Kimi（OpenAI 兼容端点）
hebb config set llm_base_url https://dashscope.aliyuncs.com/compatible-mode/v1
hebb config set llm_model openai/qwen-plus
```

### 2. 触发巩固

```bash
curl -X POST http://localhost:8321/api/v1/admin/consolidate
```

或等待每日 18:00 的定时任务。巩固期间提取的标签会写入知识图谱，可通过 `GET /api/v1/graph/tags` 查看。

## 30 秒 Python SDK

门面在**进程内**直接运行整套引擎（存储、Embedding、图谱、检索），不是 HTTP 客户端，也无需后台服务在运行。

```python
from hebb import HebbMind

mem = HebbMind()  # 进程内引擎；自动加载就近的 hebb.json（回退 ~/.hebb/hebb.json）

mem.add("用户偏好深色模式", tags=["preference", "ui"], importance=7.5)

for hit in mem.search("UI 偏好", top_k=5):
    print(hit.score, hit.memory.content)   # 命中文本在 hit.memory.content（不是顶层属性）
```

## 服务生命周期

Hebb Mind 统一以操作系统后台服务的方式运行，常用命令：

```bash
hebb service install     # 注册并启动（launchd / systemd / 任务计划程序）
hebb status      # 查看是否安装与是否运行
hebb service restart     # 原地重启
hebb service stop        # 停止但保留安装
hebb service uninstall   # 从系统中移除
```

所有 `service` 子命令都支持 `--scope user`（默认，无需权限提升）或 `--scope system`（需要 sudo / 管理员；系统级开机自启）。

Docker 部署见 [存储后端](./advanced/storage-backends.md#docker-deployment)。

## MCP 与编辑器集成

```bash
hebb claude-code install --scope user      # Claude Code：hooks 自动记忆
hebb codex install                         # Codex：MCP 记忆工具（仅全局）
codex mcp list                             # 验证
```

通用 MCP 客户端（Cursor 等）请填 `hebb-mcp` 的**绝对路径**（GUI 应用 / launchd 下 `PATH` 往往不含 pipx 的 bin 目录，裸命令会静默启动失败）。先用 `which hebb-mcp`（Windows：`where hebb-mcp`）查出路径：

```json
{
  "mcpServers": {
    "hebb": { "command": "/Users/you/.local/bin/hebb-mcp" }
  }
}
```

详见：[MCP 集成](./guide/mcp-integration.md) · [Claude Code 集成](./guide/claude-code.md) · [Codex 集成](./guide/codex.md)

## 下一步

- [配置](./guide/configuration.md) — 完整字段说明
- [记忆生命周期](./concepts/memory-lifecycle.md) — 系统核心机制
- [Benchmarks](./benchmarks/) — LoCoMo / LongMemEval 结果
- [API 文档](./api/memories.md) — 完整 API 参考
