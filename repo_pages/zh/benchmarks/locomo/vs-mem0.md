---
description: "Hebb Mind 与 mem0 的 LoCoMo 对比：检索 Recall@10 达 95.75%；在同口径 cat 1-4 子集、逐字复用 mem0 判分 prompt 下，端到端 QA 比 mem0 论文高 11pp。"
---

# LoCoMo —— Hebb Mind vs mem0

我们的头条 LoCoMo 指标是 **session 级检索 Recall@10**（评分回路中无判分器）：

| 系统 | 指标 | 得分 | 来源 |
|---|---|---|---|
| **Hebb Mind**（bge-large + 重排） | Session R@10（全量 1,978 题） | **95.75%** | [LoCoMo](./) |
| **Hebb Mind**（bge-large，默认） | Session R@10（全量 1,978 题） | 94.14% | [LoCoMo](./) |
| **Hebb Mind**（MiniLM-384） | Session R@10（全量 1,978 题） | 91.41% | [LoCoMo](./) |
| mem0 | — | 未公布检索召回数字 | [mem0ai/mem0](https://github.com/mem0ai/mem0) |

mem0 只公布**由 LLM 判分器评分的端到端 QA 准确率**（即「J score」），而非检索召回 —— 因此上表没有同指标的对照行。为了在**他们的**指标上对比，我们在完全相同的问题子集上跑了自己的端到端 QA；下面是这组同口径对照，随后说明为什么这个 QA 数字 —— 无论哪一方 —— 都难以采信。

## 同口径：相同子集（cat 1–4）、相同指标（端到端 QA）

mem0 **只评测 LoCoMo 类别 1–4** —— **446 个对抗性问题被排除**（这是他们声明的惯例「仅在类别 1–4 上评测」，也是标准的 LoCoMo-QA 做法，因为类别 5 是「模型应当拒答」且其 ground-truth 存在已记录的问题）。子集 = **约 1,540 题，而非 1,986 题**。

为了消除判分器作为混淆因素，我们在该子集上**用两种方式对同一批检索并生成的答案**评分。

**(a) 我们自己的判分器**（DeepSeek-V4-Pro，严格 —— 对列表型答案要求全部/除一项外全部命中）：

| Hebb Mind 端到端 QA | 准确率 | 分母 |
|---|---|---|
| 所有类别 | 77.0% | 1,986 |
| **类别 1–4（mem0 的子集）** | **73.8%** | 1,540 |
| 仅对抗性 | 88.3% | 446 |

（我们的全类别头条数字被对抗性这一最强类别拉高了；73.8% 才是可比的数字。）

**(b) mem0 的_原版_判分 prompt**，逐字复制自 [`benchmarks/locomo/prompts.py`](https://github.com/mem0ai/memory-benchmarks/blob/main/benchmarks/locomo/prompts.py) —— 一套宽松得多的评分准则（「命中金标列表中 ≥1 项即判 CORRECT」，日期相差 14 天内通过，复述/额外细节/同指代对象均通过）：

| Hebb Mind，按 mem0 判分 prompt 评分 | cat 1–4 |
|---|---|
| **总计** | **77.9%** |
| 多跳（cat 1） | 72.0% |
| 时序（cat 2） | 72.3% |
| 开放域（cat 3） | 34.4% |
| 单跳（cat 4） | 86.9% |

把我们的判分器换成 mem0 的，数字仅变动 **+4.1 pp**（73.8 → 77.9）：他们的判分器更宽松，但提升空间*并不*在这里。

**(c) 对比 mem0 公布的数字**，相同子集、**相同判分 prompt**：

| 系统 | cat 1–4 QA | 判分器 | vs Hebb 77.9% |
|---|---|---|---|
| **Hebb Mind**（bge-large + 重排） | **77.9%** | mem0 的，逐字 | — |
| mem0 —— arXiv 论文 | 66.9% | mem0 的 | **Hebb +11.0 pp** |
| mem0 —— graph（论文） | 68.4% | mem0 的 | **Hebb +9.5 pp** |
| mem0 —— README / 宣传 | 91.6% | mem0 的 | mem0 +13.7 pp |

在 mem0 **自己的判分 prompt**、**相同的 1,540 题子集**上，我们的检索 + 答案比 mem0 **经同行评审的论文**结果高出 **+11 pp**。上表中唯一高于我们的 mem0 数字是 **README 的 91.6%**，而判分器*无法*解释这个差距（对齐判分器只换来 +4 pp）。它来自两件事，都与检索质量无关：

1. **mem0 的 7 步思维链答案生成 prompt**（实体核验、时序消歧、包含性检查……）。我们用的是普通的一次性答案 prompt；他们的生成 harness 才是出力的关键。
2. **那个 91.6% 无法从 mem0 的公开 harness 复现**（见下一节）。

仍存在的注意点：判分**模型**依然不同（我们用 DeepSeek-V4-Pro；mem0 用 GPT-4o-mini）—— 但判分 **prompt** 现在已是逐字节一致。

## 为什么这个 QA 数字 —— 无论哪一方 —— 都难以采信

**这个排行榜被每一个参与者质疑。** Zep 的审计 [*「Lies, Damn Lies, and Statistics: Is Mem0 Really SOTA in Agent Memory?」*](https://blog.getzep.com/lies-damn-lies-statistics-is-mem0-really-sota-in-agent-memory/) 发现，一个**全上下文基线（约 73% J）击败了 mem0 最佳的 graph 配置（约 68% J）** —— 也就是说，*完全不用记忆系统*得分反而更高，因为 LoCoMo 会话（约 16k–26k token）能装进现代上下文窗口。为求平衡：mem0 发布了反驳，称 Zep 错误配置了他们的系统；而 Zep *自己*的 84% LoCoMo 主张也被另行审计降到了 58.44%（[getzep/zep-papers #5](https://github.com/getzep/zep-papers/issues/5)）。

**mem0 自己的数字无法从公开 harness 复现。** [mem0 #3944](https://github.com/mem0ai/mem0/issues/3944) 报告用 GPT-4o-mini 跑他们的评测时 LLM 得分约 **0.20**（根源是平台用*当前*日期而非数据集时间戳给记忆打戳）；[mem0 #2800](https://github.com/mem0ai/mem0/issues/2800) 在本地复现，得分「显著低于我在论文里看到的」。

**LoCoMo 的 ground truth 本身就是坏的。** 一份公开审计（[dial481/locomo-audit](https://github.com/dial481/locomo-audit)，在 [MemPalace #29](https://github.com/MemPalace/mempalace/issues/29) 中有总结）记录了十段会话中**约 99 个错误/臆造/张冠李戴的答案**（诚实的上限约 93–94%，而非 100%）—— 并且关键在于，**LoCoMo 的 LLM 判分器会接受多达约 63% 的故意写错的答案**。一个对约 63% 的故意错误答案放行的判分器，给*每一个* LoCoMo J-score（mem0 的和我们的都一样）都加上了一个巨大且系统性的误差棒。

这正是我们把**检索召回**作为头条指标的原因：ground truth 就是 `evidence` 的 session 集合，以集合求交评分，回路中没有判分器。

## 一次同指标的检索对比需要什么

要把 mem0 放进上面的 **R@10** 表，我们需要：

1. 把 mem0 接入 Hebb Mind 的 `eval/` 检索召回 harness，使两个系统都通过 evidence 求交得到 session 级 hit@10。
2. 在双方都跑全量 1,978 题（与本站其他地方一致的排除策略）。
3. 公开 mem0 的版本与 embedding 模型。

这在路线图上。如果你已经做过同 harness 的 mem0 运行，欢迎提交 PR。

## 来源

- Mem0 论文 —— [arXiv 2504.19413](https://arxiv.org/abs/2504.19413)
- mem0 判分 + 答案生成 prompt（同判分器测试逐字使用）—— [memory-benchmarks/benchmarks/locomo/prompts.py](https://github.com/mem0ai/memory-benchmarks/blob/main/benchmarks/locomo/prompts.py)
- Zep 对 mem0 的审计 —— [blog.getzep.com](https://blog.getzep.com/lies-damn-lies-statistics-is-mem0-really-sota-in-agent-memory/)
- Zep 自己的主张被审计 —— [getzep/zep-papers #5](https://github.com/getzep/zep-papers/issues/5)
- mem0 可复现性 —— [mem0 #3944](https://github.com/mem0ai/mem0/issues/3944)、[mem0 #2800](https://github.com/mem0ai/mem0/issues/2800)
- LoCoMo ground-truth 审计 —— [dial481/locomo-audit](https://github.com/dial481/locomo-audit)、[MemPalace #29](https://github.com/MemPalace/mempalace/issues/29)
- Hebb Mind 数字 —— `eval/reports/locomo/matrix/SUMMARY.md`（检索）、`eval/reports/locomo_qa/locomo-qa/v1/run-2/`（QA）
