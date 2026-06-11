---
description: "POST /api/v1/search 接口参考：融合向量、关键词与知识图谱的混合检索，支持分区、标签过滤及时效性、重要性、相关性权重调节，为 AI 智能体提供长期记忆召回。"
---

# 搜索 API

通过混合检索查找与查询语义相关的记忆。

## 搜索记忆

```
POST /api/v1/search
```

### 请求体

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `query` | string | 是 | - | 搜索查询文本 |
| `partition_ids` | list[string] | 否 | null | 限定搜索的分区 |
| `tags` | list[string] | 否 | null | 按标签过滤结果 |
| `top_k` | int | 否 | 10 | 返回结果数量（1-100） |
| `weight_recency` | float | 否 | 1.0 | 时效性权重 |
| `weight_importance` | float | 否 | 1.0 | 重要性权重 |
| `weight_relevance` | float | 否 | 1.0 | 相关性权重 |

### 基本搜索

```bash
curl -X POST http://localhost:8321/api/v1/search \
  -H "Content-Type: application/json" \
  -d '{"query": "用户的编程语言偏好"}'
```

### 高级搜索

```bash
curl -X POST http://localhost:8321/api/v1/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "项目的技术栈",
    "partition_ids": ["mem_semantic", "mem_procedural"],
    "tags": ["技术"],
    "top_k": 5,
    "weight_recency": 0.5,
    "weight_importance": 2.0,
    "weight_relevance": 1.0
  }'
```

### 响应结构

```json
{
  "results": [
    {
      "memory": {
        "id": "550e8400-e29b-41d4-a716-446655440000",
        "partition_id": "mem_preference",
        "content": "用户更喜欢 Python 而不是 JavaScript",
        "importance_score": 7.0,
        "tags": ["编程语言", "偏好"],
        "metadata": {},
        "source": "consolidation",
        "created_at": "2026-04-17T10:00:00Z",
        "updated_at": "2026-04-17T10:00:00Z",
        "last_accessed_at": "2026-04-17T15:00:00Z",
        "access_count": 5,
        "expires_at": "2026-04-25T10:00:00Z"
      },
      "score": 0.87,
      "recency_score": 0.95,
      "importance_score_normalized": 0.7,
      "relevance_score": 0.85
    }
  ],
  "related": [
    {
      "id": "661f9500-f30c-52e5-b827-557766551111",
      "partition_id": "mem_semantic",
      "content": "Python 3.12 引入了类型参数语法",
      "importance_score": 5.0,
      "tags": ["python", "类型系统"],
      "metadata": {},
      "source": "api",
      "created_at": "2026-04-16T08:00:00Z",
      "updated_at": "2026-04-16T08:00:00Z",
      "last_accessed_at": "2026-04-16T08:00:00Z",
      "access_count": 1,
      "expires_at": null
    }
  ]
}
```

### 响应字段说明

**results** — 主结果列表，按综合评分降序排列：

| 字段 | 说明 |
|------|------|
| `memory` | 完整的记忆对象 |
| `score` | 综合评分（时效性 + 重要性 + 相关性的加权平均） |
| `recency_score` | 时效性分数，基于上次访问时间的指数衰减 |
| `importance_score_normalized` | 归一化后的重要性分数 [0, 1] |
| `relevance_score` | 与查询的匹配相关性分数 |

**related** — 通过知识图谱后置扩展发现的关联记忆。这些记忆不直接匹配搜索词，但与主结果的标签存在图谱关联，可帮助发现更多相关信息。
