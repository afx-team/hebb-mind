# 论文综述

Hippocampus 的设计受到多篇学术论文的启发。以下是核心参考文献及其对本项目的影响。

## Generative Agents [Park et al., 2023]

**论文**: *Generative Agents: Interactive Simulacra of Human Behavior*

**核心贡献**: 提出了 Agent 记忆的三维检索评分框架。

**检索公式**:
```
score = w_recency * recency + w_importance * importance + w_relevance * relevance
```

- **时效性 (Recency)**: 基于时间的指数衰减，最近的记忆得分更高
- **重要性 (Importance)**: 由 LLM 对记忆内容的重要性进行 1-10 评分
- **相关性 (Relevance)**: 查询与记忆内容的语义相似度

**对 Hippocampus 的影响**: 我们直接采用了这一三维评分框架作为混合检索的最终排序依据，并使权重可配置。

## MemGPT / Letta [Packer et al., 2023]

**论文**: *MemGPT: Towards LLMs as Operating Systems*

**核心贡献**: 将操作系统的内存管理概念引入 LLM，提出了"Agent 驱动的记忆管理"思想。

- 主记忆 (Main Memory) / 归档记忆 (Archival Memory) 分层
- Agent 自主决定何时将信息在层级间移动
- 通过函数调用实现记忆的读写操作

**对 Hippocampus 的影响**: 我们的巩固代理（Consolidation Agent）借鉴了 Agent 自主管理记忆的思路，但进一步将长期记忆细分为语义、情景、偏好、程序性四个分区。

## CoALA [Sumers et al., 2024]

**论文**: *Cognitive Architectures for Language Agents*

**核心贡献**: 提出了 Language Agent 的认知架构框架，明确了记忆系统的分类体系。

- **情景记忆 (Episodic)**: 具体事件和经历
- **语义记忆 (Semantic)**: 通用知识和事实
- **程序记忆 (Procedural)**: 操作技能和行为模式

**对 Hippocampus 的影响**: 我们的五分区设计直接参考了 CoALA 的分类框架，并增加了偏好记忆分区和海马体（工作记忆）分区。

## Zep / Graphiti [Zep AI, 2024]

**论文/项目**: *Graphiti: Building Real-Time Knowledge Graphs*

**核心贡献**: 将时序知识图谱引入 Agent 记忆系统。

- 记忆不仅存储为向量，还构建实体关系图
- 支持时间感知的图谱查询
- 图谱在检索时提供结构化的上下文

**对 Hippocampus 的影响**: 我们的知识图谱模块受此启发，在巩固过程中自动提取标签并构建共现图谱，用于增强检索的召回和关联发现。

## 综合对比

| 特性 | Generative Agents | MemGPT | CoALA | Zep/Graphiti | **Hippocampus** |
|------|-------------------|--------|-------|-------------|-----------------|
| 记忆分区 | 单一 | 两层 | 三类 | 单一 | 五分区 + 自定义 |
| 检索评分 | 三维 | 相关性 | - | 图谱+向量 | 三维 + 图谱 |
| 巩固机制 | 反思 | Agent函数 | - | 图谱构建 | 巩固代理 |
| 遗忘机制 | 衰减 | 无 | - | 无 | 动态TTL |
| 知识图谱 | 无 | 无 | 无 | 核心 | 内置 |

## 其他参考文献

- [Zhong et al., 2024] *MemoryBank: Enhancing Large Language Models with Long-Term Memory* — 记忆遗忘机制的启发
- [Modarressi et al., 2024] *LoCoMo: A Long Conversational Memory Dataset* — 评估基准之一
- [Wu et al., 2024] *LongMemEval: Benchmarking Long-Context Memory* — 评估基准之一
