# 安装

## 安装

```bash
pip install --user -U hebb-mind
```

需要 **Python >= 3.10**。无需外部数据库 — SQLite 内置。

### PATH 一次性配置（仅 `pip install --user`）

macOS 默认**不会**把 Python 用户脚本目录加进 `PATH`。`pip install --user` 之后敲 `hebb` 会 `command not found`，要配一次。挑你的 shell：

```bash
# zsh（macOS 默认）
echo 'export PATH="$(python3 -m site --user-base)/bin:$PATH"' >> ~/.zshrc && source ~/.zshrc

# bash
echo 'export PATH="$(python3 -m site --user-base)/bin:$PATH"' >> ~/.bashrc && source ~/.bashrc

# fish
fish_add_path (python3 -m site --user-base)/bin
```

`python3 -m site --user-base` 打印 pip 实际写入脚本的位置（macOS 通常是 `~/Library/Python/3.x`，Linux 是 `~/.local`）。可以单独跑一下确认。

如果你**用虚拟环境**安装，可以跳过 PATH 配置：

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -U hebb-mind   # `hebb` 自动在 venv 的 PATH 上
```

或者系统级安装（多数环境需要 `sudo`）：

```bash
sudo pip install -U hebb-mind
```

## Setup

```bash
hebb setup
```

在 `~/.hebb/`（默认工作目录）生成 `hebb.json` 和 `hebb.db`，选择默认 Embedding 模型、选择下载源并验证模型。它不会启动后台服务。

## 验证

```bash
hebb --version
hebb model status
hebb service install
```

打开 [http://localhost:8321/](http://localhost:8321/) 进入 Web 控制台，或 [http://localhost:8321/docs](http://localhost:8321/docs) 查看 API 文档。

## Docker

```bash
git clone https://github.com/afx-team/hebb-mind.git && cd hebb-mind
docker compose -f docker/docker-compose.yml up
```

## PostgreSQL 后端

生产环境推荐使用 PostgreSQL + pgvector：

```bash
pip install hebb-mind[pg]
hebb config set storage_type postgresql
hebb config set pg_url postgresql://user:pass@localhost/hebb
```

详见 [存储后端](../advanced/storage-backends.md)。

## 下一步

- [配置](./configuration.md) — 完整配置项说明
- [Claude Code](./claude-code.md) — Claude Code 跨会话自动记忆
- [Codex](./codex.md) — Codex MCP 记忆工具
- [MCP 集成](./mcp-integration.md) — 在任意 MCP 客户端中使用 Hebb Mind
