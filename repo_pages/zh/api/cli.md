# CLI 命令参考

Hippocampus 提供了 `hippocampus` 命令行工具来管理服务和配置。

## 全局选项

```bash
hippocampus --version    # 显示版本号
hippocampus --help       # 显示帮助信息
```

## hippocampus init

初始化项目目录，创建配置文件和数据库。

```bash
hippocampus init [--dir PATH] [--force]
```

| 选项 | 说明 |
|------|------|
| `--dir PATH` | 初始化目录，默认为 `~/.hippocampus/` |
| `--force` | 覆盖已有配置，重建数据库 |

执行后会创建：

- `hippocampus.json` — 配置文件
- `hippocampus.db` — SQLite 数据库（含 5 个默认分区）
- `knowledge_graph.json` — 空的知识图谱

示例：

```bash
# 在默认工作目录 ~/.hippocampus/ 初始化
hippocampus init

# 指定目录
hippocampus init --dir /opt/hippocampus

# 强制重新初始化（会删除已有数据）
hippocampus init --force
```

## hippocampus start

启动 API 服务。

```bash
hippocampus start [--host HOST] [--port PORT] [--reload]
```

| 选项 | 说明 |
|------|------|
| `--host HOST` | 监听地址，覆盖配置文件中的 `host` |
| `--port PORT` | 监听端口，覆盖配置文件中的 `port` |
| `--reload` | 启用热重载（开发模式） |

示例：

```bash
# 使用默认配置启动
hippocampus start

# 指定端口
hippocampus start --port 9000

# 开发模式（代码修改后自动重启）
hippocampus start --reload
```

启动后会显示：

```
Hippocampus v0.1.0
  Server:    http://0.0.0.0:8321
  Docs:      http://0.0.0.0:8321/docs
  Workspace: ~/.hippocampus
  Model:     openai/gpt-4o-mini
  DB:        hippocampus.db
```

## hippocampus stop

停止正在运行的服务。

```bash
hippocampus stop [--url URL]
```

| 选项 | 说明 |
|------|------|
| `--url URL` | 服务地址，默认从配置文件推断 |

```bash
hippocampus stop
```

## hippocampus restart

重启服务（先停止再启动）。

```bash
hippocampus restart [--host HOST] [--port PORT] [--reload]
```

选项与 `start` 命令相同。

```bash
hippocampus restart
hippocampus restart --port 9000
```

## hippocampus status

检查服务运行状态。

```bash
hippocampus status [--url URL]
```

| 选项 | 说明 |
|------|------|
| `--url URL` | 服务地址，默认从配置文件推断 |

```bash
hippocampus status
```

输出示例：

```
Server is running (v0.1.0)

Scheduler Jobs
┌──────────────┬───────────────────────┐
│ Job          │ Next Run              │
├──────────────┼───────────────────────┤
│ consolidation│ 2026-04-17T11:00:00Z  │
│ forgetting   │ 2026-04-17T10:30:00Z  │
└──────────────┴───────────────────────┘
```

## hippocampus workspace

显示当前解析的工作目录。数据文件（`hippocampus.db`、`knowledge_graph.json`）存储在此目录中。

```bash
hippocampus workspace
```

输出示例：

```
Workspace: /home/user/.hippocampus
```

工作目录的解析优先级：`HIPPOCAMPUS_HOME` 环境变量 > 配置文件中的 `home` 字段 > 配置文件所在目录 > `~/.hippocampus/`。

## hippocampus config

管理 `hippocampus.json` 配置文件。

### config list

显示所有配置项及当前值：

```bash
hippocampus config list
```

敏感值（如 API 密钥）会自动脱敏显示。

### config get

获取单个配置值：

```bash
hippocampus config get llm_model
# 输出: llm_model = 'openai/gpt-4o-mini'
```

### config set

设置配置值：

```bash
hippocampus config set llm_api_key sk-xxx
hippocampus config set llm_model openai/gpt-4o
hippocampus config set port 8000
hippocampus config set embedding_enabled false
```

类型会自动转换：数字字符串转为数字，`true`/`false` 转为布尔值。

### config path

显示配置文件的完整路径：

```bash
hippocampus config path
# 输出: /home/user/project/hippocampus.json
```
