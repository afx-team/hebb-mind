# LoCoMo

[snap-research/locomo](https://github.com/snap-research/locomo) —— 两个人设角色之间的多轮会话，涵盖单跳、多跳、时序、开放式与对抗性五类共 1,986 个问题。每段会话跨越 19–32 个 session；问题用于检验记忆系统能否召回若干 session 之前建立的事实。

我们以 **session 级 Recall@10** 报告 LoCoMo —— 这与 MemPalace 公布的指标一致，因此数字可以直接对比。

> **生产环境一致性。** 数据写入调用的正是真实使用中触发的同一套 Claude Code hook 代码路径（`src/hebb/integrations/claude_code/stop.py`，逐轮捕获 hook），检索也走与 MCP server、CLI 和 Web 控制台相同的 `/api/v1/search` 端点。下文的数字就是用户在生产环境中实际得到的结果 —— 而非仅用于评测的理想化配置。关于这与那些「评测流程偏离自身生产管线」的设置有何不同，参见 [vs MemPalace](./vs-mempalace)。

## Session 级 Recall@10

评分阶段不使用 LLM。问题是「检索结果集中是否包含一条带有任一 evidence session 标签的记忆？」。数据写入完全镜像生产环境的 Claude Code hook（`integrations/claude_code/{write,stop}.py`）：每条用户发言写入一条记忆，每轮对话往返写入一条带 ISO 时间戳前缀的记忆，不做分块、不生成图像描述。检索使用 `prev_turns=2 / next_turns=2` 的上下文窗口扩展、基于查询时间戳的日期邻近度加权（`src/hebb/retrieval/temporal_boost.py`），以及 FTS 查询构造器中的通用英文同义词组扩展（`src/hebb/retrieval/fts_query.py`）。可在此之上**可选启用本地 cross-encoder 重排**（`src/hebb/retrieval/rerank/`，`BAAI/bge-reranker-base`）。

### Embedding × 重排扫描（全部 10 个场景，1,978 题）

| 配置 | Embedding | 重排 | R@10 | 平均召回 |
|---|---|---|---|---|
| **prod-mirror + 重排** | bge-large-1024 | bge-reranker-base | **95.75%** | 0.917 |
| prod-mirror + 重排 | MiniLM-384 | bge-reranker-base | 94.69% | 0.902 |
| prod-mirror + 重排 | e5-small-384 | bge-reranker-base | 94.44% | 0.903 |
| **prod-mirror（默认）** | bge-large-1024 | — | **94.14%** | 0.899 |
| prod-mirror | e5-small-384 | — | 92.01% | 0.870 |
| prod-mirror | jina-v3-1024 | — | 92.01% | 0.870 |
| prod-mirror | MiniLM-384 | — | 91.41% | 0.865 |

来源：`eval/reports/locomo/matrix/<config>/locomo/v4/run-1/` 与 `eval/reports/locomo/matrix/SUMMARY.md`。分母是 1,978 而非 1,986，因为有 8 个问题的 `evidence` 为空或无法解析（这是有意设计的对抗性题目）；按 MemPalace 惯例，它们被排除在 R@k 分母之外。

发布的默认配置（`bge-large-1024`，重排关闭）得分 **94.14%**。开启可选的 cross-encoder 重排后提升至 **95.75%** —— 为最佳配置。

### 重排带来的提升

| Embedding | 无重排 | + 重排 | Δ |
|---|---|---|---|
| bge-large-1024 | 94.14% | 95.75% | **+1.61 pp** |
| MiniLM-384 | 91.41% | 94.69% | **+3.28 pp** |
| e5-small-384 | 92.01% | 94.44% | **+2.43 pp** |

重排在每个 embedding 档位都有帮助，且对更廉价的 384 维 embedder 帮助最大 —— 几乎抹平了 embedding 容量差距（MiniLM-384 + 重排，94.69%，略胜于不带重排的 bge-large-1024 的 94.14%）。

### 分类别表现（bge-large-1024 + 重排，头条配置）

| 类别 | R@10 |
|---|---|
| open_ended | 98.2% |
| adversarial | 97.3% |
| multi_hop | 94.1% |
| single_hop | 92.9% |
| temporal | 79.8% |

temporal 落后是因为 LoCoMo 的「时序」问题大多是推理型（「X 会被视为 Y 吗？」）而非锚定在具体时间上，所以日期邻近度加权很少触发；其余每个类别都 ≥ 92%。

## 各竞品对比

- [vs MemPalace](./vs-mempalace) —— 同指标 R@10
- [vs mem0](./vs-mem0) —— 待定（判分器/评分方式不同；同 harness 复跑待进行）
- [vs Letta](./vs-letta) —— 待定（未找到公开的 LoCoMo 结果）
- [vs Zep](./vs-zep) —— 同指标 QA：约打平（Hebb 约 74–78% vs Zep 在 cat 1–4 上的 75.14%）；Zep 未公布 R@10
