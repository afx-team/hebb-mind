# 评估基准

Hippocampus 提供了在多个开源数据集上的评估工具，用于衡量记忆系统的检索质量和分类准确性。

## 支持的数据集

| 数据集 | 来源 | 评估重点 |
|--------|------|---------|
| **LoCoMo** | [Maharana et al., 2024] | 长对话中的记忆检索准确率 |
| **LongMemEval** | [Wu et al., 2024] | 长期记忆的召回与推理能力 |
| **ConvoMem** | 社区基准 | 多轮对话中的记忆管理 |
| **PersonaMem** | 社区基准 | 用户画像和偏好记忆 |

## 安装评估依赖

```bash
pip install afx-hippocampus[eval]
```

## 运行评估

```bash
# 运行 LoCoMo 基准
python -m eval.run --benchmark locomo

# 运行 LongMemEval 基准
python -m eval.run --benchmark longmemeval

# 运行所有基准
python -m eval.run --benchmark all
```

## 评估指标

评估工具会输出以下指标：

- **Recall@K** — 前 K 个结果中包含正确记忆的比例
- **Precision@K** — 前 K 个结果中正确记忆的精确率
- **MRR** — 平均倒数排名
- **分区准确率** — 记忆被分类到正确分区的比例（针对巩固功能）

## 自定义评估

评估脚本位于 `eval/` 目录，你可以基于这些脚本添加自定义数据集或评估逻辑：

```
eval/
  run.py           # 评估入口
  benchmarks/      # 各数据集适配器
  metrics.py       # 评估指标计算
```
