---
description: "用 pipx 或 pip 几秒装好 AI 智能体记忆框架 hebb-mind，内置 SQLite 免外部数据库，可选 PostgreSQL/pgvector 与 Docker，一键启动后台服务、Web 控制台与 MCP 工具。"
---

# 安装

## 安装（推荐：`pipx`）

```bash
pipx install hebb-mind
```

需要 **Python >= 3.10**。无需外部数据库 — SQLite 内置。

`pipx` 会把 `hebb-mind` 装到一个独立的虚拟环境里，并自动把 `hebb` / `hebb-mcp` 入口脚本软链到 `PATH` 上。它是 Python CLI 工具的现代标准做法，规避了 `pip install --user` 长期存在的两个坑：PATH 没更新、以及 Homebrew / Debian 系 Python 的 PEP 668 拦截。

### 如果还没装 `pipx`

根据系统挑一段执行，**然后新开一个终端**让 `PATH` 生效。

::: code-group

```bash [macOS]
brew install pipx
pipx ensurepath
```

```bash [Debian / Ubuntu]
sudo apt install pipx       # Ubuntu 23.04+ / Debian 12+
pipx ensurepath
```

```bash [Fedora]
sudo dnf install pipx
pipx ensurepath
```

```powershell [Windows]
python -m pip install --user pipx
python -m pipx ensurepath
```

```bash [通用方案]
python -m pip install --user pipx
python -m pipx ensurepath
```

:::

`ensurepath` 会修改你的 shell rc 或 Windows 用户 `PATH`，新开一个终端再执行 `pipx install hebb-mind`。

后续升级：`pipx upgrade hebb-mind`；干净卸载：`pipx uninstall hebb-mind`。

### 替代方案：虚拟环境 + `pip`

如果你已经习惯在 venv 里工作（或想自己管理一切）：

```bash
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -U hebb-mind           # `hebb` 自动在 venv 的 PATH 上
```

系统级 `sudo pip install` 在新版发行版上会被 PEP 668 拦截，`pipx` 是后续的官方推荐路径。

## Setup

```bash
hebb setup
```

在工作目录下生成 `hebb.json` 和 `hebb.db`，按系统语言选择一个**小**的默认 Embedding 模型，选择下载源，并在该模型尚未缓存时下载它。裸默认是 `all-MiniLM-L6-v2`（英文，~90MB）或 `intfloat/multilingual-e5-small`（多语言，~470MB）；需要高质量的 bge 模型（1–2GB）时加 `--profile best`。它**不会**启动后台服务。

默认工作目录是 `~/.hebb/`（全局回退）。如果你在一个已有、或将会有 `hebb.json` 的目录里运行 `hebb setup`，该目录就会成为工作目录。解析顺序：`$HEBB_HOME` → 最近的上级 `hebb.json` → `~/.hebb/`。运行 `hebb config get workspace` 查看解析出的位置。

## 验证

```bash
hebb --version
hebb model status
```

## 安装后台服务

```bash
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
pipx install 'hebb-mind[pg]'    # 或：pipx inject hebb-mind 'hebb-mind[pg]' --force
hebb config set storage_type postgresql
hebb config set pg_url postgresql://user:pass@localhost/hebb
```

详见 [存储后端](../advanced/storage-backends.md)。

## 下一步

- [配置](./configuration.md) — 完整配置项说明
- [Claude Code](./claude-code.md) — Claude Code 跨会话自动记忆
- [Codex](./codex.md) — Codex 自动记忆 hooks 与 MCP 工具
- [MCP 集成](./mcp-integration.md) — 在任意 MCP 客户端中使用 Hebb Mind
