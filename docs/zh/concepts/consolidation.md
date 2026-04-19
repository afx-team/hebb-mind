# 记忆巩固

记忆巩固是 Hippocampus 的核心机制，灵感来自人类大脑中海马体将短期记忆转化为长期记忆的过程。巩固代理（Consolidation Agent）自动将工作记忆分类到合适的长期分区中。

## 巩固流程

```
mem_hippocampus 中的未处理记忆
         │
         ▼
   ① Agentic RAG 召回
   在已有记忆中搜索相关内容
         │
         ▼
   ② 构建上下文
   将记忆内容 + 可用分区 + 相关记忆
   组装成 LLM prompt
         │
         ▼
   ③ LLM 分类决策
   判断目标分区、提炼内容、评估重要性、提取标签
         │
         ▼
   ④ 冲突检测与解决
   如果与已有记忆冲突：
   - update：更新旧记忆
   - discard：丢弃新记忆（已有更好版本）
   - keep_both：同时保留
         │
         ▼
   ⑤ 写入目标分区 + 更新知识图谱
   从 hippocampus 移动到长期分区
   标签自动添加到知识图谱
```

## 五个系统分区

| 分区 ID | 名称 | 说明 |
|---------|------|------|
| `mem_hippocampus` | 海马体 | 工作记忆收件箱，新记忆先到这里，等待巩固处理 |
| `mem_semantic` | 语义记忆 | 事实、知识、通用信息 |
| `mem_episodic` | 情景记忆 | 经历、事件、上下文交互 |
| `mem_preference` | 偏好记忆 | 用户偏好、喜好、个人设置 |
| `mem_procedural` | 程序记忆 | 技能、操作方法、行为模式 |

这 5 个分区是系统内置的，无法删除。你还可以创建自定义分区来满足特定业务需求。

## 自定义分区

```bash
curl -X POST http://localhost:8321/api/v1/partitions \
  -H "Content-Type: application/json" \
  -d '{
    "id": "mem_project_notes",
    "name": "项目笔记",
    "description": "与当前项目相关的技术决策和进展"
  }'
```

自定义分区的 ID 必须以 `mem_` 开头，长度 5-64 个字符，只能包含小写字母、数字和下划线。

## 手动触发巩固

除了等待定时任务自动执行，你也可以通过 API 立即触发一次巩固：

```bash
curl -X POST http://localhost:8321/api/v1/consolidate
```

响应示例：

```json
{
  "processed": 5,
  "succeeded": 4,
  "failed": 1
}
```

## 调整巩固频率

在 `hippocampus.json` 中修改 `consolidation_interval_seconds`：

```bash
# 每 30 分钟巩固一次
hippocampus config set consolidation_interval_seconds 1800

# 每 2 小时巩固一次
hippocampus config set consolidation_interval_seconds 7200
```

## LLM 依赖

巩固功能依赖 LLM 进行智能分类，使用前请确保已配置 `llm_model` 和 `llm_api_key`。未配置 LLM 时，记忆会留在 `mem_hippocampus` 分区中，不影响读写和搜索。
