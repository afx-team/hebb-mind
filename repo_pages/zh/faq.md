---
description: "Hebb Mind 常见问题：是否需要 LLM API Key、支持哪些 LLM 与 embedding 模型、数据存在哪里、与 mem0 对比、PostgreSQL 与 Docker 部署，以及本地 AI Agent 记忆。"
---

# 常见问题

回答那些在深入读文档之前就会冒出来的问题。基于症状的求助请看 [故障排查](./troubleshooting.md)。

---

## 我需要 LLM API Key 吗？

写入、向量检索、CRUD 和 Web 控制台都**不需要**。但巩固、冲突解决、重要度打分和标签提取都**需要 LLM**。这些功能的开关门槛是 `llm_model`：没有设置它，`POST /api/v1/admin/consolidate` 虽然会运行，但处理 0 条记忆。用 `hebb config set llm_model <provider>/<model>` 设置模型。本地或代理模型只需模型名即可；托管厂商还需要再设置 `llm_api_key`。

## 支持哪些 LLM？

凡是 [LiteLLM](https://github.com/BerriAI/litellm) 支持的都行 —— OpenAI、Anthropic、Google、Azure、Bedrock、通义千问、GLM、Kimi、Ollama、vLLM 等等。用 `hebb config set llm_model <provider>/<model>` 切换；非 OpenAI 端点再加 `llm_base_url`。详见 [多模型](./advanced/multi-model.md)。

## 我的数据存在哪里？

存在工作区目录下的一个 SQLite 文件加一份 JSON 知识图谱里。运行 `hebb config get workspace` 查看解析出的路径。解析顺序：`$HEBB_HOME` → 最近的 `hebb.json` → `~/.hebb/`。

## 能用于生产环境吗？

v0.1.x 标注为**实验性**。CRUD 和检索是稳定的；巩固与遗忘策略可能在小版本里变化。HTTP 服务没有内置鉴权，且 CORS 默认完全放开 —— 暴露前请用带鉴权的反向代理挡在前面。如需更高并发，支持 PostgreSQL。

## 和 mem0 相比如何？

两者都用 embedding 存储 Agent 记忆。Hebb Mind 的不同之处在于：(a) 以单一本地二进制运行，内置 Web 控制台和 MCP 服务；(b) 实现了一套受神经科学启发的巩固周期（编码 → 巩固 → 遗忘）；(c) 默认完全本地推理。mem0 在托管云端的打磨上更成熟，我们在本地掌控力上更强。见 [从 mem0 迁移](./guide/migration.md#从-mem0-迁移)。

## Web 控制台支持多租户吗？

不支持。控制台（及其底层 API）当前一次只操作一个工作区，没有鉴权、没有按用户的隔离。请用**分区**（`partition_id`）在同一实例内切分逻辑上的记忆桶，但把它们当作命名空间，而非安全边界。

## 怎么导出我的记忆？

HTTP API 可以一次性把它们全部 dump 出来：

```bash
curl "http://localhost:8321/api/v1/memories?limit=200&offset=0" > memories.json
```

如需完整备份，请复制工作区文件（见下方「怎么备份数据库？」）。一个一等公民的 `hebb export` 命令在 roadmap 上。

## 怎么备份数据库？

先停服务，避免拷到写了一半的 WAL，再复制工作区：

```bash
hebb service stop
cp -a "$(hebb config get workspace)" ~/backup/hebb-$(date +%Y%m%d)
hebb service start
```

PostgreSQL 用 `pg_dump` 针对 `pg_url` 里设置的地址来备份。

## 能跑在 PostgreSQL 上吗？

可以：

```bash
hebb config set storage_type postgresql
hebb config set pg_url "postgresql://user:pass@host:5432/hebb"
```

首次启动时会自动建表。`pgvector` 的要求见 [存储后端](./advanced/storage-backends.md)。

## 有托管版吗？

目前没有。Hebb Mind 设计为在本地或你自己的基础设施上运行。如果未来出现托管选项，会在 [GitHub 仓库](https://github.com/afx-team/hebb-mind) 上公布。

## 怎么用 Docker 部署？

参考镜像和 `docker-compose.yml`（含 PostgreSQL + pgvector）见 [存储后端 → Docker](./advanced/storage-backends.md#docker-deployment)。最短版本：

```bash
docker run -p 8321:8321 -v ~/.hebb:/data ghcr.io/afx-team/hebb-mind:latest
```

## 用的什么许可证？

MIT。见仓库里的 [LICENSE](https://github.com/afx-team/hebb-mind/blob/main/LICENSE)。可商用、可修改、可再分发 —— 保留版权声明即可。

## 怎么贡献？

欢迎在 <https://github.com/afx-team/hebb-mind> 提 issue、PR 和讨论。当下最有用的贡献是：附带 `hebb doctor` 输出的真实 bug 报告、集成方案（Cursor / Continue / Cline），以及在我们没有的硬件上复现 benchmark。见仓库根目录的 `CONTRIBUTING.md`。

## 为什么叫 "Hebb Mind"？

**Hebb Mind** 取名自加拿大神经心理学家 **唐纳德·O·赫布（Donald O. Hebb，1904–1985）**，他 1949 年的著作《行为的组织》给了我们赫布学习 —— *「一起放电的神经元，会连到一起」*。这条法则正是本框架的核心：标签知识图谱把共现的概念连到一起，每次它们再次出现就强化这条连边；巩固保留被强化的，遗忘修剪其余的。

**hippocampus（海马体）** —— 这个项目最初的名字 —— 作为工作记忆分区（`mem_hippocampus`）的名称在 Hebb Mind 里延续了下来：它是新记忆在巩固前落地的收件箱，呼应大脑中那个把新经验送入长期记忆的脑区。见 [记忆生命周期](./concepts/memory-lifecycle.md)。

## Embedding 模型支持多语言吗？

取决于 `hebb setup` 选了什么。`hebb setup`（默认 profile）会选一个**小模型**：英文是 `all-MiniLM-L6-v2`（约 90MB），中文/多语言是 `intfloat/multilingual-e5-small`（约 470MB，多语言）。需要更高质量时，用 `hebb setup --profile best` 选用 bge 系列（英文 `BAAI/bge-large-en-v1.5`、中文/多语言 `BAAI/bge-m3`，1–2GB 以上，仅在需要时下载）。安装后想换模型 —— 包括维度变化 → 重新计算向量的流程 —— 见 [切换 Embedding 模型](./guide/switch-embedding-model.md)。
