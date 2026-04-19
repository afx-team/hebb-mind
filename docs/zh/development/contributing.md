# 贡献指南

感谢你有兴趣为 Hippocampus 贡献代码！本文介绍开发环境搭建、代码规范和提交 PR 的流程。

## 开发环境搭建

```bash
# 1. Fork 并克隆仓库
git clone https://github.com/your-username/hippocampus.git
cd hippocampus

# 2. 创建虚拟环境
python -m venv .venv
source .venv/bin/activate

# 3. 安装开发依赖
pip install -e ".[dev]"

# 4. 初始化项目
hippocampus init
```

## 运行测试

```bash
# 运行全部测试
pytest

# 运行特定测试文件
pytest tests/test_storage.py

# 带覆盖率报告
pytest --cov=hippocampus --cov-report=html

# 只运行标记为异步的测试
pytest -m asyncio
```

测试使用 `pytest` + `pytest-asyncio`，异步测试自动识别。

## 代码规范

项目使用以下工具保证代码质量：

### Ruff（代码检查 + 格式化）

```bash
# 检查
ruff check src/

# 自动修复
ruff check --fix src/

# 格式化
ruff format src/
```

配置在 `pyproject.toml` 中：

- 目标版本：Python 3.12
- 行宽：120 字符
- 启用规则：E（错误）、F（pyflakes）、I（import 排序）、N（命名）、W（警告）、UP（现代化）

### Mypy（类型检查）

```bash
mypy src/hippocampus/
```

项目启用了 `strict` 模式，所有公开函数需要完整的类型注解。

## 目录结构

```
src/hippocampus/
  config/          # 配置加载与管理
  models/          # Pydantic 数据模型
  storage/         # 存储后端（SQLite, PostgreSQL）
  embedding/       # Embedding 模型
  retrieval/       # 检索与评分
  graph/           # 知识图谱
  agents/          # 巩固代理、召回代理
  scheduler/       # 定时任务管理
  server/          # FastAPI 服务
    routers/       # API 路由
  cli/             # CLI 命令
    commands/      # 各子命令实现
tests/             # 测试
eval/              # 评估基准
```

## 扩展存储后端

1. 实现 `storage/base.py` 中的 `MemoryStore` 和 `PartitionStore` 协议
2. 添加数据库迁移文件
3. 在 `storage/factory.py` 中注册新后端
4. 在 `pyproject.toml` 中添加可选依赖

## 提交 PR

1. 从 `main` 分支创建功能分支：`git checkout -b feat/your-feature`
2. 编写代码和测试
3. 确保通过所有检查：
   ```bash
   ruff check src/
   mypy src/hippocampus/
   pytest
   ```
4. 提交有意义的 commit message
5. 推送到你的 fork 并创建 Pull Request
6. 在 PR 描述中说明改动内容和动机

## 提交规范

推荐使用以下 commit message 格式：

```
feat: 添加 XX 功能
fix: 修复 XX 问题
docs: 更新文档
test: 添加测试
refactor: 重构 XX 模块
chore: 更新依赖/配置
```

## 报告问题

如果发现 Bug 或有功能建议，欢迎在 [GitHub Issues](https://github.com/afx-team/hippocampus/issues) 中提交。提交 Bug 报告时，请附上：

- Python 版本和操作系统
- 复现步骤
- 预期行为和实际行为
- 错误日志（如有）

## 许可证

贡献代码将遵循 [Apache License 2.0](https://github.com/afx-team/hippocampus/blob/main/LICENSE)。
