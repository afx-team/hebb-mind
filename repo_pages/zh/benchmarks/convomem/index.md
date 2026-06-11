---
description: "Hebb Mind 在 Salesforce ConvoMem 基准上的结果：6 个类别端到端 QA 准确率 73.5%，由 LLM 判分，含分类别明细及与 MemPalace 的对比。"
---

# ConvoMem

[Salesforce/ConvoMem](https://huggingface.co/datasets/Salesforce/ConvoMem) —— 6 个类别共 75,336 条证据项（user facts、assistant facts、changing facts、abstention、preferences、implicit connections）。每一项都提供一个多对话「干草堆」、一个问题、一个自由文本标准答案，以及可推导出该答案的具体证据消息。

我们在 600 项上评测（每类别 100 项 × 6）。MemPalace 公布的数字基于 250 项（每类别 50 项 × 5；他们跳过 `changing_evidence` —— 该类别的 HF 目录树没有 `1_evidence/` 切片）。Hebb 这次运行额外覆盖 `changing_evidence`，办法是对该类别回退到 `2_evidence/` —— 同样的项、同样的数据集、更广的覆盖。

> **生产一致。** 每一项的对话消息都被写入一个专属的、按场景划分的分区，每条消息一条记忆（与 MemPalace 的逐消息写入方式保持一致，确保正面对比时写入对称）。检索走的是生产系统所用的同一个 `/api/v1/search`。

## 如何评测

**指标：端到端 QA 准确率，由 LLM 判分。** 检索从问题所在的分区取出 top-k 记忆 → 判分 LLM（`eval/eval.json` 中的 `llm_model`，当前为开启 thinking 的 Kimi-K2.5）仅使用这些记忆生成答案 → 同一个 LLM 依据 `eval/judge.py` 中的语义等价规则，把生成的答案与数据集的标准答案对照判分。当且仅当判分返回 `correct == true` 时，该问题记为「正确」。

**为何用此指标** —— ConvoMem 公布的指标是 `message_evidences` 文本与检索到的记忆内容之间的逐字子串匹配。我们刻意**不**为 Hebb 报告这个数字，因为它衡量的并非用户真正在意的东西：

1. **生产写入允许对文本做归一化。** `hebb.ingest.noise` 中的 `strip_noise` 步骤会移除系统标签和工具产物；一条记忆的存储文本只要与证据相差哪怕一个字符，就会在子串匹配上得 0 分 —— 即便系统显然「记住」了这个事实并能正确作答。
2. **该指标把检索和重新表述混为一谈。** 一个成功的系统可以跨多条检索到的消息做总结，而不必逐字呈现证据。子串匹配会惩罚这种综合，而综合恰恰是生产级作答所必需的。
3. **端到端 QA 直接衡量生产用户实际得到的结果。** 系统是否正确回答了用户的问题？这才是唯一重要的事。

因此我们使用同一套「先生成、再判分」的流程（`eval/judge.py`），用同样的判分 prompt 和同样的语义等价规则。

## Hebb Mind 在 ConvoMem 上的结果

| Hebb Mind 配置 | QA 准确率 | 来源 |
|---|---|---|
| **v0.1.2 prod-mirror，bge-large-1024，judge = Kimi-K2.5（thinking on）** | **73.5%** QA 准确率（600 题，全部 6 个类别） | `eval/reports/convomem/v3/run-1/convomem.md` |

分类别明细：

| 类别 | QA 准确率 |
|---|---|
| abstention_evidence | 99.0% |
| assistant_facts_evidence | 94.0% |
| user_evidence | 82.0% |
| changing_evidence | 76.0% |
| preference_evidence | 59.0% |
| implicit_connection_evidence | 31.0% |

`abstention_evidence`（99%）是数据集要求给出「我不知道」类答案的地方；我们的判分能正确接受系统在那里的拒答。`implicit_connection_evidence`（31%）是结构上最难的类别 —— 答案需要在两条不同的对话消息之间架桥，而我们每条记忆只对应一条消息，无法合成这座桥。要补上这个缺口，需要的是 LLM 重排序或查询改写，而非更多写入期规则。

被接受为正确的答案上的平均判分置信度为 0.969 —— 判分在接受时很果断，在拒绝时则没那么有把握（这是 LLM-judge 的常见模式）。平均检索延迟（不含 LLM 生成 + 判分时间）为 45.5 ms。

## 与各竞品的对比

MemPalace 的 ConvoMem 数字是子串匹配召回率（5 个类别平均 92.9%）。它与我们的 QA 准确率不可直接比较 —— 不同指标、不同问题。基于上文理由，我们的正面对比不纳入这个子串数字：拿 QA 准确率去比子串召回率，两个方向上都会产生误导。

如果我们将来发布同指标的 ConvoMem 对比，它会是：

- (a) 让 MemPalace 的管线通过我们的 harness，在同样的 600 题上跑一次端到端 QA；或
- (b) 在同一份分类别样本上给出两个系统的子串召回率，并明确标注为「子串代理，非 QA 质量」。

目前两者都尚未发布；基于上述理由，我们不追求那个子串数字。
