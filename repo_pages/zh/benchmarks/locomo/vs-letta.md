# LoCoMo —— Hebb Mind vs Letta

| 系统 | 得分 | 来源 |
|---|---|---|
| **Hebb Mind** | 95.75% R@10（bge-large + 重排）/ 94.14%（bge-large 默认）/ 91.41%（MiniLM-384），各为全量 1,978 题 | [LoCoMo](./) |
| Letta | 待定 | 在其公开仓库中未找到第一方 LoCoMo 结果 |

## 为什么这一行是「待定」

截至撰写本文，Letta（前身为 MemGPT）未在其主仓库或博客上公布第一方 LoCoMo 结果。已出现一些第三方基准测试，但它们使用了各自定制的判分器与场景数量。

若要给出同行可比的对照行，我们需要把 Letta 接入 Hebb Mind 的 `eval/` harness 运行；相关注意事项参见 [vs mem0](./vs-mem0)。

如果 Letta 此后已公布了应当在此引用的 LoCoMo 数字，欢迎提交 PR。
