# MemBench

[import-myself/Membench](https://github.com/import-myself/Membench)（ACL 2025）—— 覆盖 **11 个类别**（simple、highlevel、knowledge_update、comparative、conditional、noisy、aggregative、highlevel_rec、lowlevel_rec、RecMultiSession、post_processing）的多轮对话。每段对话都配有 4 选 1 的 QA，其 `target_step_id` 指向承载答案的那一轮（或几轮）。我们跑的是 **完整 11 类全量评测**（所有 topic，共 11,996 题）。MemPalace 最难的切片是 `noisy`，仅 43.4 % Hit@5 —— 这是公开榜单上最有信息量的「反向窗口」，也是我们领先幅度最大的一类。

> **生产环境一致性。** 每条样本的 `message_list` 按「每个 `[User] X [Assistant] Y` 轮次对一条记忆」写入各自独立的 per-scenario 分区，并把数据集的 `sid` 与跨 session 的 `global_idx` 一并保留在记忆的 metadata 上。检索走与生产系统相同的 `/api/v1/search` 端点。

## 我们怎么评测

**指标：轮次级 Hit@k（双键匹配）。** 对每个问题检索 top-k 记忆，取出它们 metadata 里携带的 `sid` 与 `global_idx` 两个值，看是否有任一 `target_step_id`（数据集指向答案轮次的整数指针）落在这两个集合之中。交集非空即记为「正确」。之所以要双键匹配，是因为数据集对 `target_step_id` 指向哪个整数并不一致 —— 有的类别是 `sid`，有的是 `global_idx`。我们报告 Hit@1 / Hit@3 / Hit@5 / Hit@10。

**为什么用这个指标** —— MemBench 的 ground truth（`target_step_id`）是一个轮次级整数指针，而非自由文本答案。Hit@k 正是数据集作者与 MemPalace 自己的 bench 所测量的；与 MemPalace 公布的 Hit@5 完全同口径。

我们在这个数据集上**不使用** LLM 判分。题目是 4 选 1 单选（A/B/C/D）；即便一个完全没检索到相关轮次的系统，靠瞎猜也能拿 25%，这会把检索失败与生成运气混为一谈，掩盖记忆层真实的表现。

## Hebb Mind 在 MemBench 上

**v0.1.6，生产镜像** —— `all-MiniLM-L6-v2`（384 维）embedding + `BAAI/bge-reranker-base` cross-encoder 重排（两者都是出厂默认），`top_k=5`，11 类全覆盖、所有 topic、共 11,996 题。轮次级双键（sid ∪ global_idx）Hit@k。

| 类别 | Hit@1 | Hit@3 | Hit@5 | Hit@10 | MemPalace Hit@5 | Δ@5 |
|---|---|---|---|---|---|---|
| noisy | 49.0% | 69.9% | **79.4%** | 89.3% | 43.4% | **+36.0 pp** |
| post_processing | 60.1% | 83.6% | **90.3%** | 97.2% | 56.6% | **+33.7 pp** |
| conditional | 53.0% | 75.5% | **86.0%** | 95.9% | 57.3% | **+28.7 pp** |
| highlevel_rec | 48.9% | 78.3% | **89.6%** | 99.1% | 76.2% | **+13.4 pp** |
| highlevel | 61.1% | 96.1% | 99.7% | 100.0% | 95.8% | +3.9 pp |
| simple | 91.3% | 98.0% | 99.4% | 100.0% | 95.9% | +3.5 pp |
| comparative | 89.8% | 99.6% | 100.0% | 100.0% | 98.4% | +1.6 pp |
| knowledge_update | 54.2% | 93.1% | 97.1% | 99.6% | 96.0% | +1.1 pp |
| lowlevel_rec | 89.3% | 98.3% | 99.9% | 100.0% | 99.8% | +0.1 pp |
| aggregative | 91.6% | 98.0% | 99.1% | 99.9% | 99.3% | −0.2 pp |
| RecMultiSession | 60.8% | 94.4% | 99.8% | 100.0% | —— | —— |
| **总体（按题量加权）** | **68.2%** | **89.5%** | **94.6%** | **98.4%** | **80.3%** | **+14.3 pp** |

来源：`eval/reports/membench/v1/run-6` … `run-17`（每个类别一份独立的 run），汇总于 `eval/reports/membench/v1/sweep-summary.md`（可用 `eval/aggregate_membench_sweep.py --min-run 6` 重新生成）。

**这正印证了「重排是关键杠杆」的论点。** Hebb 在简单类别上与 MemPalace 持平（±4 pp 以内），在每一个困难类别上都大幅领先 —— **noisy +36.0 pp、post_processing +33.7 pp、conditional +28.7 pp、highlevel_rec +13.4 pp**。这些恰恰是「逐字存储 + embedding」检索会崩溃的切片：信号里混入干扰项、条件推理、后处理。本地 cross-encoder 对融合后的候选池重新打分，把纯 embedding 相似度埋没的答案轮次重新捞回来 —— 与我们在 LoCoMo、LongMemEval 上的提升同源。

> **为什么是逐类别跑，而不是合并成一次跑。** sqlite-vec 即便带上 `partition_id` 过滤，KNN 仍是对整张向量表做暴力扫描（`partition_id` 只是 metadata 列，不是 partition-key 分片），所以单库 1.12 M 向量会让每次查询变成 10–20 秒的全表扫描。因此每个类别都跑在各自 ≤145 k 向量的独立库里，把分区内检索维持在约 2 秒/查询的区间。Hit@k 不受影响 —— 检索是无状态、确定性的。

## 逐对手对比

- **vs MemPalace** —— 见上表正面对比：同一指标（轮次级 Hit@5 对 `target_step_id`）、同一 MiniLM-384 embedding 档位。Hebb **总体领先 +14.3 pp**，并在 MemPalace **全部四个困难类别上领先 +13 到 +36 pp**，简单类别持平。
