# 安装

## 基础安装

```bash
pip install afx-hippocampus
```

**前置条件：** Python >= 3.10。推荐使用 `venv` 或 `conda` 创建独立环境。

## 可选扩展

Hippocampus 通过 pip extras 提供可选功能：

| 扩展 | 安装命令 | 说明 |
|------|---------|------|
| `pg` | `pip install afx-hippocampus[pg]` | PostgreSQL + pgvector 存储后端 |
| `dev` | `pip install afx-hippocampus[dev]` | 开发依赖（pytest, ruff, mypy, 评估基准工具） |

安装全部扩展：

```bash
pip install afx-hippocampus[pg,dev]
```

## 从源码安装

```bash
git clone https://github.com/afx-team/hippocampus.git
cd hippocampus
pip install -e ".[dev]"
```

`-e` 表示可编辑模式，修改代码后无需重新安装。

## 核心依赖

Hippocampus 的主要依赖包括：

- **FastAPI + Uvicorn** — HTTP 服务
- **LiteLLM** — 多模型 LLM 调用
- **sqlite-vec** — SQLite 向量扩展
- **sentence-transformers** — 本地 Embedding 模型
- **NetworkX** — 知识图谱
- **APScheduler** — 定时任务（巩固 + 遗忘）
- **Click + Rich** — CLI 界面

## 验证安装

```bash
hippocampus --version
```

如能正常输出版本号，说明安装成功。接下来执行 `hippocampus init` 初始化项目。
