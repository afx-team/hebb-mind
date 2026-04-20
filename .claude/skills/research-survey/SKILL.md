---
name: research-survey
description: Conduct a structured research survey on a topic, combining academic papers and open-source projects
user_invocable: true
arguments:
  - name: topic
    description: The research topic to survey
    required: true
  - name: output
    description: Output file path for the survey report (default writes to repo_pages/surveys/)
    required: false
---

# Research Survey

Conduct a comprehensive research survey combining academic and open-source sources.

## Instructions

1. **Academic Search**: Use WebSearch to find 5-10 recent papers on `${topic}` from arxiv, ACL, NeurIPS, ICML, etc.
2. **Open Source Search**: Use WebSearch to find top GitHub repos related to `${topic}` (sort by stars, recency)
3. **Industry Search**: Look for blog posts, technical reports from major AI labs (OpenAI, Anthropic, Google, Meta)
4. **Synthesize** findings into a structured report:
   - Executive Summary
   - Academic Landscape (key papers, trends)
   - Open Source Landscape (key projects, comparisons)
   - Industry Trends
   - Gap Analysis
   - Recommendations
5. Write the report to `${output}` or `repo_pages/surveys/${topic}-survey.md` if no output specified
6. Use markdown tables for comparisons, include all source links
