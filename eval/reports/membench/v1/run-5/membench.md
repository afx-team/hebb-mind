# Hebb Mind Evaluation Report: MemBench

**Eval version**: v1
**Mode**: raw_per_turn_pair
**Model (judge)**: N/A
**Temperature**: N/A
**Top-p**: N/A
**Search top_k**: 10
**Concurrency**: 4
**Scenarios**: 1000

## Summary

| Metric | Value |
|--------|-------|
| Total Questions | 1000 |
| Correct | 893 |
| **Accuracy** | **89.3%** |
| Avg Latency | 2631.7ms |
| Est. Total Time | 43.9min |

## Accuracy by Category

| Category | Accuracy |
|----------|----------|
| noisy | 89.3% |

## Retrieval Quality

| Metric | Value |
|--------|-------|
| avg_top1_relevance | 0.223 |
| hit@1 | 0.490 |
| hit@10 | 0.893 |
| hit@3 | 0.699 |
| hit@5 | 0.794 |

## Error Analysis

Total errors: 107 / 1000

### membench_noisy_roles_10_10_q (noisy)
- **Q**: I was thinking about that charity event last year, it reminded me of my friend's graduation. Does my sister's cake need more frosting? Oh, and I need to check the calendar for the meeting.I got it wrong, what I really meant to ask is: What is the birthday of the person with a Bachelor's degree?
- **Expected**: 08/11
- **Generated**: 

### membench_noisy_roles_110_110_q (noisy)
- **Q**: I overheard someone talking about their favorite cheesesteak spot, it reminded me of this time I visited the city. Did you see that new exhibit at the art museum? I wonder how long it takes to get there from the airport.Oops, actually what I wanted to ask was: What age is someone whose hometown is Philadelphia, PA?
- **Expected**: 30 years old
- **Generated**: 

### membench_noisy_roles_127_127_q (noisy)
- **Q**: You know, I was thinking about that conference last week. Did you hear the speaker's insights on curriculum design? By the way, how old is your sister now? I can't seem to recall her birthday.Sorry about that, what I truly wanted to ask is,What is the birthday of the person with a PhD in education?
- **Expected**: 05/03
- **Generated**: 

### membench_noisy_roles_133_133_q (noisy)
- **Q**: It was an interesting day at the office, and I couldn't help but wonder about the plans for the weekend. Do I need to pick up groceries later? It's always something different. I remember chatting with someone about their favorite movie, but I can't quite recall the title. Time flies, doesn't it?Oh no, I actually wanted to figure out,What is the contact number for someone whose birthday is on 02/16?
- **Expected**: 31005372856
- **Generated**: 

### membench_noisy_roles_137_137_q (noisy)
- **Q**: I was thinking about the concert last week, did you ever find out what time it starts? I should really update my playlist, it's been ages since I added new songs. What do you think about that film everyone is talking about?Oh no, I actually wanted to figure out,What is the work location for someone whose hobby is running?
- **Expected**: Orlando, FL
- **Generated**: 

## Configuration

```json
{
  "eval_version": "v1",
  "mode": "raw_per_turn_pair",
  "metric": "turn_level_hit_at_k",
  "search_top_k": 10,
  "concurrency": 4,
  "weight_recency": 0.0,
  "weight_importance": 0.0,
  "weight_relevance": 1.0,
  "num_scenarios": 1000
}
```
