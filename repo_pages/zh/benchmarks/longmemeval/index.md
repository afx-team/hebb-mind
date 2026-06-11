---
description: "Hebb Mind 在 LongMemEval 上的实测：检索 recall@10 达 99.4%，官方判分下端到端 QA 准确率 79.0%，与 Zep、Mem0、MemPalace 同口径对比 AI 智能体记忆。"
---

# LongMemEval

[xiaowu0162/longmemeval](https://huggingface.co/datasets/xiaowu0162/longmemeval) —— 500 个问题，覆盖六类：知识更新、多 session 推理、时序推理、单 session（用户 / 助手 / 偏好）。每个问题都附带一大段历史 session 构成的「干草堆」，数据集明确标注了哪几个 session 含有答案证据。

> **生产环境一致性。** 数据写入调用的正是真实使用中触发的同一套 Claude Code hook 代码路径（`src/hebb/integrations/claude_code/{write,stop}.py`）：每条用户发言写入一条记忆，每轮对话往返写入一条带 ISO 时间戳前缀的记忆。检索也走与 MCP server、CLI、Web 控制台相同的 `/api/v1/search` 端点。每个问题的干草堆装入各自独立的 per-scenario 分区，使检索严格限定在该问题自己的历史中 —— 与数据集预设的「每题一份干净干草堆」协议一致。

## 我们怎么评测

LongMemEval 其实存在两个截然不同的指标，我们**两个都报**，且分开呈现 —— 因为「找到证据」是答对的必要条件，但并不充分。

**1. 检索 Recall@k —— 隔离记忆层。** 对每个问题检索 top-k 记忆，取出它们携带的 `session_id`，看这个集合是否与该问题的 `answer_session_ids` 相交。`recall_any@k == 1.0` 即记为正确；我们报告 R@1 / R@3 / R@5 / R@10 与 NDCG@k，评分阶段不使用 LLM。这正是 LongMemEval 的 ground truth（`answer_session_ids`）所编码的信号，也与 MemPalace 公布的 R@k 完全同口径。

**2. 端到端 QA 准确率 —— LongMemEval 的官方指标。** 检索 → 生成答案 → 由 LLM 判分器对照金标评分。这是 Zep 和 Mem0 所报告的指标。为了让它既可比又不掺水，我们**逐字使用 LongMemEval 的官方作答 prompt**（`src/generation/run_generation.py`）和**官方的分题型判分 prompt**（`get_anscheck_prompt`）—— 不做任何针对基准的 prompt 调优 —— reader 与 judge 都用 DeepSeek-V4-Pro。

> Recall@k 回答的是「证据找到了吗？」，QA 回答的是「答对了吗？」。即便是检索完美的 oracle，用 GPT-4o 作答也只能到约 82%，所以两者不可互换。我们以检索为头条（它隔离了记忆层），同时报告 QA 以便与「以 QA 为主」的系统正面对照。

## Hebb Mind 在 LongMemEval 上

**v0.1.6，生产镜像** —— `all-MiniLM-L6-v2`（384 维）embedding + `BAAI/bge-reranker-base` cross-encoder 重排（两者都是出厂默认），`search_top_k=10`，全量 500 题、六类全覆盖。

| k | R@k（any） | NDCG@k |
|---|---|---|
| 1 | 93.4% | 0.934 |
| 3 | 98.0% | 0.938 |
| 5 | **99.0%** | 0.941 |
| 10 | **99.4%** | 0.943 |

来源：`eval/reports/longmemeval/v3/run-14/longmemeval.md`。R@5（99.0%）是可对比口径的数字，与 MemPalace、Zep 公布时所用的 k 一致。

### 重排的作用

v0.1.6 默认开启重排。固定灌入的语料和 embedding 模型、只切换重排开关：

| 配置 | R@1 | R@5 | R@10 |
|---|---|---|---|
| 仅 `all-MiniLM-L6-v2` | 89.0% | 98.4% | 98.6% |
| `+ bge-reranker-base` | **93.4%** | **99.0%** | **99.4%** |

提升集中在 rank 1（+4.4 pp），随 k 增大而递减 —— 这正是重排的典型特征。≥98% 的问题，正确 session 本就已经落在 top-10 池里，cross-encoder 的任务主要是把它顶到最前：这是「rank-1 精度」的杠杆，而非「召回」的杠杆。

### 分类别（R@10）

| 类别 | R@10 |
|---|---|
| knowledge-update | 100.0% |
| single-session-assistant | 100.0% |
| single-session-preference | 100.0% |
| single-session-user | 100.0% |
| multi-session | 99.2% |
| temporal-reasoning | 98.5% |

`single-session-preference` —— 抽象的推荐类问题（「能推荐些适合我现有摄影装备的配件吗？」）对上具体的用户陈述（「升级相机闪光灯」「想入一个三脚架」），两者几乎零 token 重叠 —— 曾经是本基准的地板。如今检索已到天花板：生产灌库镜像会为每条偏好短语额外写入一条合成记忆（与 `integrations/claude_code/stop.py` 一致），补回了原始 embedding 相似度无法跨越的「查询↔语料」词汇鸿沟，剩下的排序由重排解决。

## 端到端 QA 准确率

同样 500 题，**官方作答 prompt + 官方分题型判分**（`get_anscheck_prompt`），reader 与 judge 均为 DeepSeek-V4-Pro：

| 类别 | QA 准确率 |
|---|---|
| single-session-user | 98.6% |
| single-session-assistant | 92.9% |
| knowledge-update | 80.8% |
| temporal-reasoning | 75.2% |
| single-session-preference | 70.0% |
| multi-session | 67.7% |
| **总计** | **79.0%**（395 / 500） |

来源：`eval/reports/longmemeval/v3/run-16/longmemeval.md`。判分零失败（无 API 限流）。

这里用的是**中立的官方 reader prompt**，并非针对基准调过的版本 —— 所以 79.0% 是检索层所能支撑的**下限**，而非经 prompt 工程拉满的上限。它已经逼近 GPT-4o oracle 上界（82.4%，且该上界假设*检索完美*），差距只有约 3 pp，因为 Hebb 的检索召回本就接近天花板（99.4% @10）。作为对照：我们自己那版较严格的 reader prompt 总分只有 66.6%（偏好类仅 16.7%）—— 换成中立的官方 prompt 后总分 +12.4 pp、偏好类 +53 pp，说明差距来自 prompt 的过度拒答，而非记忆能力。

## 各竞品对比

- [vs MemPalace](./vs-mempalace) —— 检索 R@5（同指标、全量 500）
- [vs Zep / Graphiti](./vs-zep) —— 检索 R@k **与**端到端 QA
- [vs Mem0](./vs-mem0) —— 端到端 QA 准确率
