# 记忆生命周期

Hippocampus 中的每条记忆都会经历四个阶段：**写入 → 巩固 → 检索 → 遗忘**，模拟人类大脑的记忆处理过程。

## 架构概览

<table style="width:100%; border:none; border-collapse:collapse;">
<tr>
<td align="center" colspan="5" style="padding:6px 14px; background:#1a1a2e; border-radius:8px; color:#e0e0e0; font-weight:600;">
API &middot; MCP &middot; CLI
</td>
</tr>
<tr><td align="center" colspan="5" style="font-size:18px; color:#555;">▼</td></tr>
<tr>
<td align="center" colspan="5" style="padding:10px 18px; background:#16213e; border-radius:8px;">
<b style="color:#00d2ff; font-size:16px;">HIPPOCAMPUS</b><br/>
<span style="color:#888; font-size:12px;">工作记忆收件箱</span>
</td>
</tr>
<tr><td align="center" colspan="5" style="font-size:14px; color:#555; padding:4px 0;">▼&nbsp; 巩固代理 <span style="color:#666; font-size:11px;">(Agentic RAG &middot; 分类 &middot; 冲突解决 &middot; 标签提取)</span></td></tr>
<tr>
<td align="center" style="padding:8px 12px; background:#1b4332; border-radius:6px; min-width:100px;">
<b style="color:#52b788;">语义</b><br/><span style="color:#888; font-size:11px;">知识/事实</span>
</td>
<td align="center" style="padding:8px 12px; background:#3c1642; border-radius:6px; min-width:100px;">
<b style="color:#c77dff;">情景</b><br/><span style="color:#888; font-size:11px;">经历/事件</span>
</td>
<td align="center" style="padding:8px 12px; background:#6b2d5b; border-radius:6px; min-width:100px;">
<b style="color:#ff6b6b;">偏好</b><br/><span style="color:#888; font-size:11px;">喜好/厌恶</span>
</td>
<td align="center" style="padding:8px 12px; background:#2d3a4a; border-radius:6px; min-width:100px;">
<b style="color:#4ecdc4;">程序性</b><br/><span style="color:#888; font-size:11px;">技能/方法</span>
</td>
<td align="center" style="padding:8px 12px; background:#3d3d3d; border-radius:6px; min-width:100px;">
<b style="color:#aaa;">自定义</b><br/><span style="color:#888; font-size:11px;">你的分区</span>
</td>
</tr>
<tr><td align="center" colspan="5" style="font-size:14px; padding:6px 0;">
<span style="color:#555;">▼</span>&nbsp;
<span style="color:#666; font-size:12px;">混合检索</span>
<span style="color:#555;">&nbsp;⟷&nbsp;</span>
<span style="color:#666; font-size:12px;">知识图谱</span>
<span style="color:#555;">&nbsp;⟷&nbsp;</span>
<span style="color:#666; font-size:12px;">动态遗忘 (TTL)</span>
</td></tr>
</table>

## 阶段一：写入

新记忆通过 REST API 写入，默认进入 `mem_hippocampus`（工作记忆）分区：

```bash
curl -X POST http://localhost:8321/api/v1/memories \
  -H "Content-Type: application/json" \
  -d '{"content": "用户更喜欢 Python 而不是 JavaScript"}'
```

写入时系统自动计算 Embedding 向量，用于后续语义检索。

## 阶段二：巩固

巩固代理按照 `consolidation_time` 设定的每日时间运行（默认 `18:00`），也可通过 API 手动触发：

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
