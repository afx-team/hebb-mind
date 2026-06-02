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
| Avg Latency | 20034.3ms |
| Est. Total Time | 167.0min |

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
| qa_accuracy | 0.790 |
| qa_accuracy_knowledge-update | 0.808 |
| qa_accuracy_multi-session | 0.677 |
| qa_accuracy_single-session-assistant | 0.929 |
| qa_accuracy_single-session-preference | 0.700 |
| qa_accuracy_single-session-user | 0.986 |
| qa_accuracy_temporal-reasoning | 0.752 |
| qa_correct | 395.000 |
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
- **Generated**: Based on the chat history, you have led or are currently leading the following projects:

1. **Leading a team of five engineers** – Since your promotion to senior software engineer three months ago (around February 2023), you have been leading a team of five engineers.
2. **Launching a new product feature in June** – You are currently planning and leading this project, including creating a timeline and Gantt chart.
3. **High-priority project completed two months ahead of schedule** – You led this project, which resulted in a significant increase in company revenue.
4. **Leading a cloud migration effort** – You are currently responsible for leading your company's migration of applications to the cloud.

So, you have led **4 projects** in total (2 completed and 2 currently ongoing).

### longmemeval_gpt4_4929293b (temporal-reasoning)
- **Q**: What was the the life event of one of my relatives that I participated in a week ago?
- **Expected**: my cousin's wedding
- **Generated**: Based on the chat history, you mentioned attending your niece's kindergarten graduation ceremony. However, you said that was "last week" relative to April 15, 2023. Since the current date is June 22, 2023, that event would have been over two months ago, not a week ago.

There is no mention in the chat history of a relative's life event that you participated in a week ago from the current date.

### longmemeval_eac54add (temporal-reasoning)
- **Q**: What was the significant buisiness milestone I mentioned four weeks ago?
- **Expected**: I signed a contract with my first client.
- **Generated**: Based on the chat history, you didn't mention a significant business milestone four weeks ago. 

Looking at the timeline, four weeks before the current date (March 28, 2023) would be around February 28, 2023. The conversations from that period include:

- Your Sundance experience and seeing "The Whale" and "Women Talking" (February 26)
- Discussions about your script and dialogue changes inspired by Sundance films (February 26)
- Questions about improving your 5K time with interval training (March 1)
- Questions about strength training for running (March 1)
- Plant recommendations and snake plant care (March 1)
- Onboarding and training plan tools (March 1)

None of these conversations mention a business milestone. Is it possible you're thinking of a different timeframe or topic?

## Configuration

```json
{
  "eval_version": "v3",
  "mode": "raw_production_mirror",
  "metric": "session_level_recall_at_k+end_to_end_qa",
  "skip_qa": false,
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
