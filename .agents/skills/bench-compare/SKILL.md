---
name: bench-compare
description: Compare multiple agent memory systems by analyzing their code, benchmarks, and architecture
user_invocable: true
arguments:
  - name: projects
    description: Comma-separated list of projects to compare (e.g. mem0,zep,letta)
    required: true
  - name: criteria
    description: Comparison criteria (e.g. performance,api-design,scalability)
    required: false
---

# Benchmark & Compare

Compare multiple agent memory projects across key dimensions.

## Instructions

1. For each project in `${projects}`:
   - Search for benchmarks, performance reports, and comparisons
   - Analyze the architecture and API design
   - Check community feedback (GitHub issues, discussions, Reddit, HN)
2. Compare across these default criteria (override with `${criteria}` if provided):
   - **Memory Types**: What types of memory are supported
   - **Retrieval Strategy**: How memories are retrieved (vector, graph, hybrid)
   - **Scalability**: How it handles large memory stores
   - **API Design**: Ease of integration
   - **Ecosystem**: Integrations with LLM frameworks
   - **Performance**: Latency, throughput if data available
   - **Community**: Stars, contributors, activity
3. Output a comparison matrix (markdown table)
4. Provide a recommendation summary with trade-offs
