# Hebb Mind Evaluation Report: LongMemEval (session-doc ingest)

**Eval version**: v1
**Mode**: raw_production_mirror
**Model (judge)**: N/A
**Temperature**: N/A
**Top-p**: N/A
**Search top_k**: 10
**Concurrency**: 4
**Scenarios**: 500

## Summary

| Metric | Value |
|--------|-------|
| Total Questions | 500 |
| Correct | 419 |
| **Accuracy** | **83.8%** |
| Avg Latency | 132.9ms |
| Est. Total Time | 1.1min |

## Accuracy by Category

| Category | Accuracy |
|----------|----------|
| knowledge-update | 93.6% |
| multi-session | 85.7% |
| single-session-assistant | 98.2% |
| single-session-preference | 40.0% |
| single-session-user | 82.9% |
| temporal-reasoning | 80.5% |

## Retrieval Quality

| Metric | Value |
|--------|-------|
| avg_top1_relevance | 0.289 |
| ndcg@1 | 0.804 |
| ndcg@10 | 0.761 |
| ndcg@3 | 0.766 |
| ndcg@5 | 0.761 |
| no_evidence_excluded | 0.000 |
| recall_all@1 | 0.512 |
| recall_all@10 | 0.752 |
| recall_all@3 | 0.746 |
| recall_all@5 | 0.751 |
| recall_any@1 | 0.804 |
| recall_any@10 | 0.838 |
| recall_any@3 | 0.838 |
| recall_any@5 | 0.838 |

## Error Analysis

Total errors: 81 / 500

### longmemeval_5d3d2817 (single-session-user)
- **Q**: What was my previous occupation?
- **Expected**: Marketing specialist at a small startup
- **Generated**: 

### longmemeval_3b6f954b (single-session-user)
- **Q**: Where did I attend for my study abroad program?
- **Expected**: University of Melbourne in Australia
- **Generated**: 

### longmemeval_726462e0 (single-session-user)
- **Q**: What was the discount I got on my first purchase from the new clothing brand?
- **Expected**: 10%
- **Generated**: 

### longmemeval_b86304ba (single-session-user)
- **Q**: How much is the painting of a sunset worth in terms of the amount I paid for it?
- **Expected**: The painting is worth triple what I paid for it.
- **Generated**: 

### longmemeval_60d45044 (single-session-user)
- **Q**: What type of rice is my favorite?
- **Expected**: Japanese short-grain rice
- **Generated**: 

## Configuration

```json
{
  "eval_version": "v1",
  "mode": "raw_production_mirror",
  "metric": "session_level_recall_at_k",
  "search_top_k": 10,
  "concurrency": 4,
  "weight_recency": 0.0,
  "weight_importance": 0.0,
  "weight_relevance": 1.0,
  "num_scenarios": 500,
  "no_evidence_excluded": 0
}
```
