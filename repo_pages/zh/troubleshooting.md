---
description: "按「症状 → 原因 → 解决」排查 Hebb Mind 常见问题：consolidate 返回 0（未配置 LLM 模型）、8321 端口占用、SQLite database locked、Embedding 模型下载卡住、Web 控制台空白、Claude Code 里 MCP 服务起不来。"
---

# 故障排查

针对新用户最容易先撞上的问题，给出「症状 → 原因 → 解决」。如果这里没有对上你看到的现象，下一步首选诊断是 `hebb doctor`，概念性问题则可参考 [FAQ](./faq.md)。

---

## `consolidate` 返回 `processed: 0`（或冲突一直没被解决）

**症状。** 调用接口后拿回的全是 0：

```bash
curl -X POST http://localhost:8321/api/v1/admin/consolidate
# {"processed":0,"succeeded":0,"failed":0}
```

或者你能看到数据库里新记忆不断堆积，却没有任何合并、去重或打标签发生。

**原因。** 没有配置 LLM 模型。巩固、冲突解决、重要度打分、自动标签提取都要通过 [LiteLLM](https://github.com/BerriAI/litellm) 调用 LLM。没有设置 `llm_model` 时，巩固 worker 会静默跳过每一批 —— 向量检索和 CRUD 照常工作，但所有「智能」环节都不会运行。

**解决。** 巩固的开关门槛是 `llm_model`。本地或代理模型只需设置模型名；托管厂商还需要额外配置 `llm_api_key`：

```bash
hebb config set llm_model openai/gpt-4o-mini
# 托管厂商还需要 API Key
hebb config set llm_api_key sk-your-key-here
# 可选：自定义端点
hebb config set llm_base_url https://api.openai.com/v1
# 重新触发
curl -X POST http://localhost:8321/api/v1/admin/consolidate
```

可以用 `hebb doctor` 确认配置是否就绪 —— 一旦设置了 `llm_model`，它会显示 `LLM: [OK]`。完整厂商列表见 [配置](./guide/configuration.md)。

---

## `Port 8321 already in use`

**症状。** `hebb service install`（或 `hebb service restart`）日志里出现 `[Errno 48] Address already in use`（macOS/Linux）或 `error while attempting to bind on address`（Windows），服务随即退出。

**原因。** 另一个进程占用了 8321 端口。最常见的是服务管理器残留的上一个 Hebb Mind 实例，也可能是无关的其他服务。

**解决。** 先找出占用进程：

```bash
# macOS / Linux
lsof -i :8321
# 或
ss -tulpn | grep 8321

# Windows（PowerShell）
Get-NetTCPConnection -LocalPort 8321
```

然后要么干净地停掉旧服务，要么换一个端口：

```bash
hebb service stop                  # 如果占用的是我们自己的服务，先停掉
hebb config set port 8322          # 持久化修改端口
hebb service restart               # 让新端口生效
```

记得把所有 MCP / Claude Code 集成指向新端口，并更新 `hebb status` 的 `--url` 参数。

---

## `database is locked`

**症状。** 请求间歇性失败，报 `sqlite3.OperationalError: database is locked`，通常发生在并发写入时（例如多个 Claude Code 会话挂在同一个工作区上）。

**原因。** SQLite 对写入串行化。Hebb Mind 默认开启 WAL 模式，但密集并发写入或一个游离事务仍可能阻塞。

**解决。**

1. 确保只有一个 `hebb` 服务进程在操作该文件：

   ```bash
   ps aux | grep hebb
   hebb service stop
   ```

2. 确认 WAL 模式已开启（默认应当是）：

   ```bash
   sqlite3 ~/.hebb/hebb.db "PRAGMA journal_mode;"
   # 预期：wal
   ```

3. 如果你需要从多个进程承载高写入 QPS，请切换到 PostgreSQL：

   ```bash
   hebb config set storage_type postgresql
   hebb config set pg_url "postgresql://user:pass@host:5432/hebb"
   ```

   迁移说明见 [存储后端](./advanced/storage-backends.md)。

---

## 首次启动卡住（几分钟没有输出）

**症状。** `hebb setup` 或 `hebb service install` 看起来卡死了，没有进度也没有报错。

**原因。** 正在从 HuggingFace 下载 Embedding 模型。默认 profile 下载的是小模型（英文约 90MB、多语言约 470MB），在普通家庭网络下通常很快；但如果你用 `hebb setup --profile best` 选择了高质量的 bge 模型（`BAAI/bge-large-en-v1.5` / `BAAI/bge-m3`，1–2GB 以上），在家用宽带上要 3–5 分钟，慢链路或公司代理下可能 15 分钟以上。进度条由 `huggingface_hub` 提供，当 stdout 不是 TTY 时有时会被吞掉。

**解决。**

1. 检查模型缓存，确认确实在下载：

   ```bash
   ls -lah ~/.cache/huggingface/hub/
   ```

   你应当看到一个 `models--*` 目录，且体积在增长。

2. 如果你在中国大陆或处于受限网络环境，把下载源切换到 [hf-mirror.com](https://hf-mirror.com) 镜像：

   ```bash
   hebb setup --region cn
   ```

   这会在下载前设置 `HF_ENDPOINT=https://hf-mirror.com`。

3. 如果上一次下载中途崩溃，清掉残留缓存后重试：

   ```bash
   rm -rf ~/.cache/huggingface/hub/models--BAAI--bge-m3
   hebb model prefetch
   ```

模型存放在 `~/.cache/huggingface/hub/` 下（若设置了 `$HF_HOME` 则在那里）。后续启动**不会**重复下载已缓存的模型。

---

## Web 控制台空空如也

**症状。** 打开 <http://localhost:8321/> 后「记忆管理 → 记忆」标签页为空，或记忆管理概览显示 `0 memories`。

**原因（最常见）。** 当前工作区是空的 —— 你启动服务时所在的目录，和持有你 `hebb.db` 的目录不是同一个。Hebb Mind 按如下顺序解析工作区：

1. 设置了 `$HEBB_HOME` 时优先用它
2. 最近的、包含 `hebb.json` 的上级目录
3. `~/.hebb/` 作为全局默认

**解决。** 打印解析出的位置：

```bash
hebb config get workspace
# /Users/you/projects/myapp/hebb.db
```

如果不是你预期的，要么 `cd` 进入持有该 db 的项目，要么显式锁定：

```bash
export HEBB_HOME=/path/to/your/workspace
hebb service restart
```

控制台每个标签页的功能介绍见 [Web 控制台](./guide/web-console.md)。

---

## Claude Code 里 MCP 服务起不来

**症状。** Claude Code 把 `hebb` MCP 服务显示为 `failed`，或者根本列不出它的工具。在 Claude Code 里执行 `/mcp` 对 hebb 没有任何返回。

**原因。** 要么集成没有在你正在用的 scope 下注册，要么 Hebb Mind 的 HTTP 服务没有运行（MCP 入口是一个 stdio 代理，它会去访问 <http://localhost:8321>）。

**解决。**

```bash
# 1. 确认 HTTP 服务已启动
hebb status
# 预期："Hebb Mind is running at http://localhost:8321"

# 2. 查看 Claude Code 都知道哪些 MCP
claude mcp list

# 3. 在正确的 scope 下重新安装（project / user）
hebb claude-code install --scope user
```

`--scope user` 会写入 `~/.claude/settings.json`，对所有项目生效；`--scope project` 则把集成限定在当前目录。安装后请彻底退出并重新打开 Claude Code，让它重新读取 settings 文件。

如果 `hebb claude-code install` 本身就失败，运行 `hebb doctor` —— 它会检查 `claude` CLI 是否在 `$PATH` 上，缺失时给出清晰的报错。

---

## 还是搞不定？

- `hebb doctor` —— 一次性体检 LLM 模型、Embedding 模型、服务和集成工具。
- [FAQ](./faq.md) —— 常见概念性问题的简短答案。
- [GitHub Issues](https://github.com/afx-team/hebb-mind/issues) —— 提交前先搜索；附上 `hebb doctor` 的输出和失败的命令。
