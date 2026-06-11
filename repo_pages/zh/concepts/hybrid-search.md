---
description: "Hebb Mind 混合检索：向量语义、关键词（FTS5/BM25）与知识图谱三路并行召回，经 RRF 融合排名与三维评分，再用 cross-encoder 重排序提升 AI 智能体记忆的召回精度。"
---

# 混合检索

Hebb Mind 采用三路并行检索策略，综合向量语义、关键词匹配和知识图谱三种信号，通过 Reciprocal Rank Fusion（RRF）融合排名，再做三维综合评分，最后可选地用 cross-encoder 重排序提升 top-k 精度。

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
       Reciprocal Rank Fusion (RRF)
       按 memory ID 融合三路排名
                 │
                 ▼
          三维综合评分
   时效性 + 重要性 + 相关性
                 │
                 ▼
     cross-encoder 重排序（可选，默认开启）
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
- 默认 Embedding 模型由 `hebb setup` 根据语言与 profile 选择：裸 `setup` 用小模型（英语 `all-MiniLM-L6-v2`，中文/多语言 `intfloat/multilingual-e5-small`）；`--profile best` 用 `BAAI/bge-large-en-v1.5`（英语）/ `BAAI/bge-m3`（中文/多语言）

### 2. 关键词路

基于全文索引进行关键词匹配，适合精确名词、代码片段等场景。

- **SQLite 后端**：使用 FTS5 全文索引
- **PostgreSQL 后端**：使用 tsvector + BM25 排序

### 3. 图谱路

通过知识图谱中的标签共现关系扩展候选集（基于标签匹配，而非语义理解）：

1. 将查询词与图谱中的标签做匹配
2. 沿共现边扩展到 1-hop 邻居
3. 收集匹配标签及其邻居关联的 memory ID
4. 根据标签权重给出相关性分数

> 图谱路是一条基于标签的轻量召回通道，用于补充向量/关键词漏掉的概念关联，**不**等同于真正的语义检索或多跳推理。

## 融合与评分

三路结果通过 Reciprocal Rank Fusion（RRF）按 memory ID 融合排名——同一条记忆在多路命中时，其多路排名共同决定融合分数。融合后进行三维综合评分：

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

## Cross-encoder 重排序

综合评分后，系统默认会用一个 cross-encoder 模型对 top-N 候选重新打分排序。它把查询与每条候选记忆的内容拼成一对一起编码，比向量内积更能捕捉细粒度的相关性，是提升 top-k 精度的主要手段。重排序在资源受限时可关闭，关闭后排序回退到融合 + 综合评分。

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
