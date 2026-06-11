---
description: "Hebb Mind 受艾宾浩斯遗忘曲线启发的动态遗忘机制，按访问次数、重要性和时间衰减计算每条记忆的存活时间，让低价值记忆自动清理、重要记忆长期保留。"
---

# 动态遗忘

Hebb Mind 的遗忘机制受艾宾浩斯遗忘曲线启发，为每条记忆动态计算存活时间（TTL）。频繁访问的重要记忆存活更久，被忽略的低价值记忆自然消失。

## TTL 计算公式

```
TTL = base_ttl * (1 + log(access_count)) * (importance / 5.0) * exp(-decay_factor * days_since_access)
```

其中：

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `base_ttl` | 基础存活时间（小时） | 168（7 天） |
| `access_count` | 记忆被访问的次数 | - |
| `importance` | 重要性评分（0-10） | - |
| `decay_factor` | 衰减因子，越大遗忘越快 | 0.693 |
| `days_since_access` | 距离上次访问的天数 | - |

## 公式解读

- **访问频率加成** `(1 + log(access_count))`：访问次数越多，TTL 越长，但增长速度递减
- **重要性加成** `(importance / 5.0)`：重要性 5 为基准，10 分记忆的 TTL 是 5 分记忆的 2 倍
- **时间衰减** `exp(-decay_factor * days)`：随时间指数衰减，长时间未访问的记忆 TTL 快速缩短

## 示例

一条 importance=8、被访问 10 次、3 天未访问的记忆：

```
TTL = 168 * (1 + log(10)) * (8 / 5) * exp(-0.693 * 3)
    = 168 * 3.30 * 1.6 * 0.125
    ≈ 110.9 小时
```

而一条 importance=3、只被访问 1 次、7 天未访问的记忆：

```
TTL = 168 * (1 + log(1)) * (3 / 5) * exp(-0.693 * 7)
    = 168 * 1.0 * 0.6 * 0.0078
    ≈ 0.79 小时
```

后者将很快被清理。

## 遗忘任务运行机制

遗忘任务按 `forget_interval_seconds` 间隔定期执行（默认 30 分钟）：

1. 遍历所有记忆
2. 根据公式计算每条记忆的 `expires_at`
3. 删除已过期的记忆

手动触发：

```bash
curl -X POST http://localhost:8321/api/v1/admin/forget
```

响应：

```json
{
  "deleted": 12
}
```

## 调整参数

```bash
# 延长基础存活时间到 2 周
hebb config set base_ttl_hours 336

# 降低衰减速度（记忆消失更慢）
hebb config set decay_factor 0.3

# 加快遗忘任务检查频率（每 10 分钟）
hebb config set forget_interval_seconds 600
```

## 设计思考

人类大脑不会记住所有信息，遗忘是正常且必要的认知机制。通过动态 TTL，Hebb Mind 实现了：

- **自适应保留**：重要且常用的记忆自然存活更久
- **自动清理**：低价值记忆不会无限积累
- **可调节性**：通过参数调整可以适应不同场景的记忆需求
