# Hebb Mind 新用户体验 & 文档有效性审计

- **日期**: 2026-06-08
- **视角**: 全新用户，从安装包 → `hebb setup` 首次运行 → Claude Code / Codex 集成 → 文档跟随
- **范围**: README(EN/ZH)、repo_pages 文档站(EN/ZH)、examples、docker、CLI `--help`、Settings 模型
- **方法**: 5 条 journey lane 并行(`code-analyst`，只读环境，仅 `hebb --help` 内省，禁止任何 setup/install/service 等写操作)→ 每条发现独立 skeptic 对抗复核 → 人工抽样实测核心 drift。
- **统计**: 50 原始 → **41 确认** / 9 证伪。确认分级：**high 10、medium 10、low 21**。
- **基线**: 工作树 = branch `fix/core-audit-remediation`（代码已含上一轮修复）。PyPI 已发布 = 0.1.6。报告区分"今天 PyPI 用户会遇到"与"仅工作树"。

> 关键背景：上一轮**代码**修复未同步**文档**——多处文档仍描述旧行为（host 0.0.0.0、doctor 门槛、`hebb cc` 等）。本审计的相当一部分是"文档滞后于已修代码"。

---

## 一、结论速览

安装命令本身正确（pipx/pip/uv、entry points `hebb`/`hebb-mcp` 都解析正常），服务/config/model/memory 命令树与真实 CLI 一致。但新用户从落地页到第一段代码、到集成，会连续撞上**会话级阻断或误导**。八个集群：

| # | 集群 | 性质 | 严重度 |
|---|------|------|-------|
| U1 | **"60 秒"承诺是假的**：默认 `hebb setup` 同步下载 bge-large(~1.3–4GB)/bge-m3(~2.3–4.6GB)，几分钟，无大小/进度提示；快路径 `--profile fast`(MiniLM ~90MB)从不在快速开始里出现 | inaccurate-claim | high |
| U2 | **照抄即崩**：SDK 片段 `hit.content`(应 `hit.memory.content`)；Migration 指南所有 Python 片段用不存在的 `partition_id=`/`importance_score=`/`mem.ingest()` | doc-code-drift | high |
| U3 | **`hebb claude-code write` 满文档但不存在**：真实命令是 `prompt`(且它是召回不是写)；cli.md(EN/ZH)、claude-code.md、README 全错；连带整套 hook 心智模型错 | doc-code-drift | high |
| U4 | **巩固上手陷阱**：到处把 `llm_api_key` 当"开启巩固"的钥匙，真实门槛是 `llm_model`；空跑静默；锚点失效；文档称 Stop 触发巩固(实则不会) | doc-code-drift / error-ux | high/medium |
| U5 | **缺前置步骤**：codex.md 漏掉 `hebb service install`，照做到第一次工具调用即以不透明连接错误失败 | missing-step | high |
| U6 | **集成文档残缺/自相矛盾**：plugin marketplace 路径无文档且无 marketplace.json；scope 段自相矛盾；手动 MCP 用裸 `hebb-mcp`(与安装器的绝对路径原则冲突)；Codex 页从不说"装完怎么用" | clarity / friction | medium |
| U7 | **EN/ZH 失配**：`zh/guide/web-console.md` 与 `zh/troubleshooting.md` 是 3 行占位 stub(EN 各 103/191 行)——恰是首次运行出问题时最需要的两页；zh benchmarks 链接到无中文镜像的页 | en-zh-parity | medium |
| U8 | **过期默认值/版本串**：configuration.md 配置参考仍写 host `0.0.0.0`、bge-large/1024、`sk-xxx`；multi-model test-llm curl 路径/body 错；examples 标 v0.1.1/0.1.2 | stale-version | medium/low |

> U1/U2/U3/U4 直接命中"新用户的第一分钟、第一段代码、第一个集成"——优先级最高。多数是**纯文档**修复（快、安全）；少数需代码侧配合（surface fast profile、加 `ingest()` facade 或下载进度）。

---

## 二、HIGH（会阻断或明确误导新用户）

### U1 · "60 秒、无需 API key"与多 GB 下载冲突  〔install F1/F3，已实测〕
- **位置**: `README.md:27`、`repo_pages/quick-start.md:3-43`、`repo_pages/index.md:21-22`（+ZH 镜像）；代码 `embedding/catalog.py:103-133`、`cli/commands/setup.py:30/67`
- **事实**: 落地页/README/quick-start 头条"Try in 60 seconds — no API key needed"，紧接着的命令就是裸 `hebb setup`。但 `choose_model(profile="default")` 对 en 返回 `BAAI/bge-large-en-v1.5`、对 zh/multi 返回 `BAAI/bge-m3`（均 1024 维），且 `prefetch_model` 未传 `allow_patterns` → `snapshot_download` 拉**整个 repo**（bge-large ≈4GB、bge-m3 ≈4.6GB，含冗余 safetensors+bin+onnx）。项目自己的 `troubleshooting.md:98-102` 都承认"3–5 分钟，慢网 15 分钟+"。新装的 hebb.json 默认 `all-MiniLM-L6-v2` 属 `LEGACY_DEFAULT_MODELS`，setup 会主动升级把用户从 MiniLM 换成大模型。
- **影响**: 每个新用户、PyPI 0.1.6 与工作树皆中。落地页第一句承诺即不可达，用户误以为卡死（正是"First start hangs"症状）。
- **修复**: 快速开始改用 `hebb setup --profile fast`（MiniLM-384 ~90MB）作为 60 秒路径；或头条改为"~60s after model cached；首次下载 1–2GB 模型(3–15 分钟)"。代码侧：setup 打印预计下载大小+进度；`prefetch_model` 加 `allow_patterns` 跳过冗余 bin/onnx（≈砍半）。

### U2 · 文档里的代码照抄就崩  〔install F2 + docs F2，已实测〕
- **SDK 片段**（`README.md:119`、`README_ZH.md:120`、`quick-start.md:127` +zh）：`print(hit.score, hit.content)` → **AttributeError**。`search()` 返回 `list[MemorySearchResult]`，内容在 `hit.memory.content`。改这一处即可。
- **Migration 指南**（`guide/migration.md:51-56/101-103/159-163`）：所有 Python 片段都用 `mem.add(..., partition_id=, importance_score=)`、`mem.search(query=, partition_id=)`、`mem.ingest(...)`。实测 facade 真实签名 `add(content, *, partition=, importance=, tags=, metadata=, source=)`、`search(query, *, partition_ids=, ...)`，**无 `ingest` 方法**。即每个片段抛 `TypeError`/`AttributeError`。这是从 mem0/Letta/Zep 迁移用户（最高意向人群）的落地页，**无一行能跑**。
- **修复**: SDK 改 `hit.memory.content`（4 处）；migration 改真实签名 `mem.add("...", partition="alice", importance=7.5)` / `mem.search("...", partition_ids=["alice"])`；`mem.ingest()` 改为 REST `POST /api/v1/ingest`，或给 facade 补 `ingest()` 并文档化。

### U3 · 满文档的 `hebb claude-code write` 不存在  〔cc-01/cc-03 + docs F1，已实测〕
- **位置**: `guide/claude-code.md:50,72`、`api/cli.md:168`、`zh/api/cli.md:160`（4 处）；真实 CLI 子命令是 `recall/prompt/stop`，**无 `write`**。
- **事实**: 不仅命令名错（`write`→`prompt`），整套心智模型也错：文档称 UserPromptSubmit 时"逐条消息 strip+dedup 写库"，实际 `prompt` 钩子做的是**召回注入**；用户回合的**写入**发生在 **Stop** 钩子（按回合从 transcript 抓最后一轮，`source:hook:stop`，按 session_id+turn 去重）。`README` 还引用了不存在的 `integrations/claude_code/write.py`(cc-07)。
- **影响**: 用户手动验证/调试 hook 时 `No such command 'write'`；排查"消息为什么没存"时盯错钩子、期望错的 source。两版本皆中。
- **修复**: 4 处 `write`→`prompt` 并改描述；重写 claude-code.md 的 Write/Stop 段：UserPromptSubmit=召回；Stop=回合写入工作区。

### U4 · 巩固上手陷阱  〔first-run F1 + cc-04，部分细化〕
- **门槛措辞**: FAQ(`faq.md:9`)、quick-start 把"设 `llm_api_key`"当作开启巩固的关键，但真实门槛是 `llm_model`（`api.py:502`、`consolidation_job.py`、本地/代理模型无需 key）。注：`troubleshooting.md:23-25` 实际**同时**设了 key 与 model（照抄能成功）——所以这页 OK，问题在 FAQ/强调点 + 上一轮已把 `hebb doctor` 改为按 `llm_model` 判定（文档未同步）。
- **Stop≠巩固**（cc-04，`claude-code.md:51,82-86`、`api/cli.md:169`）：文档称 Stop 钩子触发"consolidation + cleanup"，实际巩固只按 `consolidation_time` 定时或手动 `POST /admin/consolidate`。会话结束不会整理记忆。
- **修复**: 全文把 `llm_model` 作为巩固首要必填（key 仅托管 provider 需要）；同步 doctor 措辞；Stop 描述改为"写入工作区，巩固另由定时任务"。

### U5 · Codex 页漏掉 `hebb service install`  〔codex-01，已确认〕
- **位置**: `guide/codex.md:7-11`（Install 块只有 `hebb setup` + `hebb codex install`）；`utils/service.py:60-105 ensure_service_running` 只能启动**已安装**的服务。
- **事实**: 照 codex.md 走完，打开 Codex 让它记东西 → MCP 工具 POST `127.0.0.1:8321` 无服务 → 失败；唯一提示是 MCP server stderr 的 `logger.warning('Run: hebb service install')`，Codex 用户看不到。`mcp-integration.md` 的 Prerequisites 里**有**这步——即专用页才是坏的那个。
- **修复**: codex.md/zh 在 `setup` 与 `codex install` 之间补 `hebb service install`；并让 `hebb codex install` 在无已装服务时告警。

### U（doc-validity）· 其余 HIGH
- **docs F1** = U3（cli.md `write`）。已并入。

---

## 三、MEDIUM

- **first-run F2 · EN/ZH stub**：`zh/guide/web-console.md`、`zh/troubleshooting.md` 各仅 3 行占位（EN 103/191 行）。中国是明确目标人群（hf-mirror、`--region cn`），却恰好把"控制台空状态 / 首次运行排障"两页留空。违反 CLAUDE.md "EN 页必须连同 zh 镜像一起更新"。→ 补全翻译；过渡期把链接指向 EN 页避免死路。
- **first-run F5 · 配置参考过期默认**：`guide/configuration.md:70-94/112`（+zh）的 Full Configuration Reference 写 `host:0.0.0.0`、`embedding_model:bge-large/1024`、`llm_api_key:"sk-xxx"`。工作树 host 已改 127.0.0.1（文档**夸大**了暴露面），0.1.6 仍 0.0.0.0；读者无法分辨自己是哪版。→ host 改 127.0.0.1 并注明"≤0.1.6 为 0.0.0.0"；model/dim 标注"setup 选定；裸默认 MiniLM/384"；key 用 `null`。
- **cc-05 · plugin marketplace 路径无文档**：`.claude-plugin/plugin.json` 存在，但 claude-code.md/README 从不提 plugin 安装路径，且 `.claude-plugin/` 下**无 marketplace.json**（仅 .research 下有他人副本）——plugin 可能根本装不了。两条安装路径(CLI vs plugin)不一致。→ 要么文档化 plugin 路径并补 marketplace.json，要么明确"受支持路径是 `hebb claude-code install`"。
- **cc-06 · scope 段自相矛盾**：顶部 Install 用 `--scope user`，Scope 段又说 project 是默认、把 `--scope user` 当"全局"备选——同一命令两处出现，新手分不清推荐哪个。→ 选一个推荐并 EN/ZH 一致。
- **cc-09 · 手动 MCP 用裸 `hebb-mcp`**：`claude-code.md:100-117`、`mcp-integration.md:38-50` 让手动用户注册裸 `hebb-mcp`——正是安装器极力避免的失败模式（GUI/launchd 下 PATH 缺失，MCP 静默不启动）。→ 手动片段改用绝对路径（`which hebb-mcp`），或引导走 `hebb claude-code install`。
- **codex-04 · 从不说"装完怎么用"**：codex.md 全程没有一句"在 Codex 里输入什么来存/取记忆"。用户到达"装好但看不出有用"的状态。→ 加"在 Codex 里用"小节，给具体 prompt 例子。
- **docs F5 · quick-start 排障锚点失效**：`quick-start.md:87`（+zh）链到 troubleshooting 顶部而非巩固空跑那节——用户诊断"为什么 consolidate 返回 0"永远到不了原因。→ 锚点改 `#consolidate-returns-processed-0-...`。
- **docs F6 · multi-model test-llm curl 错**：`advanced/multi-model.md:96-98` 的验证命令缺 `/admin` 会 404，且无 `{"model":...}` body 会 422。配完多模型唯一的验证步跑不通。→ 换 `api/config.md` 的可用形式。

---

## 四、LOW（21 条，择要）

- install F4：benchmark 表称 MiniLM-384 是"用户实际所得"，与默认 profile 下大模型矛盾。
- install F5/F6：EN/ZH 安装页对 setup 写入位置说法不一（`~/.hebb/` vs "workspace"）；SDK 注释"用 ~/.hebb/hebb.json"忽略 cwd-first 查找。
- install F7 / first-run F8 / docs F10：examples 标 v0.1.1/0.1.2；installation.md "Verify" 步其实是装后台服务（标错/顺序错）；cli.md `memory reembed` 漏 `--restart`、codex `--scope project` 仍显示。
- install F8/F9：`installation.md` 的 Verify 误装服务；无 LLM 巩固静默 no-op，文档却标为已闭合的"v0.1.1 gap"。
- first-run F6/F7/F9/F10：troubleshooting 的 `hebb status` 期望输出串过期；`config get workspace` 示例输出与实际不符；空 LLM 下 console graph 静默空的体验未说明；zh 配置 restart-required 列表无说明。
- cc-07/cc-08：README 引用不存在的 `write.py`；config 段夸大自启动且 zh 漏"先装服务"。
- codex-03/05/07/08/09/10：发布版 `.codex/hooks.json` 曾引用 `hebb cc *`（工作树已修）；mcp-integration 工具表漏 `ingest_conversation`(实 4 个)；`--scope user` 被当有意义选项(实为唯一值)；远程示例用 127.0.0.1 与"remote host"措辞矛盾；codex 失败路径假设 `codex` CLI 在场但未列前置；Capability Boundary 把 Claude Code 描述成有 Codex 没有的 auto-write 钩子(实际两边写入机制已统一为 Stop)。

---

## 五、被证伪/降级（9 条）

- install F10：docker-compose `HEBB_LLM_MODEL=gpt-4o-mini` 空 key 致容器内巩固失败 → 复核为非问题（按现配置不触发）。
- first-run F4：fast profile 从不在 Quick Start 出现 → 与 U1 重复，单列降级。
- cc-10：recall 输出用 `mem_*` 标签是"捏造" → 实际输出确用 partition_id，非问题。
- codex-02：`.codex/hooks.json` 是 vestigial 误导 → 复核为 low/非阻断（无人读它，但工作树已修命令串）。
- codex-06：'60s/zero external services' → 对 ingest+search 成立，降级。
- docs F3/F7/F8/F9：embedding 默认 bge vs MiniLM 文档不一(并入 U1/U8)；KG "parallel recall" 过度描述(并入代码审计 C6)；host 0.0.0.0 文档错(并入 U8/F5)；zh mcp 自启动声明(并入 cc/codex)——均为重复或已在别处覆盖。

---

## 六、修复优先级

**P0（纯文档，落地页/第一段代码，建议立刻）**
1. U2 SDK `hit.content`→`hit.memory.content`（4 处）+ migration 全部片段改真实签名
2. U3 `hebb claude-code write`→`prompt`（4 处）+ 重写 Write/Stop 心智模型段
3. U1 快速开始改 `--profile fast` 或披露下载大小/时间
4. U5 codex.md 补 `hebb service install`
5. U4 全文以 `llm_model` 为巩固首要必填；Stop≠巩固

**P1（文档同步已修代码 + 集成完整性）**
6. U8 configuration.md host→127.0.0.1(注明历史)、model/dim/key 占位修正；multi-model curl 修正；quick-start 锚点修正
7. U7 补全 `zh/web-console.md`、`zh/troubleshooting.md` 全文翻译；zh benchmarks 缺页
8. U6 plugin 路径文档化(+marketplace.json)或明确不支持；scope 段统一；手动 MCP 用绝对路径；Codex "怎么用"小节

**P2（代码侧配合 + 打磨）**
9. setup 打印下载大小+进度；`prefetch_model` 加 `allow_patterns`；可选给 facade 加 `ingest()`
10. examples/cli.md 版本串与 flag 清理；CI 加"plugin.json/.codex/hooks.json/docs 中每个 hebb 命令都能解析"的断言
