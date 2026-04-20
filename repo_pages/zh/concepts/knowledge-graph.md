# 知识图谱

Hippocampus 内置了基于标签的知识图谱，在记忆巩固过程中自动构建，用于增强检索和发现记忆之间的关联。

## 实现方式

- **图引擎**：NetworkX（内存中的图数据结构）
- **持久化**：JSON 文件（`knowledge_graph.json`）
- **节点**：标签（tag），每个节点关联一组 memory ID
- **边**：共现关系 — 两个标签在同一条记忆中同时出现时，它们之间就会建立一条边

## 构建过程

巩固代理在处理记忆时会提取标签，这些标签自动进入知识图谱：

1. LLM 从记忆内容中提取关键标签（如 "Python"、"异步编程"、"性能优化"）
2. 每个标签成为图中的一个节点
3. 同一条记忆的标签之间自动建立共现边
4. 边的权重随共现次数增加而增大

## 在搜索中的作用

知识图谱在混合检索中有两种用法：

### 1. 并行召回（搜索时）

在三路并行检索中，图谱路负责：

- 将搜索查询与图谱中的标签匹配
- 沿边扩展到 1-hop 邻居标签
- 收集关联的 memory ID 并返回

### 2. 后置扩展（结果返回前）

搜索主结果确定后：

- 从 top-K 结果中提取所有标签
- 通过图谱边发现关联记忆
- 作为 `related` 字段返回，帮助用户发现相关但未直接匹配的记忆

## API 端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/v1/graph/tags` | GET | 列出所有标签节点 |
| `/api/v1/graph/tags?q=python` | GET | 搜索匹配的标签 |
| `/api/v1/graph/tags/{tag_id}` | GET | 获取标签详情 |
| `/api/v1/graph/neighbors/{tag_id}` | GET | 查询邻居节点（支持 `depth` 参数） |
| `/api/v1/graph/path?from=A&to=B` | GET | 查找两个标签之间的最短路径 |
| `/api/v1/graph/export` | GET | 导出完整图谱数据 |

## 示例

查询某个标签的邻居：

```bash
curl http://localhost:8321/api/v1/graph/neighbors/python?depth=2
```

查找两个概念之间的路径：

```bash
curl "http://localhost:8321/api/v1/graph/path?from=python&to=web-development"
```

导出完整图谱（可用于可视化）：

```bash
curl http://localhost:8321/api/v1/graph/export
```

## Web 控制台可视化

在 Web 控制台中可以直观地浏览知识图谱，查看标签之间的关系网络，点击节点可以查看关联的记忆。
