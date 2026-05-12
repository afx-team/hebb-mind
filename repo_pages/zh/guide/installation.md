# 安装

## 安装

```bash
pip install -U afx-hippocampus
```

需要 **Python >= 3.10**。无需外部数据库 — SQLite 内置。

## Setup

```bash
hippocampus setup
```

在 `~/.hippocampus/`（默认工作目录）生成 `hippocampus.json` 和 `hippocampus.db`，选择默认 Embedding 模型、选择下载源并验证模型。它不会启动后台服务。

仅需离线/脚本化初始化时使用：

```bash
hippocampus init
```

## 验证

```bash
hippocampus --version
hippocampus model status
hippocampus start
```

打开 [http://localhost:8321/](http://localhost:8321/) 进入 Web 控制台，或 [http://localhost:8321/docs](http://localhost:8321/docs) 查看 API 文档。

## Docker

```bash
git clone https://github.com/afx-team/hippocampus.git && cd hippocampus
docker compose -f docker/docker-compose.yml up
```

## PostgreSQL 后端

生产环境推荐使用 PostgreSQL + pgvector：

```bash
pip install afx-hippocampus[pg]
hippocampus config set storage_type postgresql
hippocampus config set pg_url postgresql://user:pass@localhost/hippocampus
```

详见 [存储后端](../advanced/storage-backends.md)。

## 下一步

- [配置](./configuration.md) — 完整配置项说明
- [Claude Code](./claude-code.md) — Claude Code 跨会话自动记忆
- [Codex](./codex.md) — Codex MCP 记忆工具
- [MCP 集成](./mcp-integration.md) — 在任意 MCP 客户端中使用 hippocampus
