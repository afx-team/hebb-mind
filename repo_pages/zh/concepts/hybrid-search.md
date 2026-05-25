# 混合检索

Hebb Mind 采用三路并行检索策略，综合向量语义、关键词匹配和知识图谱三种能力，确保高召回率和精准排序。

## 检索架构

```
搜索请求
  │
  ├──────────────┬──────────────┐
  ▼              ▼              ▼
向量路         关键词路        图谱路
sqlite-vec     FTS5           知识图谱
/ pgvector     / tsvector     邻居遍历
  │              │              │
  └──────────────┴──────────────┘
                 │
                 ▼
         按 memory ID 去重
         取最大相关性分数
                 │
                 ▼
          三维综合评分
   时效性 + 重要性 + 相关性
                 │
                 ▼
         Top-K 主结果
                 │
                 ▼
         后置图谱扩展
         发现关联记忆
                 │
                 ▼
        返回 results + related
```

## 三路并行检索

### 1. 向量路

通过 Embedding 模型将查询转为向量，在向量索引中检索语义相近的记忆。

- **SQLite 后端**：使用 sqlite-vec 扩展进行向量检索
- **PostgreSQL 后端**：使用 pgvector 进行向量检索
- 默认 Embedding 模型由 `hebb setup` 根据语言选择：英语为 `BAAI/bge-large-en-v1.5`，中文/多语言为 `BAAI/bge-m3`

### 2. 关键词路

基于全文索引进行关键词匹配，适合精确名词、代码片段等场景。

- **SQLite 后端**：使用 FTS5 全文索引
- **PostgreSQL 后端**：使用 tsvector + BM25 排序

### 3. 图谱路

利用知识图谱进行概念层面的检索：

1. 将查询关键词与图谱中的标签匹配
2. 沿共现边扩展到 1-hop 邻居
3. 收集邻居标签关联的 memory ID
4. 根据标签权重计算相关性分数

## 去重与评分

三路结果按 memory ID 合并，同一条记忆取最大相关性分数。然后进行三维综合评分：

```
score = (w_recency * recency + w_importance * importance + w_relevance * relevance)
        / (w_recency + w_importance + w_relevance)
```

各维度说明：

| 维度 | 计算方式 | 含义 |
|------|---------|------|
| **时效性** (recency) | `decay^hours_since_access` | 最近访问的记忆得分更高 |
| **重要性** (importance) | `importance_score / 10.0` | 归一化到 [0, 1] |
| **相关性** (relevance) | 向量/关键词/图谱检索得分 | 与查询的匹配程度 |

三个权重 (`weight_recency`, `weight_importance`, `weight_relevance`) 均可在配置中调整，也可在每次搜索请求中覆盖。

## 后置扩展

主结果确定后，系统从 Top-K 结果中提取标签，通过知识图谱边发现关联记忆，作为 `related` 字段返回。这些记忆虽然不直接匹配搜索词，但与搜索结果存在概念关联。

## 搜索示例

```bash
curl -X POST http://localhost:8321/api/v1/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "用户的编程偏好",
    "top_k": 5,
    "weight_recency": 0.5,
    "weight_importance": 1.5,
    "weight_relevance": 1.0
  }'
```

响应结构：

```json
{
  "results": [
    {
      "memory": { "id": "...", "content": "...", ... },
      "score": 0.87,
      "recency_score": 0.95,
      "importance_score_normalized": 0.8,
      "relevance_score": 0.85
    }
  ],
  "related": [
    { "id": "...", "content": "...", ... }
  ]
}
```
