# 配置

Hippocampus 的所有配置集中在项目目录下的 `hippocampus.json` 文件中，无需设置环境变量。

## CLI 管理

```bash
# 列出所有配置
hippocampus config list

# 获取单个配置值
hippocampus config get llm_model

# 设置配置值
hippocampus config set llm_api_key sk-xxx
hippocampus config set port 8000
hippocampus config set embedding_enabled false

# 查看配置文件路径
hippocampus config path
```

## 完整配置项

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `storage_type` | string | `"sqlite"` | 存储后端，可选 `"sqlite"` 或 `"postgresql"` |
| `db_path` | string | `"hippocampus.db"` | SQLite 数据库文件路径 |
| `pg_url` | string | `null` | PostgreSQL 连接字符串 |
| `pg_pool_min` | number | `2` | PostgreSQL 连接池最小连接数 |
| `pg_pool_max` | number | `10` | PostgreSQL 连接池最大连接数 |
| `embedding_enabled` | boolean | `true` | 是否启用向量搜索 |
| `embedding_model` | string | `"all-MiniLM-L6-v2"` | Embedding 模型名称 |
| `embedding_dim` | number | `384` | 向量维度 |
| `llm_model` | string | `null` | LLM 模型标识（如 `openai/gpt-4o-mini`） |
| `llm_base_url` | string | `null` | 自定义 LLM API 地址 |
| `llm_api_key` | string | `null` | LLM 提供商 API 密钥 |
| `host` | string | `"0.0.0.0"` | 服务监听地址 |
| `port` | number | `8321` | 服务监听端口 |
| `consolidation_interval_seconds` | number | `3600` | 巩固任务执行间隔（秒） |
| `forget_interval_seconds` | number | `1800` | 遗忘任务执行间隔（秒） |
| `base_ttl_hours` | number | `168.0` | 记忆基础存活时间（小时），即 7 天 |
| `decay_factor` | number | `0.693` | 遗忘衰减因子 |
| `weight_recency` | number | `1.0` | 检索时"时效性"权重 |
| `weight_importance` | number | `1.0` | 检索时"重要性"权重 |
| `weight_relevance` | number | `1.0` | 检索时"相关性"权重 |
| `kg_path` | string | `"knowledge_graph.json"` | 知识图谱文件路径 |

## 示例配置文件

```json
{
  "storage_type": "sqlite",
  "db_path": "hippocampus.db",
  "embedding_enabled": true,
  "embedding_model": "all-MiniLM-L6-v2",
  "embedding_dim": 384,
  "llm_model": "openai/gpt-4o-mini",
  "llm_api_key": "sk-your-key",
  "host": "0.0.0.0",
  "port": 8321,
  "consolidation_interval_seconds": 3600,
  "forget_interval_seconds": 1800,
  "base_ttl_hours": 168.0,
  "decay_factor": 0.693,
  "weight_recency": 1.0,
  "weight_importance": 1.0,
  "weight_relevance": 1.0,
  "kg_path": "knowledge_graph.json"
}
```

## Web 控制台配置

启动服务后，打开 `http://localhost:8321/` 进入 Web 控制台，在 **Settings** 页面也可以可视化编辑配置。修改后会自动写入 `hippocampus.json`。

::: tip
部分配置修改后需要重启服务才能生效，包括：`storage_type`、`db_path`、`pg_url`、`embedding_enabled`、`embedding_model`、`embedding_dim`、`host`、`port`、`kg_path`。
:::
