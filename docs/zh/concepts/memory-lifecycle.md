# 记忆生命周期

Hippocampus 中的每条记忆都会经历四个阶段：**写入 → 巩固 → 检索 → 遗忘**，模拟人类大脑的记忆处理过程。

## 架构概览

```
                        ┌──────────────────────────────┐
                        │         HIPPOCAMPUS          │
   写入记忆 ──────────► │        （工作记忆）           │
   POST /memories       │   mem_hippocampus 分区       │
                        └─────────────┬────────────────┘
                                      │
                                      ▼
                        ┌──────────────────────────────┐
                        │        巩固代理 (Agent)       │
                        │  1. Agentic RAG 召回相关记忆  │
                        │  2. LLM 分类 + 冲突解决      │
                        │  3. 提取标签 → 知识图谱       │
                        └─────────────┬────────────────┘
                                      │
                    ┌────────┬────────┼────────┬────────┐
                    ▼        ▼        ▼        ▼        ▼
              ┌─────────┐┌────────┐┌────────┐┌────────┐┌────────┐
              │ 语义记忆 ││情景记忆││偏好记忆││程序记忆││ 自定义 │
              │ semantic ││episodic││preferen││procedu ││ custom │
              └─────────┘└────────┘└────────┘└────────┘└────────┘
                    │        │        │        │        │
                    └────────┴────────┼────────┴────────┘
                                      ▼
                        ┌──────────────────────────────┐
                        │        遗忘任务 (Job)         │
                        │  动态 TTL → 过期记忆自动删除   │
                        └──────────────────────────────┘
```

## 阶段一：写入

新记忆通过 REST API 写入，默认进入 `mem_hippocampus`（工作记忆）分区：

```bash
curl -X POST http://localhost:8321/api/v1/memories \
  -H "Content-Type: application/json" \
  -d '{"content": "用户更喜欢 Python 而不是 JavaScript"}'
```

写入时系统自动计算 Embedding 向量，用于后续语义检索。

## 阶段二：巩固

巩固代理按照 `consolidation_interval_seconds` 设定的间隔定期运行（默认 1 小时），也可通过 API 手动触发：

```bash
curl -X POST http://localhost:8321/api/v1/consolidate
```

巩固流程详见 [记忆巩固](./consolidation.md)。

## 阶段三：检索

通过混合检索 API 查询记忆，系统同时执行向量搜索、关键词搜索和图谱搜索，综合评分后返回结果：

```bash
curl -X POST http://localhost:8321/api/v1/search \
  -H "Content-Type: application/json" \
  -d '{"query": "用户的编程语言偏好"}'
```

检索机制详见 [混合检索](./hybrid-search.md)。

## 阶段四：遗忘

遗忘任务按照 `forget_interval_seconds` 设定的间隔定期执行（默认 30 分钟），计算每条记忆的动态 TTL，清理过期记忆：

```bash
curl -X POST http://localhost:8321/api/v1/forget
```

遗忘机制详见 [动态遗忘](./forgetting.md)。

## 记忆的数据结构

每条记忆包含以下字段：

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | string | 唯一标识（UUID） |
| `partition_id` | string | 所属分区 |
| `content` | string | 记忆内容 |
| `importance_score` | float | 重要性评分（0-10） |
| `tags` | list[string] | 标签列表 |
| `metadata` | dict | 附加元数据 |
| `source` | string | 来源：`api`、`agent`、`consolidation` |
| `created_at` | datetime | 创建时间 |
| `updated_at` | datetime | 更新时间 |
| `last_accessed_at` | datetime | 最后访问时间 |
| `access_count` | int | 访问次数 |
| `expires_at` | datetime | 过期时间（由遗忘任务动态计算） |
