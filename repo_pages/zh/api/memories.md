# 记忆 API

记忆的增删改查接口。所有端点前缀为 `/api/v1`。

## 列出记忆

```
GET /api/v1/memories
```

查询参数：

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `partition_id` | string | - | 按分区过滤 |
| `tags` | string | - | 按标签过滤，多个标签用逗号分隔 |
| `offset` | int | 0 | 分页偏移量 |
| `limit` | int | 50 | 每页数量（1-200） |

```bash
# 列出所有记忆
curl http://localhost:8321/api/v1/memories

# 按分区过滤
curl "http://localhost:8321/api/v1/memories?partition_id=mem_semantic"

# 按标签过滤
curl "http://localhost:8321/api/v1/memories?tags=python,web"

# 分页
curl "http://localhost:8321/api/v1/memories?offset=50&limit=20"
```

响应：

```json
{
  "items": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "partition_id": "mem_semantic",
      "content": "Python 是一门解释型编程语言",
      "importance_score": 6.0,
      "tags": ["python", "编程语言"],
      "metadata": {},
      "source": "consolidation",
      "created_at": "2026-04-17T10:00:00Z",
      "updated_at": "2026-04-17T10:00:00Z",
      "last_accessed_at": "2026-04-17T12:30:00Z",
      "access_count": 3,
      "expires_at": "2026-04-24T10:00:00Z"
    }
  ],
  "total": 128,
  "offset": 0,
  "limit": 50
}
```

## 获取记忆详情

```
GET /api/v1/memories/{memory_id}
```

每次访问会自动更新 `last_accessed_at` 和 `access_count`，影响遗忘 TTL 的计算。

```bash
curl http://localhost:8321/api/v1/memories/550e8400-e29b-41d4-a716-446655440000
```

## 创建记忆

```
POST /api/v1/memories
```

请求体：

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `content` | string | 是 | - | 记忆内容（1-10000 字符） |
| `partition_id` | string | 否 | `mem_hippocampus` | 目标分区 |
| `importance_score` | float | 否 | 5.0 | 重要性评分（0-10） |
| `tags` | list[string] | 否 | [] | 标签列表 |
| `metadata` | dict | 否 | {} | 附加元数据 |
| `source` | string | 否 | null | 来源标识 |

```bash
curl -X POST http://localhost:8321/api/v1/memories \
  -H "Content-Type: application/json" \
  -d '{
    "content": "用户喜欢使用 Vim 编辑器",
    "importance_score": 7.0,
    "tags": ["编辑器", "偏好"],
    "metadata": {"session": "abc123"}
  }'
```

返回状态码 `201`，响应体为创建的完整记忆对象。

## 批量创建记忆

```
POST /api/v1/memories/batch
```

一次性创建多条记忆，Embedding 会批量计算以提升效率。

```bash
curl -X POST http://localhost:8321/api/v1/memories/batch \
  -H "Content-Type: application/json" \
  -d '[
    {"content": "用户的时区是 UTC+8"},
    {"content": "用户偏好暗色主题", "importance_score": 6.0},
    {"content": "上周讨论了微服务架构", "tags": ["架构", "微服务"]}
  ]'
```

返回状态码 `201`，响应体为记忆对象数组。

## 更新记忆

```
PATCH /api/v1/memories/{memory_id}
```

支持部分更新，只传需要修改的字段。如果更新了 `content`，系统会自动重新计算 Embedding。

```bash
curl -X PATCH http://localhost:8321/api/v1/memories/550e8400-e29b-41d4-a716-446655440000 \
  -H "Content-Type: application/json" \
  -d '{
    "importance_score": 9.0,
    "tags": ["python", "编程语言", "最爱"]
  }'
```

## 删除记忆

```
DELETE /api/v1/memories/{memory_id}
```

```bash
curl -X DELETE http://localhost:8321/api/v1/memories/550e8400-e29b-41d4-a716-446655440000
```

返回状态码 `204`，无响应体。
