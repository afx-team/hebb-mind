# Hebb Mind Evaluation Report: LongMemEval

**Eval version**: v2
**Mode**: raw_production_mirror
**Model (judge)**: N/A
**Temperature**: N/A
**Top-p**: N/A
**Search top_k**: 5
**Concurrency**: 4
**Scenarios**: 500

## Summary

| Metric | Value |
|--------|-------|
| Total Questions | 500 |
| Correct | 421 |
| **Accuracy** | **84.2%** |
| Avg Latency | 321.6ms |
| Est. Total Time | 2.7min |

## Accuracy by Category

| Category | Accuracy |
|----------|----------|
| knowledge-update | 96.2% |
| multi-session | 86.5% |
| single-session-assistant | 100.0% |
| single-session-preference | 36.7% |
| single-session-user | 82.9% |
| temporal-reasoning | 79.7% |

## Retrieval Quality

| Metric | Value |
|--------|-------|
| avg_top1_relevance | 0.289 |
| ndcg@1 | 0.826 |
| ndcg@10 | 0.758 |
| ndcg@3 | 0.765 |
| ndcg@5 | 0.758 |
| no_evidence_excluded | 0.000 |
| recall_all@1 | 0.526 |
| recall_all@10 | 0.738 |
| recall_all@3 | 0.736 |
| recall_all@5 | 0.738 |
| recall_any@1 | 0.826 |
| recall_any@10 | 0.842 |
| recall_any@3 | 0.842 |
| recall_any@5 | 0.842 |

## Error Analysis

Total errors: 79 / 500

### longmemeval_118b2229 (single-session-user)
- **Q**: How long is my daily commute to work?
- **Expected**: 45 minutes each way
- **Generated**: 

### longmemeval_6ade9755 (single-session-user)
- **Q**: Where do I take yoga classes?
- **Expected**: Serenity Yoga
- **Generated**: 

### longmemeval_5d3d2817 (single-session-user)
- **Q**: What was my previous occupation?
- **Expected**: Marketing specialist at a small startup
- **Generated**: 

### longmemeval_0862e8bf (single-session-user)
- **Q**: What is the name of my cat?
- **Expected**: Luna
- **Generated**: 

### longmemeval_ccb36322 (single-session-user)
- **Q**: What is the name of the music streaming service have I been using lately?
- **Expected**: Spotify
- **Generated**: 

## Configuration

```json
{
  "eval_version": "v2",
  "mode": "raw_production_mirror",
  "metric": "session_level_recall_at_k",
  "search_top_k": 5,
  "concurrency": 4,
  "weight_recency": 0.0,
  "weight_importance": 0.0,
  "weight_relevance": 1.0,
  "num_scenarios": 500,
  "no_evidence_excluded": 0
}
```
