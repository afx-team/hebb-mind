# Hebb Mind Evaluation Report: MemBench

**Eval version**: v1
**Mode**: raw_per_turn_pair
**Model (judge)**: N/A
**Temperature**: N/A
**Top-p**: N/A
**Search top_k**: 5
**Concurrency**: 8
**Scenarios**: 1000

## Summary

| Metric | Value |
|--------|-------|
| Total Questions | 1000 |
| Correct | 794 |
| **Accuracy** | **79.4%** |
| Avg Latency | 3886.4ms |
| Est. Total Time | 64.8min |

## Accuracy by Category

| Category | Accuracy |
|----------|----------|
| noisy | 79.4% |

## Retrieval Quality

| Metric | Value |
|--------|-------|
| avg_top1_relevance | 0.223 |
| hit@1 | 0.490 |
| hit@10 | 0.893 |
| hit@3 | 0.699 |
| hit@5 | 0.794 |

## Error Analysis

Total errors: 206 / 1000

### membench_noisy_roles_3_3_q (noisy)
- **Q**: I was thinking about that book I read last summer, the plot was quite intriguing. Have you heard about the new café that opened downtown? I wonder if they're hiring anyone lately.Wait a minute,What is the contact number for the person with a PhD in education?
- **Expected**: 51000333838
- **Generated**: 

### membench_noisy_roles_10_10_q (noisy)
- **Q**: I was thinking about that charity event last year, it reminded me of my friend's graduation. Does my sister's cake need more frosting? Oh, and I need to check the calendar for the meeting.I got it wrong, what I really meant to ask is: What is the birthday of the person with a Bachelor's degree?
- **Expected**: 08/11
- **Generated**: 

### membench_noisy_roles_33_33_q (noisy)
- **Q**: I saw someone the other day, I think he had a blue jacket on, but I can't recall his name. Did I mention I need to pick up groceries? It's been such a long time since we last met.Hmm, actually my question was this: What is the height of the person with the contact number 31009325688?
- **Expected**: 160cm
- **Generated**: 

### membench_noisy_roles_40_40_q (noisy)
- **Q**: I was thinking about the weather yesterday, it seemed so unpredictable. Did I leave the lights on at home? I wonder how the presentation went. There's that movie I've been meaning to watch, what was it called again?Hmm, actually my question was this: What is the email address of the person whose hobby is cooking?
- **Expected**: sophie.madison@southernfreightlogistics.com
- **Generated**: 

### membench_noisy_roles_60_60_q (noisy)
- **Q**: She mentioned a great coffee shop downtown, but I can't recall the name. Did I forget to send that report? I wonder if the concert starts at seven or eight.I got it wrong, what I really meant to ask is: What is the email address of someone whose hometown is Austin, TX?
- **Expected**: lachlan.hayes@culinarycreationsdc.com
- **Generated**: 

## Configuration

```json
{
  "eval_version": "v1",
  "mode": "raw_per_turn_pair",
  "metric": "turn_level_hit_at_k",
  "search_top_k": 5,
  "concurrency": 8,
  "weight_recency": 0.0,
  "weight_importance": 0.0,
  "weight_relevance": 1.0,
  "num_scenarios": 1000,
  "per_category_hit_at_k": {
    "noisy": {
      "hit@1": 0.49,
      "hit@10": 0.893,
      "hit@3": 0.699,
      "hit@5": 0.794,
      "n": 1000.0
    }
  }
}
```
