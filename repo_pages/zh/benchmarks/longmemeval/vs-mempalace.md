---
description: "Hebb Mind 与 MemPalace 在 LongMemEval-S 上的同口径检索对比：同题集、同 MiniLM-384 embedding 的 session 级 Recall@5。Hebb 出厂默认即达 99.0% R@5、99.4% R@10，未调参。"
---

# LongMemEval —— Hebb Mind vs MemPalace

MemPalace 与 Hebb Mind 都在全量 500 题的 LongMemEval-S 上报告 **session 级 Recall@5**，算法一致（top-k 里是否含有某个证据 session 的记忆？）。MemPalace 的基准只做检索，所以这是一次干净、同口径的检索对比 —— 同指标、同题集、同样的 MiniLM-384 embedding。

| 系统 | R@5 | Embedding | LLM 重排？ | 备注 |
|---|---|---|---|---|
| MemPalace raw | 96.6% | MiniLM-384 | 否 | 原文 session 文档 |
| MemPalace hybrid v2（时序 + 两遍） | 98.4% | MiniLM-384 | 否 | |
| MemPalace hybrid v3 + Haiku 重排 | 99.4% | MiniLM-384 | 是 | 在所报告的题集上调过 |
| MemPalace hybrid v4（留出 450 题） | 98.4% | MiniLM-384 | 否 | 诚实的非过拟合数字 |
| **Hebb Mind v0.1.6** | **99.0%** | MiniLM-384 | 是（`bge-reranker-base`） | 生产 hook 镜像、全量 500 |

Hebb 的 **99.0% R@5**（R@10 99.4%、R@1 93.4%）处在 MemPalace 区间的顶端 —— 在相同的 MiniLM-384 embedding 上与其最佳的「hybrid + 重排」配置持平，并高于其诚实的留出数字（98.4%）。

来源：Hebb `eval/reports/longmemeval/v3/run-14/longmemeval.md`；MemPalace [基准页面](https://mempalaceofficial.com/reference/benchmarks.html)。

## 关于过拟合

MemPalace 的 hybrid v1–v3 是在他们所报告的同一批 500 题上调出来的；留出的 v4（450 题未见样本上 98.4%）才是诚实的非过拟合数字。Hebb Mind **不**在 LongMemEval 上训练或调参 —— 我们不存在训练/测试集划分（因为我们并不拟合模型），所以 99.0% 是一次用出厂默认配置（与用户拿到的 `hebb.json` 完全相同）跑出的全量结果。

## 检索之外

MemPalace 只报告检索召回。Hebb 另外还跑了官方的端到端 QA 协议 —— 见 [LongMemEval 主页](./)（中立官方 reader 下 79.0%）以及 [vs Zep](./vs-zep) / [vs Mem0](./vs-mem0) 的 QA 对比。
