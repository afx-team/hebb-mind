# Hebb Mind Evaluation Report: PersonaMem

**Date**: 2026-04-19T10:22:02.140656+00:00
**Mode**: raw
**Model (judge)**: openai/Kimi-K2.5
**Thinking**: enabled
**Temperature**: 1.0
**Top-p**: 0.95
**Search top_k**: 10
**Concurrency**: 2
**Scenarios**: 3

## Summary

| Metric | Value |
|--------|-------|
| Total Questions | 37 |
| Correct | 25 |
| **Accuracy** | **67.6%** |
| Avg Latency | 179.2ms |
| Est. Total Time | 6.6s |

## Accuracy by Category

| Category | Accuracy |
|----------|----------|
| generalizing_to_new_scenarios | 50.0% |
| provide_preference_aligned_recommendations | 60.0% |
| recall_user_shared_facts | 40.0% |
| recalling_the_reasons_behind_previous_updates | 62.5% |
| suggest_new_ideas | 83.3% |
| track_full_preference_evolution | 88.9% |

## Retrieval Quality

| Metric | Value |
|--------|-------|
| avg_top1_relevance | 0.629 |

## Error Analysis

Total errors: 12 / 37

### personamem_e898d03fec68_q0 (recall_user_shared_facts)
- **Q**: I recently attended an event where there was a unique blend of modern beats with Pacific sounds.
- **Expected**: (c) It's great to see such innovative approaches in music. Since you like producing music with software, this must have been quite interesting to experience.
- **Generated**: Yes, you found such live performances exhilarating, noting the palpable energy and cultural unity they created (Turn 13, 48).

### personamem_e898d03fec68_q1 (provide_preference_aligned_recommendations)
- **Q**: I'm planning a weekend getaway and want to try something creatively fulfilling. What would you suggest?
- **Expected**: (d)
- **Generated**: I don't know.

### personamem_e898d03fec68_q4 (recalling_the_reasons_behind_previous_updates)
- **Q**: I've decided I don't enjoy podcasting about music trends anymore.
- **Expected**: (d) I understand your change of heart. Previously, you felt motivated to continue podcasting about music trends after getting positive feedback from your peers. It's normal for interests to evolve over time. If there's another topic you're considering or a reason behind this shift you'd like to explore, I'm here to support your new direction.
- **Generated**: According to your memories, you started a podcast about music trends in 2018 but paused it because it became overwhelming and your passion waned. You later launched a different podcast about the fusion of traditional and electronic music that you described enjoying.

### personamem_1b0b224347ae_q1 (provide_preference_aligned_recommendations)
- **Q**: I'm planning a weekend getaway and want to try something creatively fulfilling. What would you suggest?
- **Expected**: (a)
- **Generated**: I don't know.

### personamem_1b0b224347ae_q4 (recalling_the_reasons_behind_previous_updates)
- **Q**: I've decided I don't enjoy podcasting about music trends anymore.
- **Expected**: (c) I understand your change of heart. Previously, you felt motivated to continue podcasting about music trends after getting positive feedback from your peers. It's normal for interests to evolve over time. If there's another topic you're considering or a reason behind this shift you'd like to explore, I'm here to support your new direction.
- **Generated**: According to your memories, you paused a podcast about music trends in 2018 because it became overwhelming and time-consuming, though you later launched a different podcast about traditional and electronic music fusion that you enjoy.

## Configuration

```json
{
  "llm_model": "openai/Kimi-K2.5",
  "llm_thinking": true,
  "llm_temperature": 1.0,
  "llm_top_p": 0.95,
  "mode": "raw",
  "search_top_k": 10,
  "concurrency": 2,
  "weight_recency": 1.0,
  "weight_importance": 1.0,
  "weight_relevance": 2.0,
  "num_scenarios": 3
}
```
