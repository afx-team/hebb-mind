---
description: "使用一条幂等命令，将 OpenHands、OpenClaw 或 HKUDS OpenHarness 的 Markdown 记忆导入 Hebb Mind。"
---

# 导入 Agent 记忆

Hebb Mind 可以迁移 OpenHands、OpenClaw 和 HKUDS OpenHarness 的确定性 Markdown 记忆语料。导入命令使用 Hebb Mind 的正常写入接口，因此导入内容会使用当前配置的嵌入模型，并进入与普通记忆相同的向量索引和全文索引。

```bash
hebb import <source> <path>
```

对未变化的语料重复执行同一命令是安全的。Hebb Mind 会在记忆元数据中保存来源标识和清洗后内容的哈希，并跳过已经存在的导入键。

## OpenHands

路径可以是仓库根目录、`.openhands` 目录或技能目录：

```bash
hebb import openhands /path/to/project
```

导入器会发现 `.openhands/skills/` 下的仓库技能、`.openhands/microagents/` 下的旧版 microagent，以及 `.agents/skills/` 下的新版 Agent Skills 布局。每个 Markdown 技能会成为一条 `mem_procedural` 记忆，并带有 `external-memory` 和 `openhands` 标签。

## OpenClaw

传入包含记忆文件的 OpenClaw 工作区：

```bash
hebb import openclaw ~/.openclaw/workspace
```

文件会按用途路由：

| 输入 | Hebb Mind 分区 |
|---|---|
| `MEMORY.md` | `mem_hippocampus` |
| `USER.md` | `mem_preference` |
| `SOUL.md` | `mem_procedural` |
| `memory/*.md` 每日记录 | `mem_episodic` |

## HKUDS OpenHarness

传入项目根目录或其中的 `.openharness/memory` 目录：

```bash
hebb import hkuds /path/to/openharness-project
```

导入器读取顶层的 schema-v1 Markdown 主题文件，忽略 `MEMORY.md` 索引和标记为 `disabled: true` 的条目。原始记忆 ID、schema 版本、类型和分类会保存在导入元数据中。工作流和操作步骤分类进入 `mem_procedural`；用户、反馈、项目和参考类型分别路由到偏好、情景或语义分区。

## 清洗和更新

每个文档都会在存储前经过 `clean_user_input()`。系统标签块、围栏代码、粘贴的 HTML 和长 base64 内容会被删除；清洗后为空或只有问候语的内容会被跳过。

幂等键同时包含稳定来源标识和清洗后内容哈希。未变化的文件在重复导入时会被跳过；当文件的有效内容发生变化时，新版本会作为一条新记忆导入，旧版本仍保留，便于明确审查或删除。该命令用于一次性迁移，不提供实时或双向同步。
