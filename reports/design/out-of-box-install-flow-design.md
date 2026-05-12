# 开箱即用安装链路设计

## Problem

当前用户路径已经具备基础可用性：`pip install afx-hippocampus`、`hippocampus init`、`hippocampus start` 可以建立本地服务；Claude Code 还有 `hippocampus cc install` 自动注入 hooks 和 MCP。问题在于链路还没有达到“默认效果就好”的产品级顺滑度，尤其是首次安装、模型下载、地区差异和 Codex 支持。

当前主要入口如下：

| 用户场景 | 当前流程 | 现状判断 |
| --- | --- | --- |
| 通用本地服务 | `pip install` -> `hippocampus init` -> `hippocampus start` | 步骤短，但首次启动会触发模型下载，失败后会静默降级为无向量检索 |
| 一键安装 | `curl .../scripts/install.sh \| sh` | 会安装和初始化，但后续提示使用环境变量配置 key，与配置加载实现不一致 |
| Claude Code 自动记忆 | `pip install` -> `init` -> `hippocampus cc install` | 方向正确，是目前最完整的专用链路 |
| MCP 手动接入 | 手写 `.mcp.json` 或客户端配置 | 可用，但不是面向 Claude Code / Codex 的一条命令体验 |
| Codex | 无专门入口 | 缺少 `codex mcp add` 安装命令、验证步骤和 AGENTS.md 使用提示 |

本次检查发现的关键阻塞：

1. 构建出来的 wheel 约 95KB，没有包含 `src/hippocampus/static/`。用户通过 PyPI 安装后，内置 Web 控制台很可能缺失。
2. 默认 embedding 使用 `all-MiniLM-L6-v2`，代码里的缓存检测对该短名返回未缓存；实际下载/缓存通常走 `sentence-transformers/all-MiniLM-L6-v2`。因此启动页和接口可能显示“未下载”，但运行时又可能从 HuggingFace 缓存加载，状态不可信。
3. 本地模型下载失败会在 `create_embedder` 中降级为 `NoopEmbedder`，服务仍然启动；这对“开箱即用”不友好，因为用户会以为默认效果正常，实际语义检索已经关闭。
4. `hf_endpoint` 已经存在，但需要用户手动配置。没有地区识别、下载源测速、下载前提示、断点续传状态或显式预拉取命令。
5. `hippocampus init` 的下一步提示把 LLM 配置放在必经路径，但实际只有记忆巩固需要 LLM；这会误导用户以为没有 key 就无法启动。
6. `scripts/install.sh` 提示 `export HIPPOCAMPUS_LLM_API_KEY` 和 `export HIPPOCAMPUS_PG_URL`，但配置加载器声明并实际采用 `hippocampus.json` 为主，除 `HIPPOCAMPUS_HOME` 和 `HIPPOCAMPUS_URL` 外并不读取这些变量。
7. 设置 `HIPPOCAMPUS_HOME` 后直接运行 `hippocampus init` 时，配置文件目标仍可能落到默认目录，数据目录却被环境变量改到另一个位置，容易形成“配置和数据分家”。
8. README 中 Claude Code 详情链接指向 `advanced/claude-code.html`，实际文档在 `guide/claude-code.md`。
9. PostgreSQL 报错仍提示设置 `HIPPOCAMPUS_PG_URL`，但当前实现应提示 `hippocampus config set pg_url ...`。
10. Codex 是重点服务对象，但仓库中没有 `hippocampus codex install`、Codex 文档页、安装命令或 AGENTS.md 建议。

## Solution

新用户主路径改为 `hippocampus setup`，`init` 保留为离线底层初始化命令。`setup` 默认不启动服务，只完成初始化、语言识别、下载区域识别、模型预下载和验证。

核心原则：

- `language` 决定 embedding 模型。
- `region` 决定 HuggingFace 下载源。
- 二者独立，不能互相推断。

建议主路径：

```bash
pip install -U afx-hippocampus
hippocampus setup
hippocampus start
```

面向重点 agent：

```bash
hippocampus cc install --scope user
hippocampus codex install --scope user
```

### CLI 设计

| 命令 | 作用 |
| --- | --- |
| `hippocampus setup --language auto --region auto --profile default` | 新用户入口：初始化、选择模型、选择下载源、预下载模型、验证 embedding |
| `hippocampus init` | 底层离线初始化：只创建 config、SQLite DB、默认 partitions、knowledge graph |
| `hippocampus model status` | 展示当前模型、维度、缓存路径、下载源、可用状态 |
| `hippocampus model prefetch --model <id> --region auto` | 手动预下载 embedding 模型 |
| `hippocampus doctor` | 检查 Python、config、workspace、静态资源、模型、服务、MCP 配置 |
| `hippocampus codex install --scope user` | 配置 Codex MCP |

### Language 识别

`language` 只表示用户内容语言偏好，不表示网络位置。

识别顺序：

1. 用户显式传参：`--language en|zh|multi`。
2. 已有用户自定义 `embedding_model` 时不覆盖。
3. 读取 OS locale 信息：`LC_ALL`、`LC_MESSAGES`、`LANGUAGE`、`LANG`、`locale.getlocale()`。
4. `en_*` -> `en`。
5. `zh_*` -> `zh`。
6. 其他语言、`C`、`POSIX`、空值、不确定 -> `multi`。

默认模型映射：

| language | 默认模型 | 维度 | 理由 |
| --- | --- | --- | --- |
| `en` | `BAAI/bge-large-en-v1.5` | 1024 | 英语用户优先英语检索质量和模型直觉 |
| `zh` | `BAAI/bge-m3` | 1024 | 中文用户需要多语言和长文本能力 |
| `multi` | `BAAI/bge-m3` | 1024 | 跨语言和不确定场景优先稳妥 |

### Region 识别

`region` 只表示下载网络环境，不表示用户语言。

识别顺序：

1. 用户显式传参：`--region cn|global`。
2. 已有 `hf_endpoint` 时沿用。
3. 并发探测 HuggingFace 官方源和 `https://hf-mirror.com` 的可达性和延迟。
4. 官方源更快且可用 -> `global`。
5. 镜像更快且可用 -> `cn`。
6. 都不可用 -> 保持官方源，并输出修复命令。

下载源映射：

| region | 下载源 |
| --- | --- |
| `global` | HuggingFace 官方源，不设置 `hf_endpoint` |
| `cn` | `https://hf-mirror.com` |
| `auto` | 根据网络探测结果写入或清空 `hf_endpoint` |

典型场景：

```bash
# 英语用户在中国网络
hippocampus setup --language en --region cn

# 中文用户在海外网络
hippocampus setup --language zh --region global

# 默认自动判断
hippocampus setup --language auto --region auto
```

## Trade-offs

英语环境默认使用 `BAAI/bge-large-en-v1.5`，而不是 `BAAI/bge-m3`，可以避免英语母语用户承担不必要的多语言模型心智和下载成本。代价是默认策略不再是单一模型，需要更清楚的 `language` 识别和文档说明。

中文和多语言环境默认使用 `BAAI/bge-m3`，下载体积较大，但符合“默认效果就好”的目标。下载链路必须有镜像、进度、失败恢复和明确状态提示，否则大模型会成为安装阻力。

自动地区识别不应依赖 IP 定位服务。网络测速足够解决下载源选择，也更容易解释和复现。OS locale 可以用于 language 推断，但不能用于 region 主判断。

`setup` 不默认启动服务，避免无意常驻进程和端口占用。用户需要显式运行 `hippocampus start` 或 `hippocampus start -d`。

模型资产不打进 wheel，避免 PyPI 包过大；Web Console 静态资源必须打进 wheel，因为这是“内置 Web 控制台”承诺的一部分。

## Implementation Plan

### P0：修复真实安装不可用风险

1. 在 `pyproject.toml` 中包含 `hippocampus/static/**`、`logo.svg` 等包内静态资源，并新增 wheel 内容检查测试。
2. 修正 README 中 Claude Code 文档链接。
3. 修正 `scripts/install.sh`、PostgreSQL 报错和文档中的环境变量提示，统一使用 `hippocampus config set`。
4. 修正 `hippocampus init` 对 `HIPPOCAMPUS_HOME` 的处理，确保默认初始化目标、配置文件和数据目录一致。

### P1：打磨模型下载和默认效果

1. 新增模型 profile 和维度表。
2. 新增 `hippocampus setup --language auto --region auto --profile default`。
3. 新增 `hippocampus model status/prefetch`，使用统一模型 ID、缓存目录和维度校验。
4. 新增 language 识别器：显式参数、OS locale、兜底 multi。
5. 新增 region 识别器：显式参数、已有配置、网络测速、失败提示。
6. 启动时如果向量模型不可用，应在 CLI、health/status 和 Web Console 中明确显示“语义检索已关闭”，不要只静默降级。

### P2：专门服务 Claude Code 和 Codex

1. 增强 `hippocampus cc install`：检查 `claude` CLI、优先使用官方 MCP 添加命令、继续注入 hooks、提供 `claude mcp list` 验证提示。
2. 新增 `hippocampus codex install`：检查 `codex` CLI、执行 `codex mcp add hippocampus -- hippocampus-mcp`、输出 `codex mcp list` 验证提示。
3. 新增 Codex 文档页和 README 快速命令，说明 MCP-only 能力边界。

### P3：验收矩阵

1. 干净虚拟环境从 wheel 安装，验证 `hippocampus start` 能打开 Web Console。
2. 英语 locale 下 `setup` 选择 `BAAI/bge-large-en-v1.5`。
3. 中文 locale 下 `setup` 选择 `BAAI/bge-m3`。
4. `setup --language en --region cn` 选择英文模型和国内镜像。
5. `setup --language zh --region global` 选择多语言模型和官方源。
6. 无 HuggingFace 缓存、国内镜像、官方源、代理环境分别验证模型下载。
7. 断网启动验证：服务可启动但状态明确提示向量检索不可用。
8. Claude Code 验证：`hippocampus cc install --scope user` 后 `claude mcp list` 可见，hooks 不重复注入。
9. Codex 验证：`hippocampus codex install --scope user` 后 `codex mcp list` 可见，`search_memory` 和 `write_memory` 可调用。
