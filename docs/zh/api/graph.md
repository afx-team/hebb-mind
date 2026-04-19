# 知识图谱 API

知识图谱由巩固过程中提取的标签构成，节点是标签，边是共现关系。

## 列出标签

```
GET /api/v1/graph/tags
```

```bash
# 列出所有标签
curl http://localhost:8321/api/v1/graph/tags

# 搜索匹配的标签
curl "http://localhost:8321/api/v1/graph/tags?q=python"
```

响应：

```json
[
  {
    "id": "python",
    "weight": 12.0,
    "memory_ids": ["550e8400-...", "661f9500-..."]
  },
  {
    "id": "异步编程",
    "weight": 5.0,
    "memory_ids": ["772a0600-..."]
  }
]
```

## 获取标签详情

```
GET /api/v1/graph/tags/{tag_id}
```

```bash
curl http://localhost:8321/api/v1/graph/tags/python
```

如果标签不存在，返回 `404`。

## 查询邻居

```
GET /api/v1/graph/neighbors/{tag_id}
```

查询参数：

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `depth` | int | 1 | 遍历深度（1-5） |

```bash
# 查询 1-hop 邻居
curl http://localhost:8321/api/v1/graph/neighbors/python

# 查询 2-hop 邻居
curl "http://localhost:8321/api/v1/graph/neighbors/python?depth=2"
```

响应包含图查询结果中涉及的所有节点和边。

## 最短路径

```
GET /api/v1/graph/path?from={source}&to={target}
```

查找两个标签之间的最短路径。

```bash
curl "http://localhost:8321/api/v1/graph/path?from=python&to=web-development"
```

响应包含路径上的所有节点和边。如果两个标签之间没有路径，返回空结果。

## 导出图谱

```
GET /api/v1/graph/export
```

导出完整的图谱数据，包含所有节点和边。

```bash
curl http://localhost:8321/api/v1/graph/export
```

响应：

```json
{
  "nodes": [
    {"id": "python", "weight": 12.0, "memory_ids": ["..."]},
    {"id": "web-development", "weight": 8.0, "memory_ids": ["..."]}
  ],
  "edges": [
    {"source": "python", "target": "web-development", "weight": 3.0}
  ],
  "version": 1
}
```

导出的数据可用于前端可视化或外部分析工具。
