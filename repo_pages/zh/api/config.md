---
description: "通过 HTTP 接口在运行时读取和修改 Hebb Mind 配置：LLM 与 embedding 参数、敏感字段脱敏、连通性测试、字段元数据，修改直接写入 hebb.json。"
---

# 配置 API

通过 HTTP 接口读取和修改 `hebb.json` 配置。

所有配置端点都挂载在 `/api/v1/admin/config` 下。

## 获取配置

```
GET /api/v1/admin/config
```

返回所有配置项。敏感字段（`llm_api_key`、`pg_url`、`embedding_api_key`）自动脱敏显示。

```bash
curl http://localhost:8321/api/v1/admin/config
```

响应（节选）：

```json
{
  "storage_type": "sqlite",
  "home": null,
  "embedding_enabled": true,
  "embedding_provider": "local",
  "embedding_model": "all-MiniLM-L6-v2",
  "embedding_dim": 384,
  "hf_endpoint": null,
  "llm_model": null,
  "llm_base_url": null,
  "llm_api_key": "sk-x****ykey",
  "host": "127.0.0.1",
  "port": 8321,
  "consolidation_time": "18:00",
  "forget_interval_seconds": 1800,
  "half_life_days": 60.0,
  "k_importance": 2.0,
  "k_access": 1.5,
  "forget_threshold": 0.3,
  "forget_min_retention_days": 1.0,
  "weight_recency": 1.0,
  "weight_importance": 1.0,
  "weight_relevance": 1.0
}
```

> `host` 默认绑定回环地址 `127.0.0.1`（仅本机可访问）。服务本身没有鉴权，对外暴露（如 `0.0.0.0`）属于显式选择，应配合防火墙或反向代理。`<=0.1.6` 版本默认为 `0.0.0.0`。

## 更新配置

```
PUT /api/v1/admin/config
```

每次更新一个配置字段，修改会直接写入 `hebb.json`。

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `key` | string | 是 | 配置字段名 |
| `value` | string | 是 | 字符串形式的新值，服务端按字段类型自动转换 |

```bash
curl -X PUT http://localhost:8321/api/v1/admin/config \
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

`restart_required` 为 `true` 时需要重启服务才能生效。需要重启的字段包括：`storage_type`、`pg_url`、`pg_pool_min`、`pg_pool_max`、`embedding_enabled`、`embedding_provider`、`embedding_model`、`embedding_dim`、`embedding_api_key`、`embedding_base_url`、`consolidation_time`、`host`、`port`、`home`。

## 查看敏感值

```
GET /api/v1/admin/config/reveal/{key}
```

仅支持 `llm_api_key`、`pg_url`、`embedding_api_key`。

```bash
curl http://localhost:8321/api/v1/admin/config/reveal/llm_api_key
```

响应：

```json
{
  "key": "llm_api_key",
  "value": "sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
}
```

## 测试 LLM 连接

向指定模型发起一次最小化的请求，验证 `model`/`base_url`/`api_key` 是否可用。如果 `api_key` 中包含 `****`（脱敏占位），服务端会自动从 `hebb.json` 中读取真实密钥。

```
POST /api/v1/admin/config/test-llm
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `model` | string | 是 | LiteLLM 模型标识，如 `openai/gpt-4o-mini` |
| `base_url` | string | 否 | 自定义 API 端点 |
| `api_key` | string | 否 | API Key（可填脱敏占位以使用已保存的密钥） |

```bash
curl -X POST http://localhost:8321/api/v1/admin/config/test-llm \
  -H "Content-Type: application/json" \
  -d '{"model": "openai/gpt-4o-mini", "api_key": "sk-your-key"}'
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

## 测试 Embedding 连接

验证本地 embedding 模型能否加载，或云端 embedding API 能否响应。

```
POST /api/v1/admin/config/test-embedding
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `provider` | string | 是 | `local` 或 `api` |
| `model` | string | 是 | 模型名称（HuggingFace ID 或 LiteLLM 模型 ID） |
| `base_url` | string | 否 | `api` 类型必填 |
| `api_key` | string | 否 | API Key 或脱敏占位 |

成功响应：

```json
{
  "success": true,
  "dimension": 384,
  "message": "Model loaded, dimension=384, sample vector length=384"
}
```

## Embedding 状态

返回当前 embedding 配置以及本地模型是否已缓存。

```
GET /api/v1/admin/config/embedding-status
```

响应（local，已缓存）：

```json
{
  "enabled": true,
  "provider": "local",
  "model": "all-MiniLM-L6-v2",
  "status": "cached",
  "cached": true
}
```

`status` 取值：`cached`、`not_downloaded`、`disabled`、`api`。

## 字段元数据

返回所有配置字段的类型、描述和默认值，便于动态构建表单。

```
GET /api/v1/admin/config/fields
```

响应（节选）：

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
