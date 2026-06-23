---
description: "Hebb Mind 全部配置集中在 hebb.json 一个文件：CLI 命令、工作目录解析、Embedding 模型、LLM 与巩固开关，以及完整字段参考与重启生效规则。"
---

# 配置

Hebb Mind 的所有配置集中在项目目录下的 `hebb.json` 文件中，无需设置环境变量。

首次使用推荐：

```bash
hebb setup --language auto --region auto
```

`language` 决定 Embedding 模型，`region` 决定 HuggingFace 下载源，二者独立。

## CLI 管理

```bash
# 列出所有配置
hebb config list

# 获取单个配置值
hebb config get llm_model

# 设置配置值
hebb config set llm_api_key sk-xxx
hebb config set port 8000
hebb config set embedding_enabled false

# 查看配置文件路径
hebb config path

# 查看 Embedding 模型状态
hebb model status
```

## 完整配置项

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `storage_type` | string | `"sqlite"` | 存储后端，可选 `"sqlite"` 或 `"postgresql"` |
| `home` | string | `null` | 工作目录覆盖。设置后数据文件存储在此目录。也可通过 HEBB_HOME 环境变量设置。 |
| `pg_url` | string | `null` | PostgreSQL 连接字符串 |
| `pg_pool_min` | number | `2` | PostgreSQL 连接池最小连接数 |
| `pg_pool_max` | number | `10` | PostgreSQL 连接池最大连接数 |
| `embedding_enabled` | boolean | `true` | 是否启用向量搜索 |
| `embedding_model` | string | setup 选定 | Embedding 模型名称。默认 profile 选小模型：英文 `all-MiniLM-L6-v2`（~90MB），中文/多语言 `intfloat/multilingual-e5-small`（~470MB）。`--profile best` 改选高质量档：英文 `BAAI/bge-large-en-v1.5`、中文/多语言 `BAAI/bge-m3`（1–2GB 以上）。切换流程见 [切换 Embedding 模型](./switch-embedding-model.md) |
| `embedding_dim` | number | setup 选定 | 向量维度（须与模型一致；小模型默认 384）。修改后启动时向量表会自动重建；重启后跑 `hebb memory reembed` 重新计算 |
| `hf_endpoint` | string | `null` | HuggingFace 镜像地址。`setup --region cn` 会设置 `https://hf-mirror.com` |
| `llm_model` | string | `null` | LLM 模型标识（如 `openai/gpt-4o-mini`）。这是巩固功能的**开关门槛** —— 不设它，巩固/冲突解决/标签提取都静默跳过 |
| `llm_base_url` | string | `null` | 自定义 LLM API 地址（通义千问、GLM、Kimi 等） |
| `llm_api_key` | string | `null` | LLM 提供商 API 密钥（**托管厂商需要**；本地/代理模型可留空） |
| `host` | string | `"127.0.0.1"` | 服务监听地址（仅本机回环）。注：`<=0.1.6` 版本默认为 `0.0.0.0` |
| `port` | number | `8321` | 服务监听端口 |
| `consolidation_time` | string | `"18:00"` | 每日巩固时间（`HH:MM`） |
| `forget_interval_seconds` | number | `1800` | 遗忘任务执行间隔（秒） |
| `half_life_days` | number | `60` | 遗忘的基础留存半衰期（天）。内置分区会各自覆盖，详见[动态遗忘](../concepts/forgetting.md)。 |
| `k_importance` | number | `2.0` | 重要度对半衰期的拉长强度（×重要度/10） |
| `k_access` | number | `1.5` | 访问次数对半衰期的拉长强度（×访问次数/10） |
| `forget_threshold` | number | `0.3` | 留存率低于此值即被遗忘 |
| `forget_min_retention_days` | number | `1` | 任何记忆留存寿命的硬下限（天） |
| `weight_recency` | number | `1.0` | 检索时"时效性"权重 |
| `weight_importance` | number | `1.0` | 检索时"重要性"权重 |
| `weight_relevance` | number | `1.0` | 检索时"相关性"权重 |

## 示例配置文件

下面 `embedding_model` / `embedding_dim` 展示的是裸默认值（`hebb setup --profile default --language en`）。`hebb setup` 会按你的语言环境和 `--profile` 写入相应的值，详见上方字段表。

```json
{
  "storage_type": "sqlite",
  "home": null,
  "embedding_enabled": true,
  "embedding_model": "all-MiniLM-L6-v2",
  "embedding_dim": 384,
  "hf_endpoint": null,
  "llm_model": null,
  "llm_api_key": null,
  "host": "127.0.0.1",
  "port": 8321,
  "consolidation_time": "18:00",
  "forget_interval_seconds": 1800,
  "half_life_days": 60,
  "k_importance": 2.0,
  "k_access": 1.5,
  "forget_threshold": 0.3,
  "forget_min_retention_days": 1,
  "weight_recency": 1.0,
  "weight_importance": 1.0,
  "weight_relevance": 1.0
}
```

## 工作目录

Hebb Mind 的数据文件（`hebb.db`、`knowledge_graph.json`）始终存储在工作目录中。工作目录的解析优先级如下：

1. **`HEBB_HOME` 环境变量** — 最高优先级
2. **`home` 配置字段** — `hebb.json` 中的 `home` 字段
3. **配置文件所在目录** — `hebb.json` 的父目录
4. **`~/.hebb/`** — 默认目录

```bash
# 查看当前解析的工作目录
hebb config get workspace
# 输出示例：/home/user/.hebb

# 通过环境变量覆盖工作目录
export HEBB_HOME=/data/hebb

# 或在配置文件中设置
hebb config set home /data/hebb
```

## Web 控制台配置

启动服务后，打开 `http://localhost:8321/` 进入 Web 控制台。基础设施配置（LLM、嵌入、存储、服务）在 **系统设置（System）** 页面，召回、巩固、遗忘参数分别在对应的 **记忆激活 / 记忆巩固 / 记忆遗忘** 页面，均可可视化编辑，修改后会自动写入 `hebb.json`。

::: tip
部分配置修改后需要重启服务才能生效，包括：`storage_type`、`home`、`pg_url`、`embedding_enabled`、`embedding_model`、`embedding_dim`、`hf_endpoint`、`host`、`port`。
:::

## 国内镜像加速

国内用户下载 HuggingFace 模型可能较慢，可以通过配置镜像加速：

```bash
hebb setup --region cn
```

设置后，启动服务时会自动通过镜像站下载 Embedding 模型。

也可以手动设置：

```bash
hebb config set hf_endpoint https://hf-mirror.com
```
