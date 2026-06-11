---
description: "Hebb Mind 管理 API 参考：手动触发记忆巩固与遗忘，查询各分区记忆数、知识图谱规模和调度器状态，重启服务并通过 health/status 探针监控运行状况。"
---

# 管理 API

管理端点用于手动触发系统任务和查看运行状态。

管理端点统一挂载在 `/api/v1/admin/` 下；健康检查与状态接口位于根路径。

## 触发巩固

立即执行一次记忆巩固，处理 `mem_hippocampus` 分区中所有待巩固的记忆，同步返回结果。

```
POST /api/v1/admin/consolidate
```

```bash
curl -X POST http://localhost:8321/api/v1/admin/consolidate
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

按动态 TTL 评估所有记忆并删除已过期的，同步返回删除数量。

```
POST /api/v1/admin/forget
```

```bash
curl -X POST http://localhost:8321/api/v1/admin/forget
```

响应：

```json
{
  "deleted": 12
}
```

## 系统统计

返回各分区的记忆数量、知识图谱规模与调度器状态。

```
GET /api/v1/admin/stats
```

```bash
curl http://localhost:8321/api/v1/admin/stats
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
      "consolidation_job": {"next_run_time": "2026-04-18T18:00:00+08:00"},
      "forgetting_job":    {"next_run_time": "2026-04-17T11:00:00+08:00"}
    }
  }
}
```

## 重启服务

重启 OS 托管的 Hebb Mind 服务。接口**立即返回**，真正的重启延迟约 1 秒后由 launchd / systemd / 任务计划程序触发，确保响应能在进程被杀掉之前发出。客户端应轮询 `GET /health` 等待新进程就绪。

```
POST /api/v1/admin/restart
```

```bash
curl -X POST http://localhost:8321/api/v1/admin/restart
```

响应：

```json
{
  "message": "Restart scheduled",
  "expected_downtime_seconds": 5,
  "poll": "/health"
}
```

如果运行平台不被 service manager 支持（目前支持 macOS、systemd Linux、Windows 任务计划程序），返回 `501 Not Implemented`。Web 控制台在 Embedding 配置 Save 后，如有需要重启的字段会调用此端点。

## 健康检查

用于监控和负载均衡器的轻量探针。

```
GET /health
```

```bash
curl http://localhost:8321/health
```

响应：

```json
{
  "status": "ok",
  "version": "0.1.6"
}
```

## 服务状态

扩展状态：调度器任务和 embedding 就绪情况。

```
GET /status
```

```bash
curl http://localhost:8321/status
```

响应：

```json
{
  "version": "0.1.6",
  "scheduler": {
    "running": true,
    "jobs": {
      "consolidation_job": {"next_run_time": "2026-04-18T18:00:00+08:00"},
      "forgetting_job":    {"next_run_time": "2026-04-17T11:00:00+08:00"}
    }
  },
  "embedding": {
    "enabled": true,
    "provider": "local",
    "model": "all-MiniLM-L6-v2",
    "dimension": 384,
    "available": true
  }
}
```
