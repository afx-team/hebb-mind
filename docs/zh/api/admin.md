# 管理 API

管理端点用于手动触发系统任务和查看运行状态。

## 触发巩固

```
POST /api/v1/consolidate
```

立即执行一次记忆巩固，处理 `mem_hippocampus` 分区中所有待巩固的记忆。

```bash
curl -X POST http://localhost:8321/api/v1/consolidate
```

响应：

```json
{
  "processed": 8,
  "succeeded": 7,
  "failed": 1
}
```

| 字段 | 说明 |
|------|------|
| `processed` | 处理的记忆总数 |
| `succeeded` | 成功巩固的记忆数 |
| `failed` | 巩固失败的记忆数（通常是 LLM 调用失败） |

## 触发遗忘

```
POST /api/v1/forget
```

立即执行一次遗忘清理，删除所有已过期的记忆。

```bash
curl -X POST http://localhost:8321/api/v1/forget
```

响应：

```json
{
  "deleted": 12
}
```

## 系统统计

```
GET /api/v1/stats
```

获取系统运行状态概览。

```bash
curl http://localhost:8321/api/v1/stats
```

响应：

```json
{
  "partitions": [
    {"id": "mem_hippocampus", "name": "Hippocampus", "memory_count": 3, "enabled": true},
    {"id": "mem_semantic", "name": "Semantic Memory", "memory_count": 45, "enabled": true},
    {"id": "mem_episodic", "name": "Episodic Memory", "memory_count": 22, "enabled": true},
    {"id": "mem_preference", "name": "Preference Memory", "memory_count": 15, "enabled": true},
    {"id": "mem_procedural", "name": "Procedural Memory", "memory_count": 8, "enabled": true}
  ],
  "total_memories": 93,
  "graph": {
    "tag_count": 67,
    "edge_count": 142
  },
  "scheduler": {
    "running": true,
    "jobs": {
      "consolidation": {"next_run_time": "2026-04-17T11:00:00Z"},
      "forgetting": {"next_run_time": "2026-04-17T10:30:00Z"}
    }
  }
}
```

## 健康检查

```
GET /health
```

用于监控和负载均衡器的健康检查端点。

```bash
curl http://localhost:8321/health
```

响应：

```json
{
  "status": "ok",
  "version": "0.1.0"
}
```
