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
| `embedding_model` | string | setup-selected | Embedding 模型名称。英语默认 `BAAI/bge-large-en-v1.5`，中文/多语言默认 `BAAI/bge-m3` |
| `embedding_dim` | number | setup-selected | 向量维度 |
| `hf_endpoint` | string | `null` | HuggingFace 镜像地址。`setup --region cn` 会设置 `https://hf-mirror.com` |
| `llm_model` | string | `null` | LLM 模型标识（如 `openai/gpt-4o-mini`） |
| `llm_base_url` | string | `null` | 自定义 LLM API 地址 |
| `llm_api_key` | string | `null` | LLM 提供商 API 密钥 |
| `host` | string | `"0.0.0.0"` | 服务监听地址 |
| `port` | number | `8321` | 服务监听端口 |
| `consolidation_time` | string | `"18:00"` | 每日巩固时间（`HH:MM`） |
| `forget_interval_seconds` | number | `1800` | 遗忘任务执行间隔（秒） |
| `base_ttl_hours` | number | `168.0` | 记忆基础存活时间（小时），即 7 天 |
| `decay_factor` | number | `0.693` | 遗忘衰减因子 |
| `weight_recency` | number | `1.0` | 检索时"时效性"权重 |
| `weight_importance` | number | `1.0` | 检索时"重要性"权重 |
| `weight_relevance` | number | `1.0` | 检索时"相关性"权重 |

## 示例配置文件

```json
{
  "storage_type": "sqlite",
  "home": null,
  "embedding_enabled": true,
  "embedding_model": "BAAI/bge-m3",
  "embedding_dim": 1024,
  "hf_endpoint": "https://hf-mirror.com",
  "llm_model": null,
  "llm_api_key": null,
  "host": "0.0.0.0",
  "port": 8321,
  "consolidation_time": "18:00",
  "forget_interval_seconds": 1800,
  "base_ttl_hours": 168.0,
  "decay_factor": 0.693,
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
hebb workspace

# 也可通过 config get 查看
hebb config get workspace
```

示例：

```bash
# 通过环境变量设置工作目录
export HEBB_HOME=/data/hebb

# 或在配置文件中设置
hebb config set home /data/hebb
```

## Web 控制台配置

启动服务后，打开 `http://localhost:8321/` 进入 Web 控制台，在 **Settings** 页面也可以可视化编辑配置。修改后会自动写入 `hebb.json`。

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
