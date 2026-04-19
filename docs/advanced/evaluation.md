# Evaluation and Benchmarks

Hippocampus includes an evaluation framework for testing memory system performance against academic benchmark datasets.

## Benchmark Datasets

Four academic benchmark datasets are supported:

| Benchmark | Focus | Description |
|-----------|-------|-------------|
| **LoCoMo** | Long conversation memory | Tests ability to recall information from extended multi-turn conversations |
| **LongMemEval** | Long-term memory evaluation | Evaluates retention and retrieval across long time spans |
| **ConvoMem** | Conversational memory | Measures accuracy of memory in conversational contexts |
| **PersonaMem** | Persona consistency | Tests whether the system maintains consistent persona-related memories |

## Setup

Install the evaluation extras:

```bash
pip install afx-hippocampus[eval]
```

## Running Benchmarks

Run a specific benchmark:

```bash
python -m eval.run --benchmark locomo
```

Available benchmark names:

- `locomo` -- LoCoMo (long conversation memory)
- `longmemeval` -- LongMemEval (long-term memory)
- `convomem` -- ConvoMem (conversational memory)
- `personamem` -- PersonaMem (persona consistency)

Run all benchmarks:

```bash
python -m eval.run --benchmark all
```

## Results

Benchmark results are saved to the `eval/reports/` directory as JSON files with timestamps. Each report includes:

- Dataset name and configuration
- Per-question accuracy scores
- Aggregate metrics (precision, recall, F1)
- Retrieval quality metrics
- Timing information

## Evaluation Metrics

The evaluation framework measures:

- **Retrieval accuracy** -- did the system find the right memories for each query?
- **Answer quality** -- when used with an LLM, does the retrieved context produce correct answers?
- **Latency** -- how fast is retrieval at different dataset sizes?
- **Memory efficiency** -- how does consolidation and forgetting affect long-term accuracy?

## Custom Evaluations

The evaluation framework is extensible. To add a custom benchmark:

1. Create a new dataset loader in `eval/datasets/`
2. Define evaluation metrics in `eval/metrics/`
3. Register the benchmark in `eval/run.py`

See the existing benchmark implementations for reference.

## Why Benchmarks Matter

Memory systems for AI agents are difficult to evaluate because:

- There is no single "correct" memory to retrieve -- relevance is contextual
- Long-term retention must be balanced against storage and latency constraints
- Different applications prioritize different memory characteristics (recency vs. comprehensiveness)

The included benchmarks provide standardized tests that cover the most important aspects of agent memory performance.
