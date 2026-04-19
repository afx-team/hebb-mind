---
layout: home

hero:
  name: Hippocampus
  text: Agent 记忆框架
  tagline: 为你的 AI Agent 提供类脑记忆系统 — 自动巩固、检索与遗忘。
  actions:
    - theme: brand
      text: 快速开始
      link: /zh/guide/getting-started
    - theme: alt
      text: GitHub 仓库
      link: https://github.com/afx-team/hippocampus

features:
  - icon: "\U0001F9E0"
    title: 记忆巩固
    details: 自动将记忆分类到语义、情景、偏好、程序性分区 — 模拟人类大脑的记忆系统。
  - icon: "\U0001F504"
    title: 动态遗忘
    details: 基于艾宾浩斯遗忘曲线的 TTL 公式 — 频繁访问的高重要性记忆存活更久，被忽略的自然消失。
  - icon: "\U0001F50D"
    title: 混合检索
    details: 三路并行检索（向量 + 关键词 + 知识图谱），结合时效性、重要性、相关性三维评分。
  - icon: "\U0001F310"
    title: 知识图谱
    details: 巩固过程中自动提取标签构建概念图谱，在 Web 控制台中可视化探索关系。
  - icon: "\u26A1"
    title: 零配置启动
    details: "SQLite 后端：hippocampus init && hippocampus start 即可运行。生产环境可切换 PostgreSQL。"
  - icon: "\U0001F5A5"
    title: Web 控制台
    details: 内置暗色主题管理面板，支持记忆 CRUD、语义搜索、分区管理、图谱可视化。
---

<div class="vp-doc" style="max-width: 688px; margin: 48px auto; padding: 0 24px;">

## 快速安装

```bash
pip install afx-hippocampus
hippocampus init
hippocampus start
# 打开 http://localhost:8321/
```

## 对比

| 特性 | Mem0 | Letta | Zep | **Hippocampus** |
|------|------|-------|-----|-----------------|
| 记忆巩固 | - | - | - | 自动化 |
| 遗忘/衰减 | - | - | 隐式 | 动态 TTL |
| 知识图谱 | - | - | 部分 | 内置 |
| 零配置部署 | - | - | - | SQLite |
| 多模型支持 | 部分 | 部分 | 部分 | 通过 LiteLLM |
| Web 管理界面 | - | 部分 | 部分 | 内置 |

</div>
