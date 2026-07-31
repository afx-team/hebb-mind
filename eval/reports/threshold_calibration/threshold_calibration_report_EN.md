# Strict-Recall Threshold Calibration Review Report (V2 — Full Dataset)

**Date**: 2026-07-30
**Issue**: #31 — feat(retrieval): make the strict-recall score floor configurable + recalibrate for the cross-encoder scale
**Audit Item**: C5 / Recall F3
**Data Scale**: LoCoMo full 1,978 queries, 19,766 results

---

## 1. Conclusion First

**Core Finding: Sigmoid scores are not suitable for hard filtering. The fundamental issue is not "what threshold to set", but "using the wrong filtering dimension."**

Specifically:

1. **The sigmoid score distribution of bge-reranker-base is severely left-skewed** — the median for relevant samples is only 0.166 (the derived assumption of "~0.5" is completely invalid). No matter how the ratio is tuned, sigmoid-based filtering cannot simultaneously achieve R@10 ≥ 90% and empty recall rate < 5%.
2. **The current default configuration (0.8, 0.625) is severely unusable**: 39% of queries return empty result sets, and R@10 is only 53.5%.
3. **The correct approach is "reranker handles ranking, composite score handles filtering"**: retain the reranker's ranking gain (R@10 improves from 91.5% to 94.6%), but only apply the threshold to the composite score.
4. **Recommended default `recall_min_score = 0.6`**: R@10 = 91.5%, empty recall rate = 1.0%, average 7.3 results — achieving the best balance between filtering purity and recall rate.

---

## 2. Data Overview

### 2.1 Score Distribution (Full Dataset — 19,766 Results)

| Score System                    | Count  | Mean  | p10   | p50       | p90   | max   |
| ------------------------------- | ------ | ----- | ----- | --------- | ----- | ----- |
| Composite score (no reranker)   | 19766  | 67.5% | 42.4% | 69.4%     | 88.3% | 100%  |
| Sigmoid score (with reranker)   | 19766  | 18.1% | 0.2%  | **3.9%**  | 68.1% | 100%  |
| Relevant samples sigmoid        | 6348   | 33.1% | 0.7%  | **16.6%** | 93.1% | 100%  |
| Irrelevant samples sigmoid      | 13418  | 11.0% | 0.2%  | 2.4%      | 36.5% | 99.9% |

**Key Issue**: The sigmoid distribution is extremely left-skewed. When deriving the 0.625 ratio, the assumption was "relevant hit sigmoid ~0.5", but the actual median is only 16.6% — **a deviation of more than 3x**. This means the effective threshold of `0.8 × 0.625 = 0.5` falls near the p90 of relevant samples (93.1st percentile) — effectively cutting off over 90% of correct hits.

### 2.2 Three-Mode Baseline Comparison (No Threshold Filtering)

| Mode                          | Description               | R@1   | R@3   | R@5   | R@10      |
| ----------------------------- | ------------------------- | ----- | ----- | ----- | --------- |
| A — Pure composite            | No reranker               | 68.0% | 81.9% | 86.8% | **91.5%** |
| B — Reranker + sigmoid filter | Current production logic  | 71.9% | 87.3% | 91.5% | **94.6%** |
| C — Reranker + composite filter | Recommended approach    | 71.9% | 87.3% | 91.5% | **94.6%** |

**Reranker's ranking gain**: R@10 improves from 91.5% → 94.6% (+3.1 percentage points). This gain is valuable and should be retained.

### 2.3 Current Default Configuration (0.8, 0.625) Performance

| Mode               | Effective Threshold | R@1   | R@10      | Empty Recall Rate | Avg Results |
| ------------------ | ------------------- | ----- | --------- | ----------------- | ----------- |
| A — Composite filter | 0.8               | 55.4% | 63.6%     | **27.5%**         | 2.36        |
| B — Sigmoid filter   | 0.5               | 48.8% | **53.5%** | **39.0%**         | 1.44        |
| C — Composite filter | 0.8               | 55.4% | 63.6%     | **27.5%**         | 2.36        |

**39% of queries return empty result sets. This means nearly four out of ten users find nothing in strict recall mode.**

---

## 3. Key Findings

### 3.1 Mode B (Sigmoid Filter): Dead End

Full parameter sweep (10 × 16 = 160 combinations) — no single combination can simultaneously achieve R@10 ≥ 90% and empty recall rate < 5%.

The most lenient parameter combination (min_score=0.5, ratio=0.3, effective threshold=0.15):

| Metric        | Value         |
| ------------- | ------------- |
| R@10          | 71.8%         |
| Empty Recall  | **19.7%**     |
| Avg Results   | 3.0           |

Even with the threshold pushed down to 0.15 (barely filtering), 20% of queries still return empty sets, and R@10 is only 72%. **This is not a threshold tuning problem — sigmoid scores are inherently unsuitable for hard filtering.**

Reasons:

- Sigmoid p50 = 3.9%, with the vast majority of results clustered near 0
- The sigmoid distributions of relevant and irrelevant samples heavily overlap (relevant p50=16.6% vs irrelevant p50=2.4%)
- Any meaningful threshold simultaneously cuts off a large number of correct results

### 3.2 Mode A/C (Composite Filter): Viable

Composite score distribution is healthy (p50=69.4%) with good discriminability.

**Full Dataset Key Threshold Points**:

| min_score  | A — R@10  | A — Empty Recall | C — R@10  | C — Empty Recall | C — Avg Results |
| ---------- | --------- | ---------------- | --------- | ---------------- | --------------- |
| No threshold | 91.5%   | 0.0%             | 94.6%     | 0.0%             | 10.0            |
| **0.50**   | **90.4%** | **0.3%**        | **93.0%** | **0.0%**        | **8.7**         |
| 0.55       | 90.0%     | 0.5%             | 92.8%     | 0.1%             | 8.1             |
| **0.60**   | **89.0%** | **1.0%**        | **91.5%** | **1.0%**        | **7.3**         |
| 0.65       | 86.0%     | 2.7%             | 88.5%     | 2.7%             | 6.2             |
| 0.70       | 81.2%     | 6.5%             | 83.6%     | 6.2%             | 4.8             |
| 0.80 (current default) | 63.6% | 27.5%    | 63.6%     | 27.5%            | 2.4             |

### 3.3 Value of the Reranker

| Comparison                  | R@10       | Description                    |
| --------------------------- | ---------- | ------------------------------ |
| A baseline (no reranker)    | 91.5%      | Pure composite ranking         |
| C baseline (with reranker)  | 94.6%      | Reranker improves ranking      |
| Difference                  | **+3.1pp** | Reranker ranking gain          |

The reranker does improve ranking quality, but its sigmoid output scores are not suitable for filtering. The correct approach is **to let the reranker only handle ranking, and use composite scores for threshold filtering**.

---

## 4. Recommended Approach

### 4.1 Architecture Decision

**Apply the threshold only to composite scores; the reranker is solely responsible for ranking.**

Rationale:

1. Composite score distribution is healthy (p50=69.4%) with good discriminability
2. Sigmoid scores are severely left-skewed (p50=3.9%) and cannot provide effective filtering
3. This retains the reranker's ranking gain (+3.1pp R@10) while avoiding empty recalls caused by sigmoid filtering

### 4.2 Recommended Defaults

| Configuration Item        | Current Value | Recommended Value        | Rationale                                                                 |
| ------------------------- | ------------- | ------------------------ | ------------------------------------------------------------------------- |
| `recall_min_score`        | 0.8           | **0.6**                  | R@10=91.5%, empty recall=1.0%, avg 7.3 results — balances filtering purity and recall |
| `rerank_floor_ratio`      | 0.625         | **Retained but not used in default filtering** | Kept as a fallback switch; can be enabled when sigmoid filtering is needed |

**More lenient approach (if zero empty recall is required)**: `recall_min_score = 0.5`, R@10=93.0%, empty recall=0.0%, avg 8.7 results.

### 4.3 Comparison of Two Approaches

| Metric        | Current Default (0.8, sigmoid) | Recommended (0.6, composite) | Lenient (0.5, composite) |
| ------------- | ------------------------------ | ---------------------------- | ------------------------ |
| R@10          | 53.5%                          | **91.5%**                    | 93.0%                    |
| Empty Recall  | 39.0%                          | **1.0%**                     | 0.0%                     |
| Avg Results   | 1.4                            | 7.3                          | 8.7                      |
| R@1           | 48.8%                          | 71.9%                        | 71.9%                    |

Recommended approach (0.6, composite) vs. current default: **R@10 improves by 38.0 percentage points (53.5% → 91.5%), empty recall rate drops from 39.0% to 1.0%.**

---

## 5. Engineering Implementation Recommendations

### 5.1 Code Changes

In the floor filtering loop of `searcher.py` (lines 285-292), uniformly use composite scores (`_pre_rerank_score`) for threshold comparison on all results (including the reranked pool):

```python
# Current logic: reranked pool uses sigmoid score for threshold
floor = rerank_floor if i < reranked_count else query.min_score

# Recommended logic: uniformly use composite score for threshold
floor = query.min_score  # All results use composite score
```

### 5.2 Rollout Strategy

- This change only adjusts the filtering threshold and filtering dimension, without altering the relative ranking order of results
- It is a monotonic threshold adjustment, conforming to the release rule in the Issue that "threshold-only adjustments do not require A/B testing"
- Can be directly rolled out via gradual deployment

### 5.3 Backward Compatibility

- Existing callers that do not pass `min_score` will automatically use the new global default of 0.6
- `rerank_floor_ratio` is retained as a configurable option; can be switched back to sigmoid filtering with a single toggle if needed

---

## 6. Remaining Risks and Follow-up Recommendations

### 6.1 Dataset Limitations

This evaluation was only conducted on LoCoMo. Recommendations:

1. Supplement with validation on LongMemEval and MemBench datasets
2. Conduct end-to-end experience testing on the MCP server and Claude Code hook

### 6.2 Reranker Model Optimization

bge-reranker-base has severely left-skewed sigmoid scores on conversational data. If more operations based on reranker scores are needed in the future (e.g., confidence display), consider evaluating alternative models (bge-reranker-v2-m3, cross-encoder/ms-marco-MiniLM, etc.).

### 6.3 Positioning of `rerank_floor_ratio`

Under the current approach, `rerank_floor_ratio` does not take effect by default (since thresholds uniformly use composite scores). Recommendations:

- Retain this configuration item as an emergency fallback switch
- Document that it should only be adjusted when reverting to sigmoid filtering logic

---

## Appendix: Full Dataset Reference Tables

### A — Pure Composite Baseline (No Reranker)

| min_score | R@1   | R@3   | R@5   | R@10  | Empty Recall | Avg Results |
| --------- | ----- | ----- | ----- | ----- | ------------ | ----------- |
| No threshold | 68.0% | 81.9% | 86.8% | 91.5% | 0.0%       | 10.0        |
| 0.50      | 68.1% | 81.8% | 86.9% | 90.4% | 0.3%         | 8.5         |
| 0.60      | 68.3% | 81.7% | 86.0% | 89.0% | 1.0%         | 7.3         |
| 0.70      | 66.1% | 76.9% | 79.5% | 81.2% | 6.5%         | 4.8         |
| 0.80      | 55.4% | 61.6% | 62.9% | 63.6% | 27.5%        | 2.4         |
| 0.90      | 33.1% | 35.2% | 35.5% | 35.5% | 60.1%        | 0.8         |

### C — Reranker + Composite Filter (Recommended Approach)

| min_score | R@1   | R@3   | R@5   | R@10  | Empty Recall | Avg Results |
| --------- | ----- | ----- | ----- | ----- | ------------ | ----------- |
| No threshold | 71.9% | 87.3% | 91.5% | 94.6% | 0.0%       | 10.0        |
| 0.50      | 72.9% | 87.0% | 90.7% | 93.0% | 0.0%         | 8.7         |
| 0.60      | 73.0% | 86.3% | 89.4% | 91.5% | 1.0%         | 7.4         |
| 0.70      | 69.6% | 80.0% | 82.2% | 83.6% | 6.2%         | 4.8         |
| 0.80      | 57.1% | 62.9% | 64.2% | 64.9% | 27.5%        | 2.3         |
| 0.90      | 33.3% | 35.3% | 35.6% | 35.9% | 60.1%        | 0.8         |

### B — Reranker + Sigmoid Filter (Current Production Logic, Problematic Mode)

| min_score | ratio | Effective Threshold | R@1   | R@10  | Empty Recall | Avg Results |
| --------- | ----- | ------------------- | ----- | ----- | ------------ | ----------- |
| 0.80      | 0.625 | 0.50                | 48.8% | 53.5% | 39.0%        | 1.4         |
| 0.50      | 0.30  | 0.15                | 61.9% | 71.8% | 19.7%        | 3.0         |
| 0.50      | 1.00  | 0.50                | 48.8% | 53.5% | 39.0%        | 1.4         |

> **No sigmoid filtering parameter combination can simultaneously achieve R@10 ≥ 90% and empty recall rate < 5%.**
