# 路线图

## 已完成 (v0.1.0)

- [x] 5 个仿脑记忆分区 + 自定义分区
- [x] LLM 驱动的记忆巩固代理
- [x] 动态遗忘（艾宾浩斯曲线 TTL）
- [x] 三路混合检索（向量 + 关键词 + 图谱）
- [x] 知识图谱（NetworkX + JSON）
- [x] SQLite + sqlite-vec 存储后端
- [x] PostgreSQL + pgvector 存储后端
- [x] REST API（CRUD、搜索、图谱、管理）
- [x] CLI 工具（init / start / stop / status / config）
- [x] Web 控制台（暗色主题）
- [x] Docker 部署
- [x] 多模型支持（LiteLLM）
- [x] GitHub OAuth 认证
- [x] 评估基准测试（LoCoMo、LongMemEval、ConvoMem、PersonaMem）

## 计划中

### v0.2.0 — MCP 与多用户

- [x] MCP Server 集成，支持 Claude Desktop 等客户端
- [ ] 多用户记忆隔离
- [ ] 记忆导入导出（JSON/CSV）
- [ ] 批量巩固性能优化

### v0.3.0 — 增强检索

- [ ] 多语言 Embedding 模型支持
- [ ] 时间感知检索（"上周提到的..."）
- [ ] 对话上下文窗口集成
- [ ] 检索质量自动评估

### v0.4.0 — 图谱增强

- [ ] Neo4j 存储后端
- [ ] 关系类型（不仅是共现）
- [ ] 实体识别与链接
- [ ] 图谱推理能力

### 远期目标

- [ ] 多模态记忆（图片、文件摘要）
- [ ] 分布式部署
- [ ] 插件系统
- [ ] Agent Framework 集成（LangChain、AutoGen 等）
- [ ] 记忆共享与协作
- [ ] 情感标签与记忆重要性学习
- [ ] 记忆压缩与摘要

## 参与讨论

如果你对某个功能特别感兴趣，或有新的想法，欢迎在 [GitHub Discussions](https://github.com/afx-team/hippocampus/discussions) 中参与讨论。
