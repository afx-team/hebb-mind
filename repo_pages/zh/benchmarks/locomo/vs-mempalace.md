---
description: "LoCoMo 基准上 Hebb Mind 与 MemPalace 的 session 级 hit@10 对比：贴近生产的混合检索达到 94.1% R@10，加本地 cross-encoder 重排升至 95.8%。"
---

# LoCoMo —— Hebb Mind vs MemPalace

MemPalace 在全量 1,986 个 LoCoMo 问题上公布 session 级 Recall@k。他们的指标与我们的（见 [LoCoMo](./)）计算方式相同：把 ground-truth 的 `evidence` 解析为一组 session_id，当任一 GT session 出现在检索结果集中时，该问题即记为正确（session 级 **hit@10**）。

## 生产环境一致性 —— 最重要的说明

**Hebb Mind 的基准测试调用与发布产品相同的代码路径。** 评测 harness 把每一个 LoCoMo 轮次都经由生产环境的 Claude Code 捕获 hook 写入（每轮往返触发 `src/hebb/integrations/claude_code/stop.py`）：逐条发言的记忆使用相同的最小长度过滤与 session 范围去重；逐轮配对的摘要使用相同的 `[<timestamp>] [<role>] …` 格式。检索走的是 Claude Code、MCP server 和 Web 控制台都命中的同一个 `/api/v1/search`。**你在这里看到的 91.4% / 94.1% R@10，就是用户在生产环境中实际得到的 R@10**（`--profile best` bge 档位、重排关闭时为 94.1%）。

**MemPalace 的基准测试并不调用他们的生产管线。** 我们对其仓库的[源码级审计](https://github.com/afx-team/hebb-mind/blob/main/docs/analysis/mempalace-benchmark-deep-dive.md)发现三处具体偏离：

1. **写入粒度** —— 基准测试每个 session（或每个轮次）写入一份逐字原文文档；生产环境则把每条记忆切成 800 字符的窗口。整段 session 的文档比真实用户累积的分块大得多，也在语义上更连贯。
2. **评分管线** —— 生产环境额外加入「closet boost」（对余弦距离 < 1.5 的加权命中按排名做距离削减 `[0.40, 0.25, 0.15, 0.08, 0.04]`）、BM25 混合加权与邻接分块富化。**这些在基准测试中一概不跑。**
3. **Embedding 灵活性** —— 生产环境硬编码 ChromaDB 默认值（`all-MiniLM-L6-v2`），不可换模型；基准测试数字则横扫 MiniLM、bge-large 等多个模型。

逐字引用我们的审计：*「生产管线（closet boost、BM25 混合、邻接扩展）在基准测试中并未被测试。基准数字反映的是基准管线，而非生产检索质量。」*

这对下面的表格很重要：我们是在拿 **prod-mirror 的 Hebb Mind** 对比**仅基准测试的 MemPalace**。MemPalace 的数字是其评测 harness 所能产出的上限，而非其发布系统实际表现的度量。

## 头条 —— 无重排（R@10）

| 系统 | R@10 | Embedding | 备注 |
|---|---|---|---|
| **Hebb Mind（prod-mirror）** | **94.14%** | bge-large-1024 | 全部 10 个场景，评分 1,978 题（排除 8 个对抗性） |
| MemPalace bge-large hybrid | 92.40% | bge-large-1024 | 全量 1,986 题（MemPalace 公布） |
| MemPalace MiniLM hybrid | 92.63% | MiniLM-384 | 全量 1,986 题（从其发布的逐题数据重算 hit@10） |
| Hebb Mind（prod-mirror） | 91.41% | MiniLM-384 | 全部 10 个场景，评分 1,978 题 |

> 关于 MemPalace 的 MiniLM 数字：他们的头条「88.9%」是*逐题平均召回*（`|GT ∩ retrieved| / |GT|`），而非 hit@10。从其发布的数据按我们相同的方式计算，同一次运行是 **92.63% hit@10**（平均召回 0.889）。我们全程以 hit@10 对 hit@10 比较。

**同 embedding、无重排的差值**（唯一诚实的比较）：

| Embedding | Hebb | MemPalace | Δ |
|---|---|---|---|
| bge-large-1024 | 94.14 | 92.40 | **+1.74 pp** |
| MiniLM-384 | 91.41 | 92.63 | **−1.22 pp** |

无重排时，我们在 bge-large 档位领先，但在 MiniLM 上略微落后 —— MemPalace 的 BM25 混合对较弱的 384 维 embedder 调校得很好。我们发布的默认配置用 bge-large，在那里 prod-mirror 的 3 路 RRF（日期邻近度加权、通用英文同义词扩展、前/后轮窗口）已然领先。

## 带重排（R@10）

Hebb Mind 现已附带可选的**本地 cross-encoder 重排**（`BAAI/bge-reranker-base`，`src/hebb/retrieval/rerank/`）—— 不调用 LLM API，在 CPU 上运行。

| 系统 | R@10 | 重排 | 备注 |
|---|---|---|---|
| MemPalace bge-large + Haiku 重排 | 96.30% | LLM（Claude Haiku） | 全量 1,986 题（MemPalace 公布） |
| **Hebb Mind bge-large + bge-reranker-base** | **95.75%** | 本地 cross-encoder | 全部 10 个场景 |
| Hebb Mind MiniLM + bge-reranker-base | 94.69% | 本地 cross-encoder | 全部 10 个场景 |

**同 embedding、带重排的差值：**

| Embedding | Hebb（+ 重排） | MemPalace（无重排） | Δ |
|---|---|---|---|
| bge-large-1024 | 95.75 | 92.40 | **+3.35 pp** |
| MiniLM-384 | 94.69 | 92.63 | **+2.06 pp** |

本地 cross-encoder 提升了每个 embedding 档位（bge-large +1.61、MiniLM +3.28、e5-small +2.43 pp），并扭转了 MiniLM 的劣势 —— MiniLM + 重排（94.69%）现已比 MemPalace 的 MiniLM hybrid 高 +2.06 pp，甚至略胜*我们自己*不带重排的 bge-large（94.14%）。

对比 MemPalace 公布的最强配置（bge-large + **Claude Haiku** LLM 重排，96.30%），我们差 **−0.55 pp** —— 而且我们用一个免费的本地 cross-encoder 而非逐查询的 LLM 调用，就几乎补齐了全部差距。（本页上一版报告为 −3.0 pp，并注明「重排尚未实现；在路线图上」；现已实现。）

## 为什么这个比较是公平的（以及哪里不公平）

公平之处：
- 相同指标（经 evidence 求交的 session 级 hit@10），两侧计算方式一致
- 相同 `top_k=10`
- 相同数据集，**两侧都跑全部 10/10 个 LoCoMo 场景**（在排除 8 个 evidence 为空/无法解析的题目后，1,986 题中评分 1,978 题 —— 与 MemPalace 使用的排除策略相同）

不严格公平之处：
- 我们用 prod-mirror 的逐发言 + 逐配对记忆（每场景约 875 条记忆，共 8,755 条）；MemPalace 每个 session 写入一份文档（每段会话约 19–32 份文档）。在相同 top-k 下我们检索的候选池大得多，这*更难* —— 但指标恰恰是在 session 粒度上评分的，所以这一点对他们的设置有利。
- MemPalace 的 bge-large 与 Haiku 重排数字是他们自己公布的（未发布逐题数据）；只有他们的 MiniLM 运行能按我们的精确指标重算。
- Embedding 容量解释的是*绝对*分数水平，而非*差距*：同 embedding 的差值在 384 维与 1024 维档位都成立。

## 来源

[mempalace benchmark deep-dive §4](https://github.com/afx-team/hebb-mind/blob/main/docs/analysis/mempalace-benchmark-deep-dive.md) —— 对 MemPalace hybrid v1–v5 管线、embedding 扫描、LLM 重排排程，以及催生上文生产一致性说明的「基准 vs 生产」偏离的源码级拆解。Hebb Mind 数字：`eval/reports/locomo/matrix/SUMMARY.md`。
