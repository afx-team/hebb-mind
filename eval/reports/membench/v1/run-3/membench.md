# Hebb Mind Evaluation Report: MemBench

**Eval version**: v1
**Mode**: raw_per_turn_pair
**Model (judge)**: N/A
**Temperature**: N/A
**Top-p**: N/A
**Search top_k**: 5
**Concurrency**: 4
**Scenarios**: 1000

## Summary

| Metric | Value |
|--------|-------|
| Total Questions | 1000 |
| Correct | 361 |
| **Accuracy** | **36.1%** |
| Avg Latency | 262.1ms |
| Est. Total Time | 4.4min |

## Accuracy by Category

| Category | Accuracy |
|----------|----------|
| noisy | 36.1% |

## Retrieval Quality

| Metric | Value |
|--------|-------|
| avg_top1_relevance | 0.201 |
| hit@1 | 0.306 |
| hit@10 | 0.362 |
| hit@3 | 0.360 |
| hit@5 | 0.361 |

## Error Analysis

Total errors: 639 / 1000

### membench_noisy_roles_0_0_q (noisy)
- **Q**: I was thinking about going for a hike this weekend, but then again, I remembered I need to finish that book. Did you see the weather forecast? I could swear I saw a post about a new place to explore. What was that restaurant we talked about last week?Oh, what I truly wanted to clarify is,What position does someone who has rock climbing as a hobby hold?
- **Expected**: Customer Service Representative
- **Generated**: 

### membench_noisy_roles_1_1_q (noisy)
- **Q**: I wonder if I left the oven on earlier, or was it the washing machine? Sometimes I forget where I put my keys; they always seem to vanish. Did I remember to water the plants this morning, or was that yesterday? Ah, I need to check my emails later; I can't recall if I sent that report.Wait a minute, what I wanted to ask is,What's the name of the person who has a hobby of model making?
- **Expected**: Aiden Parker
- **Generated**: 

### membench_noisy_roles_3_3_q (noisy)
- **Q**: I was thinking about that book I read last summer, the plot was quite intriguing. Have you heard about the new café that opened downtown? I wonder if they're hiring anyone lately.Wait a minute,What is the contact number for the person with a PhD in education?
- **Expected**: 51000333838
- **Generated**: 

### membench_noisy_roles_4_4_q (noisy)
- **Q**: I was thinking about that one project we discussed last week, but I can't recall the exact details. Did I leave the oven on? You know, sometimes I forget where I put my keys.Hold on, what I actually wanted to understand is: What is the email address for the person with the contact number 70703316548?
- **Expected**: caleb.foster@desertvalleymedical.com
- **Generated**: 

### membench_noisy_roles_5_5_q (noisy)
- **Q**: I went to the park yesterday, it was such a lovely day, and the flowers were blooming beautifully. Oh, what was the name of that restaurant we tried last month? Sometimes I just forget these little details.Sorry about that, what I truly wanted to ask is,What’s the birthday of the person with a Bachelor's degree?
- **Expected**: 07/24
- **Generated**: 

## Configuration

```json
{
  "eval_version": "v1",
  "mode": "raw_per_turn_pair",
  "metric": "turn_level_hit_at_k",
  "search_top_k": 5,
  "concurrency": 4,
  "weight_recency": 0.0,
  "weight_importance": 0.0,
  "weight_relevance": 1.0,
  "num_scenarios": 1000
}
```
