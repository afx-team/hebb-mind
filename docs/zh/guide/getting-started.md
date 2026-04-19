# 快速开始

本页介绍如何在几分钟内安装并启动 Hippocampus 记忆服务。

## 环境要求

- Python >= 3.12
- pip（推荐使用虚拟环境）

## 安装

```bash
pip install afx-hippocampus
```

## 初始化项目

```bash
hippocampus init
```

该命令会在当前目录生成：

- `hippocampus.json` — 配置文件
- `hippocampus.db` — SQLite 数据库（含默认分区）
- `knowledge_graph.json` — 空的知识图谱

## 配置 LLM

记忆巩固功能需要一个 LLM 后端。通过 CLI 设置 API 密钥和模型：

```bash
hippocampus config set llm_api_key sk-your-key
hippocampus config set llm_model openai/gpt-4o-mini
```

Hippocampus 通过 LiteLLM 支持 OpenAI、Anthropic、通义千问、智谱 GLM、Kimi 等主流模型，只需修改 `llm_model` 即可切换。

## 启动服务

```bash
hippocampus start
```

服务默认监听 `http://localhost:8321/`，打开浏览器即可使用内置的 Web 控制台。

## 一键安装

如果你不想手动操作，可以使用安装脚本一步完成：

```bash
curl -fsSL https://raw.githubusercontent.com/afx-team/hippocampus/main/scripts/install.sh | sh
```

## 验证安装

服务启动后，向 API 写入一条测试记忆：

```bash
curl -X POST http://localhost:8321/api/v1/memories \
  -H "Content-Type: application/json" \
  -d '{"content": "用户喜欢深色主题", "importance_score": 7}'
```

然后搜索：

```bash
curl -X POST http://localhost:8321/api/v1/search \
  -H "Content-Type: application/json" \
  -d '{"query": "主题偏好"}'
```

## 下一步

- [安装详情](./installation.md) — 了解可选依赖和从源码安装
- [配置](./configuration.md) — 完整配置项说明
- [记忆生命周期](../concepts/memory-lifecycle.md) — 理解系统核心机制
