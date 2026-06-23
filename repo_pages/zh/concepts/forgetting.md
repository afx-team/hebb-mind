---
description: "Hebb Mind 的动态遗忘如何以艾宾浩斯留存曲线衰减 AI 智能体记忆——半衰期由重要度与访问次数拉长，留存率低于阈值即被遗忘。"
---

# 动态遗忘

Hebb Mind 实现了一套以 **艾宾浩斯遗忘曲线** 为模型的动态遗忘机制。每条记忆都有一个随闲置而衰减的 **留存率**（强度）；一旦留存率跌破阈值，记忆即被移除。重要度与反复访问会拉长半衰期，因此高价值、常用的记忆得以保留，而被忽视的低价值记忆逐渐淡出。

## 公式

```
eff_half_life = half_life_days * (1 + k_importance * (importance / 10) + k_access * (access_count / 10))
retention(idle_days) = exp(-idle_days / eff_half_life)
当 retention < threshold 时遗忘   ⇔   idle_days > eff_half_life * ln(1 / threshold)
```

其中：

- **half_life_days** —— 基础特征寿命（天）；一条中性记忆闲置这么多天后衰减到约 37% 留存率
- **k_importance** —— 重要度对半衰期的拉长强度（重要度归一化为 `importance/10`）
- **k_access** —— 反复访问对半衰期的拉长强度（`access_count/10`，不封顶）
- **importance** —— LLM 评定的 0–10 分（0 仅表示不加成，**并非** “删除我” 的信号）
- **access_count** —— 记忆被召回的次数
- **threshold** —— 留存率低于此值即被遗忘（如 `0.3`）

全局下限（`forget_min_retention_days`，默认 1 天）确保任何设置都不会让记忆瞬间删除。

## 工作原理

遗忘任务周期性运行，评估每一条记忆：

1. 由记忆的重要度与访问次数计算有效半衰期
2. 计算其留存率跌破阈值的那一天（`eff_half_life * ln(1/threshold)`）
3. 移除留存率已衰减越过该点的记忆

### 延长记忆寿命的因素

- **高访问次数** —— 每次召回都增大 `access_count`，拉长半衰期（不封顶）
- **高重要度** —— 重要度经由 `k_importance` 乘入半衰期
- **近期访问** —— 留存率在访问后最高，随后衰减

### 缩短记忆寿命的因素

- **从未访问 / 低重要度** —— 仅适用基础半衰期（无加成）
- **长时间未访问** —— 留存率呈指数衰减趋向阈值

## 按区默认值

内置的皮层分区各自带有与其角色匹配的留存默认值；其余（用户分区）使用全局默认值：

| 分区 | `half_life_days` | `k_importance` | `k_access` | `threshold` |
|------|------------------|----------------|------------|-------------|
| `mem_episodic` | 30 | 1.0 | 1.0 | 0.3 |
| `mem_semantic` | 90 | 3.0 | 1.5 | 0.3 |
| `mem_procedural` | 90 | 3.0 | 1.5 | 0.3 |
| `mem_preference` | 180 | 4.0 | 1.5 | 0.3 |
| 用户分区（全局默认） | 60 | 2.0 | 1.5 | 0.3 |
| `mem_hippocampus` | *从不清扫——由巩固流程清空* | | | |

## 配置

| 字段 | 默认值 | 说明 |
|------|--------|------|
| `half_life_days` | `60` | 全局基础半衰期（天） |
| `k_importance` | `2.0` | 全局重要度权重 |
| `k_access` | `1.5` | 全局访问权重 |
| `forget_threshold` | `0.3` | 留存率低于此值即被遗忘 |
| `forget_min_retention_days` | `1` | 任何记忆留存寿命的硬下限（天） |
| `forget_interval_seconds` | `1800` | 遗忘任务运行间隔（30 分钟） |

```bash
# 记得更久（基础半衰期 120 天）
hebb config set half_life_days 120

# 更快遗忘（提高阈值）
hebb config set forget_threshold 0.5

# 降低遗忘运行频率（每小时）
hebb config set forget_interval_seconds 3600
```

## 按分区遗忘

上述值为 **全局兜底**；内置分区另有自己的默认值（见上表），且每个分区均可覆盖任意字段。这些覆盖是 **存于配置（`hebb.json`）的运维策略**，而非数据库数据——因此可在数据库重建后保留。

覆盖项存于 `forgetting_overrides`，以分区 id 为键。`null` 字段继承按区/全局默认值；`enabled: false` 使该分区完全不参与遗忘：

```json
{
  "half_life_days": 60,
  "k_importance": 2.0,
  "k_access": 1.5,
  "forget_threshold": 0.3,
  "forgetting_overrides": {
    "mem_facts":   { "half_life_days": 365, "k_access": 2.0, "threshold": null, "enabled": true },
    "mem_scratch": { "half_life_days": 7,   "enabled": true },
    "mem_pinned":  { "enabled": false }
  }
}
```

更改在 **下一次遗忘清扫** 时生效——调度器每个 tick 都读取实时配置，无需重启。`mem_hippocampus` 工作记忆收件箱从不清扫（由巩固流程清空），因此没有留存参数。

### 在控制台中调参

Web 控制台的 **记忆遗忘** 页面支持可视化调参：

- 按分区拖动 `半衰期` / `重要度权重` / `访问权重` / `阈值`（或关闭遗忘）。
- 实时 **留存曲线** 展示每条曲线的强度随闲置衰减，并标出其跌破阈值、被遗忘的位置。
- 实时 **遗忘矩阵** 是按 重要度 × 访问次数 排布的 *被遗忘所需天数* 热力图，随调参即时重新着色。
- **影响** 面板报告在候选参数下该分区实际会被遗忘的记忆数——用与清扫相同的算法在真实数据上计算。

保存即将覆盖项写回 `hebb.json`。

### API

```bash
# 读取全局默认值 + 每个分区的 override、effective、inherited 值
curl http://localhost:8321/api/v1/admin/forgetting

# 设置覆盖（未设置的字段继承按区/全局默认值）
curl -X PUT http://localhost:8321/api/v1/admin/forgetting/mem_facts \
  -H 'Content-Type: application/json' \
  -d '{"half_life_days": 365, "k_access": 2.0, "enabled": true}'

# 清除覆盖（回到继承按区/全局默认值）
curl -X DELETE http://localhost:8321/api/v1/admin/forgetting/mem_facts

# 预览影响而不删除任何记忆
curl -X POST http://localhost:8321/api/v1/admin/forgetting/mem_facts/preview \
  -H 'Content-Type: application/json' -d '{"half_life_days": 14, "enabled": true}'
```

## 手动触发

立即触发遗忘任务：

```bash
curl -X POST http://localhost:8321/api/v1/admin/forget
```

## 示例场景

**场景 1：高频访问、重要的记忆**（语义区）

重要度 8、访问 10 次、闲置 2 天：

```
eff_half_life = 90 * (1 + 3*(8/10) + 1.5*(10/10)) = 90 * 4.9 = 441 天
retention(2)  = exp(-2 / 441) = 0.995    （远高于 0.3 阈值）
遗忘于         = 441 * ln(1/0.3) ≈ 531 天
```

稳稳保留。

**场景 2：被忽视的低重要度记忆**（情景区）

重要度 3、访问 1 次、闲置 120 天：

```
eff_half_life = 30 * (1 + 1*(3/10) + 1*(1/10)) = 30 * 1.4 = 42 天
retention(120) = exp(-120 / 42) = 0.057   （低于 0.3 阈值）
遗忘于         = 42 * ln(1/0.3) ≈ 51 天
```

闲置已远超约 51 天的遗忘点——将在下次清扫时移除。

## 设计理念

传统记忆系统要么永久保留一切，要么需要手动清理。Hebb Mind 的动态遗忘提供：

- **自动清理** —— 无需手动管理记忆
- **自适应留存** —— 重要、常用的记忆自然存活
- **有界存储** —— 数据库规模长期可控
- **生物学合理性** —— 真正的艾宾浩斯留存曲线，对重要度与访问次数均单调
