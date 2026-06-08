# PersonaMem

PersonaMem 是一个偏好追踪基准，系统必须推断用户在多个会话之间*为何*改变了想法。我们以 `mode=raw`（不做巩固）运行，以隔离出检索层本身的表现。

## Hebb Mind 在 PersonaMem 上的结果

| Hebb Mind 配置 | 分数 | 来源 |
|---|---|---|
| **v0.1.1 raw，judge = Kimi-K2.5** | **67.6%** QA 准确率（37 题，3 个场景） | `eval/reports/personamem/v1/run-1/personamem.md` |

分类别看，最强的是 `track_full_preference_evolution`（88.9%），最弱的是 `recall_user_shared_facts`（40.0%）—— 也就是说，系统对*变化*的追踪好于对单个*事实*的记忆。把 LoCoMo R@10 推到 94.14%（开启重排序后 95.75%）的那套「逐字保留 + 生产一致写入」的杠杆，应该也能提升这里最弱类别的召回；一次完整的 PersonaMem 重跑已在路线图上。

## 与各竞品的对比

PersonaMem 较新，我们尚未找到 mem0、Letta、MemPalace 或 Zep 在其上公布的数字。本节会随着对比的出现而补充；如果你有可公开的数字，欢迎提交 PR。

| 系统 | 分数 | 来源 |
|---|---|---|
| mem0 | TBD | — |
| Letta | TBD | — |
| MemPalace | TBD | — |
| Zep | TBD | — |
