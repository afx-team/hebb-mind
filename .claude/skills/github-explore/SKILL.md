---
name: github-explore
description: Deep-dive into a GitHub repo - analyze architecture, code patterns, and design decisions
user_invocable: true
arguments:
  - name: repo
    description: GitHub repo in owner/repo format (e.g. mem0ai/mem0)
    required: true
  - name: focus
    description: Specific aspect to focus on (e.g. memory architecture, retrieval, API design)
    required: false
---

# GitHub Repo Explorer

Perform a deep analysis of a GitHub repository.

## Instructions

1. Use WebSearch to find the repo's README, documentation, and key discussions
2. Use the GitHub MCP tool (if available) to:
   - List repo structure and key directories
   - Read core source files
   - Check recent issues and PRs for insights
3. Analyze and report:
   - **Overview**: What the project does, star count, maintenance status
   - **Architecture**: How the codebase is organized, key abstractions
   - **Tech Stack**: Languages, frameworks, dependencies
   - **Design Patterns**: Notable patterns and design decisions
   - **API Surface**: Key public interfaces
   - **Strengths**: What the project does well
   - **Weaknesses/Gaps**: Limitations or missing features
4. If a focus area is specified, go deeper on that aspect
