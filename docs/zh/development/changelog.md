# 更新日志

## [0.1.0] - 2026-04-17

首个公开发布版本。

### 新增功能

- **记忆分区** — 5 个仿脑分区（海马体、语义、情景、偏好、程序性），支持自定义分区
- **记忆巩固** — LLM 驱动的巩固代理，通过 Agentic RAG 将工作记忆处理到长期分区
- **动态遗忘** — 基于访问频率和重要性的指数衰减 TTL 公式
- **知识图谱** — 基于标签共现的概念图谱，使用 NetworkX + JSON 持久化
- **存储后端** — SQLite + sqlite-vec（默认），PostgreSQL + pgvector（可选）
- **REST API** — 完整的记忆和分区 CRUD、语义搜索、图谱查询、管理端点
- **GitHub OAuth** — 可选的多用户认证（默认单用户本地模式）
- **CLI 工具** — `hippocampus init`、`hippocampus start`、`hippocampus status` 等命令
- **Docker 部署** — Dockerfile + docker-compose 一键部署
- **安装脚本** — `curl | sh` 交互式安装，支持后端选择
- **多模型支持** — 通过 LiteLLM 支持 OpenAI、Anthropic、通义千问、智谱 GLM、Kimi
