# 配置 API

通过 HTTP 接口读取和修改 `hippocampus.json` 配置。

## 获取配置

```
GET /api/v1/config
```

返回所有配置项。敏感字段（`llm_api_key`、`pg_url`）自动脱敏显示。

```bash
curl http://localhost:8321/api/v1/config
```

响应：

```json
{
  "storage_type": "sqlite",
  "home": null,
  "pg_url": null,
  "pg_pool_min": 2,
  "pg_pool_max": 10,
  "embedding_enabled": true,
  "embedding_model": "BAAI/bge-m3",
  "embedding_dim": 1024,
  "hf_endpoint": "https://hf-mirror.com",
  "llm_model": null,
  "llm_base_url": null,
  "llm_api_key": "sk-x****ykey",
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

## 更新配置

```
PUT /api/v1/config
```

每次更新一个配置字段，修改会直接写入 `hippocampus.json`。

```bash
curl -X PUT http://localhost:8321/api/v1/config \
  -H "Content-Type: application/json" \
  -d '{"key": "llm_model", "value": "openai/gpt-4o"}'
```

响应：

```json
{
  "key": "llm_model",
  "value": "openai/gpt-4o",
  "restart_required": false
}
```

`restart_required` 为 `true` 时，修改需要重启服务才能生效。需要重启的字段包括：`storage_type`、`home`、`pg_url`、`embedding_enabled`、`embedding_model`、`embedding_dim`、`host`、`port` 等。

## 查看敏感值

```
GET /api/v1/config/reveal/{key}
```

查看被脱敏的配置字段的完整值，仅支持 `llm_api_key` 和 `pg_url`。

```bash
curl http://localhost:8321/api/v1/config/reveal/llm_api_key
```

响应：

```json
{
  "key": "llm_api_key",
  "value": "sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
}
```

## 测试 LLM 连接

```
POST /api/v1/config/test-llm
```

使用指定的模型、URL 和 API 密钥测试 LLM 连通性。

```bash
curl -X POST http://localhost:8321/api/v1/config/test-llm \
  -H "Content-Type: application/json" \
  -d '{
    "model": "openai/gpt-4o-mini",
    "api_key": "sk-your-key"
  }'
```

成功响应：

```json
{
  "success": true,
  "response": "ok",
  "model": "gpt-4o-mini"
}
```

失败响应：

```json
{
  "success": false,
  "error": "AuthenticationError: Invalid API key"
}
```

::: tip
如果 `api_key` 包含 `****`（从 GET /config 复制的脱敏值），系统会自动从配置文件中读取真实密钥。
:::

## 获取字段元数据

```
GET /api/v1/config/fields
```

返回所有配置字段的类型、描述和默认值，适用于动态构建配置表单。

```bash
curl http://localhost:8321/api/v1/config/fields
```

响应：

```json
[
  {
    "key": "storage_type",
    "type": "string",
    "description": "'sqlite' or 'postgresql'",
    "default": "sqlite"
  },
  {
    "key": "port",
    "type": "number",
    "description": "",
    "default": 8321
  }
]
```
