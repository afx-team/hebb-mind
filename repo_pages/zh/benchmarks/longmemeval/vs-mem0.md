# LongMemEval —— Hebb Mind vs Mem0

Mem0 在 LongMemEval 上的头条指标是**端到端 QA 准确率**（官方的「检索 → 生成 → LLM 判分」协议）。Mem0 不公布 session 级检索召回，所以这场正面对照只能在 QA 上进行。

| 系统 | QA 准确率 | 作答 LLM | 作答 prompt |
|---|---|---|---|
| Mem0 | ~85–94%\* | gpt-4o / 多种 | 重度工程化（[已公开](https://github.com/mem0ai/memory-benchmarks/blob/main/benchmarks/longmemeval/prompts.py)） |
| **Hebb Mind v0.1.6** | **79.0%** | DeepSeek-V4-Pro | 中立的**官方** reader |

\* Mem0 公布的数字随来源与设置而变 —— 他们自家研究报告约 93–94%，第三方复现则落在约 85%。

## 该怎么客观地读这张表

直接比数字会有误导，原因有两点：

1. **作答 prompt 才是主要变量。** Mem0 的答案生成 prompt 是公开的，而且*极度*工程化 —— 13 条编号规则、一段思维链草稿区，外加专门的个性化 / 反拒答章节。Hebb 的 79.0% 用的是**中立官方 reader prompt**，零基准调优。这个杠杆我们在自己的栈上直接测过：把我们那版较严格的 reader prompt 换成中立官方版，**总分 +12.4 pp**、**偏好类 +53 pp**。也就是说，单是 reader prompt 工程就能把数字撬动 10 pp 以上 —— 与记忆质量无关。

2. **检索不是 Hebb 的瓶颈。** Mem0 不报检索召回；Hebb 的检索接近天花板 —— **99.4% recall@10**，高于 Zep 的 95.5%。证据几乎总能被检索到，真正给 Hebb 的 QA 封顶的是那条（刻意不调的）作答 prompt，而非记忆层。

所以 Mem0 在这个基准上的优势是 **reader prompt 工程，而非记忆质量**。我们以未调优的 79.0% 作为诚实的下限；若在 Hebb 更强的检索（99.4% recall@10）之上配一套同等工程化的 reader prompt，按理足以抹平这道差距。

来源：Hebb `eval/reports/longmemeval/v3/run-16`（QA）与 `run-14`（检索）；Mem0 [memory-benchmarks](https://github.com/mem0ai/memory-benchmarks)、[research](https://mem0.ai/research)。
