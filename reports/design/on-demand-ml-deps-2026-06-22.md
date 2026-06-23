# Hebb Mind 重依赖按需安装设计 (2026-06-22)

- **日期**: 2026-06-22
- **范围**: 解决 `pip install hebb-mind` 一次性拉取 torch / transformers / sentence-transformers（Linux 上含 CUDA 可达 2GB+）的安装体积问题，给出"按需安装"的机制设计与落地清单。
- **方法**: 多 agent 并行盘点 5 个维度（依赖声明 / import 站点 / 现有可选-降级机制 / embedding-rerank 架构 / 安装与首跑流程），逐条以源码 file:line 佐证；本文结论已人工复核关键源码（`pyproject.toml`、`embedding/factory.py`、`embedding/local.py`、`retrieval/rerank/*.py`、`cli/commands/setup.py`、`storage/factory.py`）。
- **校验基线**: branch `docs/seo-optimization`，version `0.1.8`，源码以 `src/hebb` 为准。

> 报告中文叙述、代码/文件标识符保留英文（与代码及内部审计备忘一致）。本报告属内部设计文档，置于 `reports/`，**不进入 `repo_pages/`**。

---

## 一、问题陈述：要区分"两种下载"

用户反馈"安装 hebb-mind 时要下载很大的包（torch、transformer），能否需要时再下载"。这里必须区分**两类完全不同的下载**——它们在当前实现中的状态恰好相反：

| 下载类型 | 内容 | 体积 | 触发时机 | 现状 |
|---|---|---|---|---|
| **A. pip 包** | `sentence-transformers` + 传递依赖 `torch` / `transformers` / `huggingface_hub` / `tokenizers` / `safetensors` | Linux 默认 wheel 含 CUDA 约 **2–2.5GB**；CPU-only 约 150–250MB | `pip install hebb-mind` **安装期** | ❌ **饿汉式，一次性全拉** —— 真正的痛点 |
| **B. 模型权重** | `all-MiniLM-L6-v2`(~90MB)、`BAAI/bge-reranker-base` 等 HuggingFace 权重 | 90MB ~ 2GB（按 tier） | 首次使用 / `hebb setup` | ✅ **已经是按需下载** |

**结论先行**：用户想要的"需要时再下载"机制，对**模型权重(B)已经存在**；真正没有按需化的是**安装期的 pip 大包(A)**。好消息是代码结构已经为 A 的按需化铺好了几乎全部前置条件，改动面很小、风险可控。

---

## 二、现状盘点（含源码佐证）

### 2.1 依赖声明：`sentence-transformers` 是核心硬依赖

`pyproject.toml:28-48` 的 `[project.dependencies]` 把 `sentence-transformers>=3.0.0`（line 37）列为**必装**核心依赖。`torch` / `transformers` / `huggingface_hub` / `safetensors` 并未显式声明，但作为 `sentence-transformers` 的传递依赖被一并拉下。

```toml
dependencies = [
    ...
    "sentence-transformers>=3.0.0",   # ← line 37，核心依赖，拉入 torch/transformers
    ...
]

[project.optional-dependencies]
pg  = ["asyncpg>=0.29.0", "pgvector>=0.3.0"]          # line 51-54
dev = ["pytest...", "mypy...", "datasets...", ...]     # line 55-64
```

→ 任何 `pip install hebb-mind` 都必然付出 A 类下载，**哪怕用户根本不用本地模型**（例如打算走 API embedding）。这是体积问题的唯一根因。

### 2.2 import 站点：torch/ST 全部是懒加载（关键利好）

`import hebb` 是亚秒级的，**不触发任何重依赖**。`src/hebb/__init__.py:20-23` 的 docstring 明确写："Heavy dependencies (sentence_transformers, litellm, FastAPI…) are not imported at package-import time. They are loaded lazily on first use."

所有重 import 都在**函数/方法体内**，仅在真正构造本地组件时触发：

| 位置 | import | 触发条件 |
|---|---|---|
| `embedding/local.py:135` | `from sentence_transformers import SentenceTransformer` | 构造 `LocalEmbedder` |
| `retrieval/rerank/local.py:58` | `from sentence_transformers import CrossEncoder` | 构造 `LocalReranker` |
| `retrieval/rerank/local.py:59` | `from torch.nn import Sigmoid` | 构造 `LocalReranker` |
| `embedding/local.py:69`, `catalog.py:299/316`, `rerank/local.py:17` | `huggingface_hub.*` | 缓存检查 / 权重下载 |

grep `^\s*(from\|import)\s+torch` 在 `src/hebb` 全树**零命中顶层 import**。

→ 含义：把 `sentence-transformers` 挪出核心依赖后，**不会有任何顶层 import 崩溃**；缺包只在"真正构造本地 embedder/reranker"那一刻才暴露，而那一刻已经被工厂层 try/except 包住（见 2.3）。

### 2.3 已有的可选 / 降级 / 按需机制（可直接复用的范式）

代码里已经实现了我们需要的全部模式，只是没用到 ML 栈上：

1. **可选 extra + 友好报错（直接照抄的模板）** —— PostgreSQL 后端
   `storage/factory.py:70-73`：
   ```python
   try:
       import asyncpg
   except ImportError:
       raise ImportError("PostgreSQL backend requires asyncpg and pgvector. "
                         "Install with: pip install hebb-mind[pg]")
   ```

2. **工厂层 try/except → 优雅降级**（缺包不会崩，会降级）
   - `embedding/factory.py:57-65` `_create_local_embedder`：构造 `LocalEmbedder` 包在 `try/except Exception` 中，失败回落 `NoopEmbedder`（向量检索禁用）。**缺 `sentence-transformers` 时 `ModuleNotFoundError` 属 `Exception` 子类，会被这里吃掉** → 当前会"静默"降级，日志只有一句通用的 `Failed to load local embedding model, vector search disabled`。
   - `retrieval/rerank/factory.py:32-44` `create_reranker`：同样 try/except → 返回 `None`，searcher 跳过整段 rerank。

3. **功能开关**：`config/settings.py` 的 `embedding_enabled`(默认 True)、`rerank_enabled`(默认 True) 可整段关闭本地链路。

4. **HF 权重按需下载 + 离线缓存优先**：`embedding/local.py:104-124` 先 `HF_HUB_OFFLINE=1` 查缓存，仅在未命中时才清离线标志去下载；`rerank/local.py:43-56` 同模式。这正是 B 类已经"需要时再下"的实现。

### 2.4 纯 API 路径已存在（完全不需要 torch）

`embedding/factory.py:43-97`：当 `embedding_provider="api"` 时走 `ApiEmbedder`（litellm，`embedding/api.py`）或 `CustomHttpEmbedder`（httpx，`embedding/http_custom.py`），**既不 import torch 也不 import sentence-transformers**。配合 `rerank_enabled=false`，整条检索链路可在零 ML 栈下跑通（向量来自 API，词法通道 FTS5 本就无依赖）。

→ 含义：A 类下载是"可被绕开"的功能，不是框架地基。把它做成 opt-in 在架构上成立。

---

## 三、关键结论

1. 痛点 = **安装期 pip 大包 (A)**；模型权重 (B) 早已按需。
2. 代码已具备按需化的全部前置：**懒 import 齐全** + **工厂层降级齐全** + **可复用的 `[pg]` extra 范式** + **现成的 API-only 路径**。
3. 唯一缺的是：①把 `sentence-transformers` 从核心依赖挪到可选 extra；②在缺包时给**可操作**的提示而非静默降级；③按"用户路径所有权"原则，让框架（`hebb setup`）替用户完成这次 pip 安装，而不是甩给用户。

---

## 四、设计方案

### 方案 A（推荐）：可选 extra + import 守卫 + `hebb setup` 接管安装

**① packaging —— 拆出 `local` extra**（`pyproject.toml`）
把 `sentence-transformers` 移出 `[project.dependencies]`，新增：
```toml
[project.optional-dependencies]
local = [
    "sentence-transformers>=3.0.0",
]
```
- `pip install hebb-mind` → 轻量（无 torch）。
- `pip install hebb-mind[local]` → 完整本地栈。
- **CUDA 瘦身**：Linux 默认 torch wheel 含 CUDA（~2GB+），而 hebb 仅做 CPU 推理。`local` extra 无法纯靠 PyPI 约束钉死 CPU 版（需要 index-url），因此在**文档**与 **`hebb setup` 自动安装器**里走 CPU 通道：`pip install hebb-mind[local] --extra-index-url https://download.pytorch.org/whl/cpu`。可把体积从 ~2.5GB 降到 ~250MB。

**② import 守卫 —— 缺包时给可操作提示**（照抄 `[pg]` 范式）
在 `embedding/local.py:135` 与 `retrieval/rerank/local.py:58-59` 包装 import：
```python
try:
    from sentence_transformers import SentenceTransformer
except ModuleNotFoundError as e:
    raise ModuleNotFoundError(
        "Local embedding needs the ML stack (sentence-transformers + torch). "
        "Run `hebb setup` to install it, or `pip install hebb-mind[local]`, "
        "or switch to an API provider: `hebb config set embedding_provider api`."
    ) from e
```
同时**改进工厂层的降级日志**，让缺栈这一最常见情形不再静默——在 `embedding/factory.py:_create_local_embedder` 与 `rerank/factory.py:create_reranker` 的 `except` 中 `isinstance(exc, ModuleNotFoundError)` 时以更醒目级别打印上面的 `pip install hebb-mind[local]` 指引（仍回落 `NoopEmbedder`/`None`，不崩）。

**③ `hebb setup` 接管 pip 安装**（落实 User Path Ownership）
`cli/commands/setup.py` 的 `setup_cmd` 当前已负责下载**模型权重**（`prefetch_model`，line 75）并验证（`_verify_model`，line 77/140-147）。在 provider=local 且检测到 ML 栈缺失时，先 `pip install`（subprocess + rich 进度，走 CPU index-url），再继续下载权重。用户路径变为：
```
pip install hebb-mind        # 秒装、体积小
hebb setup                   # 按所选配置精确安装：pip 包(CPU torch) + 模型权重
```
这符合 CLAUDE.md「每一次跨进程步骤都是框架的责任，不是用户的」。

> 取舍说明：是否在**任意调用点**（而非 `hebb setup`）做运行时自动 pip install，见方案 B——不推荐作为主路径。

### 方案 B（备选，不作主路径）：运行时自动 pip install

在首次构造本地组件、import 失败时由进程自己 `subprocess pip install`。优点是对脚本式用户也"零手动"；缺点明显：① torch 构建矩阵复杂（CPU/CUDA/index-url/平台），自动选择易错；② 在运行中的进程里装包并继续 import 不可靠（已加载的解释器状态）；③ 静默联网+装 GB 级包对用户是惊吓。**结论**：把自动安装收敛到显式的 `hebb setup`（方案 A③），不要散落在任意调用点。

### 方案 C（不推荐）：把默认 provider 改成 API

最彻底（开箱零 torch），但**不建议**：
- 所有公开基准（LoCoMo / MemBench / LongMemEval）均在本地 `all-MiniLM-384 + bge-reranker-base` 默认配置上测得，改默认会动摇这些数字的出处（违反 `eval/README.md` 的"published number 必须引用 in-tree run-N 报告"基线）。
- 牺牲"零配置、纯本地、无需 API key"的开箱体验。
- API embedding 需要 base_url/key/联网，且维度探测失败会禁用向量检索。

→ 保留**本地为默认**，只把它的**安装时机**从 `pip install` 后移到 `hebb setup`。

---

## 五、推荐落地清单（方案 A）

- [ ] **pyproject.toml**：`sentence-transformers>=3.0.0` 从 `[project.dependencies]` 移至新增 `local` extra。
- [ ] **pyproject.toml**：`dev` extra 追加 `"hebb-mind[local]"`（或 CI 改为 `pip install -e .[dev,local]`），保证带 `slow` marker 的本地模型测试与 mypy 仍有栈。
- [ ] **pyproject.toml `[tool.mypy.overrides]`**：把 `sentence_transformers.*`、`torch.*`、`transformers.*` 加入 `ignore_missing_imports = true` 列表，避免轻量环境下 mypy strict 因找不到 stub 报错。
- [ ] **embedding/local.py:135** + **rerank/local.py:58-59**：import 守卫，抛可操作的 `ModuleNotFoundError`。
- [ ] **embedding/factory.py:_create_local_embedder** + **rerank/factory.py:create_reranker**：`except` 中特判 `ModuleNotFoundError`，醒目打印安装指引（仍降级，不崩）。
- [ ] **cli/commands/setup.py**：新增 `_ensure_ml_stack()`（provider=local 且栈缺失时 `pip install`，CPU index-url，rich 进度），在 `prefetch_model`/`_verify_model` 之前调用。
- [ ] **hebb doctor**：体检项增加"本地 provider 但 ML 栈缺失"的诊断 + 修复建议。
- [ ] **文档（README + repo_pages 安装页 + zh 镜像同步）**：明确两种安装姿势（轻量 / 完整 `[local]`）与 CPU index-url；EN 与 `zh/` 同步更新。
- [ ] **CHANGELOG + 版本**：按 manual-release 流程手动 bump 四处版本（pyproject / `__init__` / manifest / plugin.json）。
- [ ] **测试**：① 轻量环境（无 sentence-transformers）下 `import hebb`、`hebb config set embedding_provider api` 全链路可跑、缺栈报错文案断言；② `hebb setup` 自动装栈的 e2e（可 mock subprocess）。

---

## 六、风险与注意事项

- **向后兼容**：已有用户 `pip install hebb-mind` 升级后将**不再自动获得**本地栈。需在 CHANGELOG / release note 显著提示"如用本地模型请改装 `hebb-mind[local]` 或跑 `hebb setup`"。可考虑过渡期：保留一个 `all`/`full` extra = `[local,pg]` 作为"全都要"的别名。
- **CI / mypy**：`dev` 不再传递获得 `sentence-transformers`，CI 必须显式 `[dev,local]`，否则 `slow` 测试与 mypy 断裂（见落地清单）。
- **eval 复现性**：评测脚本须确保运行环境装了 `[local]`；默认配置（embedding/reranker 模型）**不变**，因此已发布数字不受影响。
- **User Path Ownership**：方案 A③ 是这条红线的关键——不能止步于"友好报错让用户自己 pip"，要由 `hebb setup` 真正替用户完成跨进程安装。
- **静默降级回归**：务必落实 ② 的日志改进，否则轻量安装的用户会遇到"向量检索悄悄失效"而无指引——这正是当前 `_create_local_embedder` 通用 warning 的隐患。
- **离线/内网环境**：自动 pip 安装需要可达的 PyPI / 镜像；`hebb setup` 应在装栈失败时给出"手动 `pip install hebb-mind[local]`"回退提示，并复用已有的 region/mirror 解析思路（`catalog.resolve_region`）。

---

## 七、验收标准

1. `pip install hebb-mind` 不再拉取 torch/transformers/sentence-transformers；安装体积显著下降（Linux 从 ~2GB+ 量级降到百 MB 量级）。
2. 轻量安装下 `import hebb` 正常；走 API provider 全链路可用；本地 provider 在缺栈时给出明确、可操作的指引而非静默失效。
3. `hebb setup`（本地 provider）能自动、带进度地装好 CPU 版 ML 栈 + 模型权重，无需用户手敲任何 pip/torch 命令。
4. CI（含 `slow` 测试与 mypy strict）在 `[dev,local]` 下全绿；默认评测配置与已发布基准不变。
