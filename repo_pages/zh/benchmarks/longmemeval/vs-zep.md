# LongMemEval —— Hebb Mind vs Zep / Graphiti

LongMemEval 是 Zep 主推的公开基准。Zep **两个指标都报** —— 检索召回和端到端 QA 准确率；在同一份 LongMemEval-S 500 题上，Hebb Mind 两项都领先。

## 端到端 QA 准确率

| 系统 | QA 准确率 | 作答 LLM | 判分器 | 延迟 |
|---|---|---|---|---|
| **Hebb Mind v0.1.6** | **79.0%** | DeepSeek-V4-Pro | 官方 `get_anscheck_prompt` | —— |
| Zep | 71.2% | gpt-4o | 官方 | 2.6s |
| _（全上下文基线）_ | 60.2% | gpt-4o | 官方 | 29s |

两者都走官方 LongMemEval QA 协议（检索 → 生成 → 分题型 LLM 判分）。Hebb 用的是**中立的官方 reader prompt** —— 没有任何针对基准的调优 —— 所以 79.0% 是下限，而非经 prompt 工程拉满的上限。

## 检索召回

| 系统 | R@1 | R@3 | R@10 |
|---|---|---|---|
| **Hebb Mind v0.1.6** | **93.4%** | **98.0%** | **99.4%** |
| Zep | 75.9% | 90.2% | 95.5% |

`recall_any@k`，对证据 session 求交。Hebb 在每个深度都领先，rank 1 上差距最大（+17.5 pp）—— 也就是说，当 Hebb 检索到正确 session 时，把它排到首位的概率要高得多。

## 关于数据集划分

两者都在 **LongMemEval-S** 上评测 —— 即标准的 500 题集（`xiaowu0162/longmemeval`，文件 `longmemeval_s`，ICLR 2025 发布版）。（本页早先版本曾称我们用的是「清洗/去重的衍生集」，那是错的 —— 用的就是标准的 S 集，和 Zep 报告所用的同一份。）

来源：Hebb `eval/reports/longmemeval/v3/run-14`（检索）与 `run-16`（QA）；Zep [State of the Art Agent Memory](https://blog.getzep.com/state-of-the-art-agent-memory/)。
