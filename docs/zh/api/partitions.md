# 分区 API

分区用于组织和分类记忆。系统内置 5 个分区，用户可以创建自定义分区。

## 列出分区

```
GET /api/v1/partitions
```

```bash
curl http://localhost:8321/api/v1/partitions
```

响应：

```json
[
  {
    "id": "mem_hippocampus",
    "name": "Hippocampus",
    "description": "Working memory inbox. New memories arrive here before consolidation.",
    "enabled": true,
    "is_system": true,
    "created_at": "2026-04-17T00:00:00Z",
    "updated_at": "2026-04-17T00:00:00Z",
    "memory_count": 12
  },
  {
    "id": "mem_semantic",
    "name": "Semantic Memory",
    "description": "Facts, knowledge, and general world information.",
    "enabled": true,
    "is_system": true,
    "created_at": "2026-04-17T00:00:00Z",
    "updated_at": "2026-04-17T00:00:00Z",
    "memory_count": 45
  }
]
```

## 获取分区详情

```
GET /api/v1/partitions/{partition_id}
```

```bash
curl http://localhost:8321/api/v1/partitions/mem_semantic
```

## 创建分区

```
POST /api/v1/partitions
```

请求体：

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `id` | string | 是 | 分区 ID，必须以 `mem_` 开头，5-64 个字符，只能包含小写字母、数字和下划线 |
| `name` | string | 是 | 分区显示名称（1-128 字符） |
| `description` | string | 否 | 分区描述 |
| `enabled` | boolean | 否 | 是否启用（默认 true） |

```bash
curl -X POST http://localhost:8321/api/v1/partitions \
  -H "Content-Type: application/json" \
  -d '{
    "id": "mem_project_alpha",
    "name": "Alpha 项目",
    "description": "与 Alpha 项目相关的技术决策和进展"
  }'
```

返回状态码 `201`。如果分区 ID 已存在，返回 `409 Conflict`。

## 更新分区

```
PATCH /api/v1/partitions/{partition_id}
```

支持部分更新 `name`、`description`、`enabled` 字段。

```bash
curl -X PATCH http://localhost:8321/api/v1/partitions/mem_project_alpha \
  -H "Content-Type: application/json" \
  -d '{"description": "已归档的 Alpha 项目记忆", "enabled": false}'
```

## 删除分区

```
DELETE /api/v1/partitions/{partition_id}
```

```bash
curl -X DELETE http://localhost:8321/api/v1/partitions/mem_project_alpha
```

返回状态码 `204`。

::: warning
系统内置分区（`is_system: true`）无法删除，尝试删除会返回 `403 Forbidden`。这 5 个系统分区包括：`mem_hippocampus`、`mem_semantic`、`mem_episodic`、`mem_preference`、`mem_procedural`。
:::
