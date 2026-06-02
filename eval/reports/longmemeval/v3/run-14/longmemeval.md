# Hebb Mind Evaluation Report: LongMemEval

**Eval version**: v3
**Mode**: raw_production_mirror
**Model (judge)**: openai/DeepSeek-V4-Pro
**Thinking**: disabled
**Temperature**: 1.0
**Top-p**: N/A
**Search top_k**: 10
**Concurrency**: 4
**Scenarios**: 500

## Summary

| Metric | Value |
|--------|-------|
| Total Questions | 500 |
| Correct | 497 |
| **Accuracy** | **99.4%** |
| Avg Latency | 26065.8ms |
| Est. Total Time | 217.2min |

## Accuracy by Category

| Category | Accuracy |
|----------|----------|
| knowledge-update | 100.0% |
| multi-session | 99.2% |
| single-session-assistant | 100.0% |
| single-session-preference | 100.0% |
| single-session-user | 100.0% |
| temporal-reasoning | 98.5% |

## Retrieval Quality

| Metric | Value |
|--------|-------|
| avg_top1_relevance | 0.611 |
| ndcg@1 | 0.934 |
| ndcg@10 | 0.943 |
| ndcg@3 | 0.938 |
| ndcg@5 | 0.941 |
| no_evidence_excluded | 0.000 |
| qa_accuracy | 0.000 |
| qa_accuracy_knowledge-update | 0.000 |
| qa_accuracy_multi-session | 0.000 |
| qa_accuracy_single-session-assistant | 0.000 |
| qa_accuracy_single-session-preference | 0.000 |
| qa_accuracy_single-session-user | 0.000 |
| qa_accuracy_temporal-reasoning | 0.000 |
| qa_correct | 0.000 |
| recall_all@1 | 0.603 |
| recall_all@10 | 0.960 |
| recall_all@3 | 0.927 |
| recall_all@5 | 0.954 |
| recall_any@1 | 0.934 |
| recall_any@10 | 0.994 |
| recall_any@3 | 0.980 |
| recall_any@5 | 0.990 |

## Error Analysis

Total errors: 3 / 500

### longmemeval_6d550036 (multi-session)
- **Q**: How many projects have I led or am currently leading?
- **Expected**: 2
- **Generated**: 

### longmemeval_gpt4_4929293b (temporal-reasoning)
- **Q**: What was the the life event of one of my relatives that I participated in a week ago?
- **Expected**: my cousin's wedding
- **Generated**: 

### longmemeval_eac54add (temporal-reasoning)
- **Q**: What was the significant buisiness milestone I mentioned four weeks ago?
- **Expected**: I signed a contract with my first client.
- **Generated**: 

## Configuration

```json
{
  "eval_version": "v3",
  "mode": "raw_production_mirror",
  "metric": "session_level_recall_at_k+end_to_end_qa",
  "skip_qa": true,
  "search_top_k": 10,
  "concurrency": 4,
  "weight_recency": 0.0,
  "weight_importance": 0.0,
  "weight_relevance": 1.0,
  "llm_model": "openai/DeepSeek-V4-Pro",
  "llm_thinking": false,
  "llm_temperature": 1.0,
  "num_scenarios": 500,
  "no_evidence_excluded": 0
}
```
