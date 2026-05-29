# LoCoMo —— Hebb Mind vs Zep

| 系统 | LoCoMo 得分 | 指标 | 来源 |
|---|---|---|---|
| **Hebb Mind** | 95.75%（bge-large + 重排）/ 94.14%（bge-large 默认）/ 91.41%（MiniLM-384），各为全量 1,978 题 | session 级 **Recall@10**（评分时无 LLM） | [LoCoMo](./) |
| **Hebb Mind** | **77.9%**（宽松判分器）/ **73.8%**（严格判分器），cat 1–4 | 端到端 **QA 准确率**（LLM-as-judge）—— 与 Zep 同指标 | [LoCoMo](./) |
| Zep | **75.14% ± 0.17**，cat 1–4 | 端到端 **QA 准确率**（J score） | [Zep 博客](https://blog.getzep.com/lies-damn-lies-statistics-is-mem0-really-sota-in-agent-memory/) |

## 同指标：端到端 QA 准确率

Zep 的 75.14% 是一个 **J score** —— 由 LLM-as-judge 在 LoCoMo 类别 1–4 上对*生成的答案*与 ground truth 评分（排除 446 个对抗性问题）。这正是我们也用来为 Hebb Mind 评分的指标与子集，所以两者**确实**可比：

| 系统 | cat 1–4 QA 准确率 | 判分器 |
|---|---|---|
| **Hebb Mind** | **77.9%** | 标准 LoCoMo QA 判分 prompt（宽松） |
| **Hebb Mind** | **73.8%** | 我们自己的严格判分器 |
| Zep | **75.14% ± 0.17** | LoCoMo QA 判分器 |

应读作一个区间而非单点：**Hebb Mind 视判分器严格程度落在约 74–78%，Zep 为 75.14%** —— 彼此都在噪声范围内。在标准（更宽松）的 LoCoMo QA 判分 prompt 下，Hebb Mind 的 **77.9%** 略微领先；在我们更严格的判分器下则稍低于它。这*不是*受控比较 —— 答案生成的 LLM 不同（我们用 DeepSeek-V4-Pro），且两套完整 QA 管线从未在同一 harness 中运行过。

> **支配两个数字的注意点。** LoCoMo 的 LLM 判分器被记录会接受多达 **约 63% 的故意写错的答案**，且 ground truth 有约 99 个错误/张冠李戴的金标答案（[dial481/locomo-audit](https://github.com/dial481/locomo-audit)，经 [MemPalace #29](https://github.com/MemPalace/mempalace/issues/29)）。在带有那种误差棒的指标上，约 1 pp 的差距毫无意义 —— 应把 Hebb Mind 与 Zep 视为**在 LoCoMo QA 上打平**。

## 检索 vs QA：为什么我们的头条是 95.75% 而 QA 是约 77%

我们的头条 LoCoMo 指标是 **session 级 Recall@10 = 95.75%** —— 检索结果集是否召回了某个 evidence session 的一条记忆？它只评分*检索*，不生成答案。它与我们 QA 准确率之间 18 pp 的差距**不是检索差距**（检索接近天花板）；它来自答案生成模型的推理 —— 几乎全部集中在 LoCoMo 的推理型 `temporal` 类（QA 准确率 33.7%，如*「X 会被视为 Y 吗？」*）与 `multi_hop`（64.5%）。J score 受那种推理能力的上限约束；召回数字则不受。所以 95.75% R@10 与 77.9% QA 描述的是**同一系统在不同维度**上的表现，且只有 QA 这一行可与 Zep 的 J score 比较。

## 关于 Zep 的 LoCoMo 数字

Zep 主要公布的基准是 LongMemEval（Graphiti 在那里报告 >90% R@5 —— 见 [LongMemEval —— vs Zep / Graphiti](/benchmarks/longmemeval/vs-zep)）。在 **LoCoMo** 上，Zep 在一篇[博客文章](https://blog.getzep.com/lies-damn-lies-statistics-is-mem0-really-sota-in-agent-memory/)中报告 **75.14% ± 0.17**（J score）。应将其视为在一次有争议的基准交锋中由单一厂商自报的数字 —— 而非我们在自己 harness 中复跑出来的数字。

## 结论

- **在端到端 QA（Zep 公布的指标）上：** 大致**打平** —— Hebb Mind 约 74–78% vs Zep 在 cat 1–4 上的 75.14% —— 且差距远在 LoCoMo 判分器已知误差棒之内。我们不主张在此击败 Zep。
- **在检索 Recall@10（我们的头条）上：** 无从比较 —— Zep 未公布 LoCoMo 召回数字，我们也未把 Zep 接入自己的 harness 复跑。**不要把 95.75% vs 75.14% 当作正面对决**；它们是不同维度。

如果你有同 harness 的 Zep 数字（无论是 LoCoMo Recall@10，还是把 Hebb Mind 接入 Zep 的 QA harness），欢迎提交 PR。
