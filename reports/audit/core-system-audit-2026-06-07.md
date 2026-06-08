# Hebb Mind 核心系统审计报告

- **日期**: 2026-06-07
- **范围**: 安装 / 启动 / 写入 / 召回 / 巩固 / 遗忘 / embedding / LLM 配置 / hook / console 共 10 个维度
- **方法**: 多 agent 并行审计（每维度一个 `code-analyst` 深读指定文件并追踪运行时流程）→ 每条发现由独立 skeptic 重新打开源码对抗式复核（refute-by-default）→ 人工抽样校验关键结论。
- **统计**: 91 条原始发现 → **71 条确认** / 20 条证伪或降级。确认项分级：**critical 2、high 23、medium 23、low 23**。
- **校验基线**: commit `80626b6`（branch `fix/subagent-filter-and-delete-consistency`），源码以 `src/hebb` 为准（`build/lib` 为陈旧拷贝）。

> 报告中文叙述、代码/文件标识符保留英文（与代码及内部备忘一致）。本报告属内部审计，置于 `reports/`，不进入 `repo_pages/`。

---

## 一、结论速览


| # | 根因集群 | 性质 | 波及维度 |
|---|---------|------|---------|
| C0 | **发布通道 build 即坏**：Docker `hebb start` 不存在、plugin/codex hooks `hebb cc write` 不存在 | critical/high | 安装、hook |
| C1 | **单一共享 sqlite 连接 + 无锁共享 graph**：所有 HTTP handler 与调度任务共用一条 aiosqlite 连接和一个 `nx.Graph`，锁粒度不一致 | high | 启动、写入、巩固、遗忘 |
| C2 | **网络暴露 + 零鉴权 + 明文密钥**：默认 `host=0.0.0.0`、全开 CORS、`/reveal` 明文返回密钥、test 端点把真实密钥外发 | high | 启动、LLM 配置、console |
| C3 | **写入/迁移非原子 → 静默数据丢失**：create 三写无回滚、维度变更 DROP 向量表、空内容覆盖、partition 不校验 | high/medium | 写入、embedding、console |
| C4 | **cwd 绑定 workspace/DB**：`service install` 把安装时 cwd 烤进 plist，不钉 `HEBB_HOME` | critical/high | 安装、启动 |
| C5 | **遗忘过激 + 召回门槛错配**：importance=0 → TTL=0 当场删除、strict 召回 0.8 门槛跨尺度比较、IDF 校准是死代码、非本地 embedder 未归一 | high | 遗忘、巩固、召回、embedding |
| C6 | **图通道形同虚设 / 跨 partition 泄漏**：whole-query 子串匹配几乎永不命中；graph 召回不按 partition 过滤 | medium | 召回 |

> C2/C3/C4 直接命中 CLAUDE.md 列为头号风险的"跨进程路径所有权"与"数据丢失"红线。

---

## 二、两个 CRITICAL（发布即坏）

### C0-1 · Docker 镜像启动不存在的 `hebb start`，容器永不提供服务
- **位置**: `docker/Dockerfile:23`
- **事实**: CMD 末尾是 `hebb start --host 0.0.0.0 --port ${HEBB_PORT:-8321}`，但根命令组只注册了 `setup/service/status/console/config/mcp/model/memory/doctor/claude-code(cc)/codex` 和隐藏的 `_serve`——**没有 `start`**；`--host/--port` 也只有 `_serve` 接受。已实测 `hebb start` 退出码 2（`No such command 'start'`）。
- **影响**: 每次 `docker run` / `docker compose up` 先跑完 setup，再在最后一句崩溃；8321 永不起服务。`restart: unless-stopped` 把它变成崩溃循环。整条 Docker 发布通道不可用，且日志里 setup 成功会误导排障。
- **修复**: CMD 改为 `hebb _serve --host 0.0.0.0 --port ${HEBB_PORT:-8321}`，或新增公开 `hebb serve`/`start` 别名；CI 加 build-and-curl-/health 冒烟测试。compose 另需透传 `HEBB_PORT/HEBB_STORAGE_TYPE/HEBB_PG_URL`。

### C0-2 · marketplace plugin.json 与 .codex/hooks.json 调用不存在的 `hebb cc write`
- **位置**: `.claude-plugin/plugin.json:20/32/44`，`.codex/hooks.json:9/20/31`
- **事实**: 两处 hook 都用 `hebb cc recall|write|stop`。但 (1) 命令组是 `@click.group("claude-code")`，`main.add_command(cc)` 按组名注册为 **`claude-code` 而非 `cc`**——`hebb cc ...` 直接 "No such command"；(2) 即便组名对，子命令也只有 `install/uninstall/recall/prompt/stop`，**没有 `write`**（UserPromptSubmit 应是 `prompt`）。
- **影响**: 凡通过插件市场或这份 `.codex/hooks.json` 安装的用户，三个 hook 全部失败：SessionStart/Stop 死在组名，UserPromptSubmit 还多死在 `write`。**不召回、不记忆**。而程序化安装器 `install.py` 写的是正确的 `hebb claude-code recall/prompt/stop`——两条安装路径静默分裂。
- **修复**: 把三处改为 `hebb claude-code recall/prompt/stop`；加测试断言 plugin.json / hooks.json 中每个命令串都能解析到已注册的 Click 命令。

---

## 三、系统性根因集群（含成员缺陷）

### C1 · 单一共享 sqlite 连接 + 无锁共享 graph
`create_stores()` 只开一条 `aiosqlite.Connection`（`storage/factory.py:46`），同一个 store 实例既给所有 FastAPI handler、又给 `SchedulerManager`；`KnowledgeGraph` 是同一个 `nx.Graph`。连接默认 deferred isolation，多个协程共享一个隐式事务；kg 锁粒度还不一致。

成员缺陷：
- **[high] 启动F3 / 写入F1**（`server/app.py:44-85`, `storage/sqlite_store.py` create/commit）：跨请求 + 调度共用连接、无事务隔离；WAL 单线程下不会撕裂单语句，但**会丢失原子性**——一个协程可能提交另一个协程的半成品事务。
- **[high] 写入F2**（`storage/sqlite_store.py:48-82`）：memories 行 + vec0 + FTS 三写无 `try/except` 回滚；任一失败异常上抛而隐式事务留开，下一个协程 commit 时把半成品落库——产生**无索引（不可召回）的孤儿行**且持久。
- **[medium] 巩固F3**（`scheduler/consolidation_job.py:39-50`）：cron 与无鉴权 `/consolidate` 共用连接与 graph，`kg_lock` 只护单批，重叠运行会双处理或写出被判损坏而丢弃的 graph JSON。
- **[medium] 遗忘F3**（`scheduler/manager.py:100-128`）：遗忘/巩固任务与 HTTP handler 共连接 + 共未同步 graph；30 分钟遗忘与手动 `/consolidate` 撞上会产生孤儿/丢失节点（注：多数 sweep 不删东西时跳过 `save()`，触发面较窄）。
- **[high] 遗忘F4**（`agents/consolidation_agent.py:354-361`）：session 巩固路径的 graph 写在 `kg_lock` **之外**（单条路径 `_consolidate_one` 却有锁）——锁纪律前后不一致，并发 session 巩固可丢更新。

**统一修复方向**: 后台任务用独立连接（代码已有 isolated-db 巩固能力），或所有写入串行在一个进程级 `asyncio.Lock` 后；每个多语句操作包显式 `BEGIN IMMEDIATE...COMMIT`，失败 `rollback`；把"所有 kg 读-改-写 + save"收进一把锁。

### C2 · 网络暴露 + 零鉴权 + 明文密钥（已逐条实测）
默认 `settings.host="0.0.0.0"`（`config/settings.py:133`）；所有 router 的 `Depends()` **全是 store/settings 注入，无一条鉴权**；CORS `allow_origins=["*"] + allow_credentials=True`（`server/app.py:114-120`）。

成员缺陷：
- **[high] console F1 / LLM配置F1**：默认监听全网卡、零鉴权；`GET /api/v1/admin/config/reveal/{key}` **明文**返回 `llm_api_key/pg_url/embedding_api_key/embedding_http_headers`（`server/routers/config.py:110-118`，实测无任何 auth）。同网段任意主机可读全部记忆、改配置、取密钥、重启服务。
- **[high] console F2 / 启动F8**：通配 CORS + 凭证；Starlette 会回显调用方 Origin，使恶意网页可跨源读响应（drive-by / DNS-rebinding）。
- **[high] console F5**（`config.py:145-211`）：无鉴权的 `test-llm` / `test-embedding` / custom-http 接受调用方指定的 `base_url/http_url`，当 key/headers 为掩码时回退到**真实存储密钥并外发到调用方指定地址**——既是密钥窃取原语又是 SSRF。
- **[high] console F7**（`config.py:38-107`）：`PUT /config` 无鉴权可改 `host/port/home/storage_type/pg_url`——可重绑监听、把 workspace 指向空 DB（重启后表观数据丢失）、改库。
- **[low] console F6**（`config.py:32-35`）：掩码只在 `len>8` 时生效，≤8 字符密钥明文返回，9–12 字符泄漏首尾各 4 字符。
- **[low] LLM配置F10**（`cli/commands/config.py:125-132`）：CLI `_mask` 漏了 `embedding_http_headers`，`hebb config list` 把含 bearer 的 headers 明文打到终端（server 侧已掩码——两侧口径不一致）。

**统一修复方向**: 默认绑 `127.0.0.1`，需要远程时显式 opt-in + 生成 bearer token；admin/config 路由整体加鉴权或仅环回；CORS 收紧到 console 自身 origin 并去掉 `allow_credentials` 通配组合；test 端点只在 `base_url` 等于已配置 provider 时才注入存储密钥，否则要求显式传入；统一两侧掩码集合并对任意非空密钥用固定占位符。

### C3 · 写入/迁移非原子 → 静默数据丢失
- **[high] 写入F7 / embedding F7**（`storage/migrations.py:112-126`）：`_ensure_vec_table` 探测到维度不匹配（或缺列）就 `DROP` 整张 `memory_embeddings` 只留一条 WARNING。而维度来自 `settings.embedding_dim`，`app.py` 启动时又用 `embedder.dimension` 覆盖它——**改个 embedding_model 或 embedder 回退就会静默清空全部向量**，写入路径不会自动重嵌，向量召回归零直到手动 `hebb memory reembed`。（源数据 `memories.content` 仍在，可恢复但无提示。）
- **[high] console F8**（`static/js/components/memories.js:175-181` + `server/routers/memories.py:80-94`）：Edit 弹窗无 `content` 非空校验（Create 有），清空后保存会把内容覆盖为 `''` 并**重嵌空串**，`MemoryUpdate` 服务端也无 `min_length`——单条记忆静默销毁且不可召回。
- **[medium] 写入F4**（`server/routers/memories.py:141-145`）：`zip(items, embeddings)` 在 `embed_batch` 返回数 < 输入数时**静默截断尾部**，`memories_created` 仍报 `len(items)`——返回 201 但悄悄丢数据（仅 `provider='api'` 且上游违反每输入一行时触发）。
- **[medium] 写入F5**（`memories.py:142-152`）：批量 ingest 每条独立 commit，中途失败→已提交部分留库 + 返回 500；无幂等键，重试整段重灌→重复。
- **[medium] 写入F6**（`memories.py:55-62`, schema 无 FK）：`partition_id` 不校验也无外键，写到不存在的 partition 后对分区列表/UI 不可见、巩固永不处理——写后即丢。
- **[medium] embedding F2**（`storage/sqlite_store.py:69-81`）：vec0 INSERT 前不校验 `len(embedding)`，维度不符直接整条 create 失败（无"存文本跳向量"降级）；连键词存储一起拖垮。（注：server 路径会从 live embedder 钉维度而免疫；`_ensure_vec_table` 重启自愈——故 medium。）
- **[medium] embedding F1**（`api.py:200-218`）：库 API `HebbMemory` 先建 vec0 表再解析真实维度（与 server 相反顺序），配置 dim 与模型真实 dim 不符时，库路径建错宽度的表→后续每次写入失败。

**统一修复方向**: create 三写包显式事务 + 失败回滚；维度不匹配**拒绝启动并提示 reembed**，或重建后自动入队重嵌，至少要显式 opt-in 才允许销毁向量；`zip(..., strict=True)` 并按实际插入数计数；批量 ingest 一次事务；写入校验 partition 存在；Edit 前后端都拒空内容；`api.py` 调整为先建 embedder 钉维度再建 store。

### C4 · cwd 绑定 workspace/DB（历史 eval 污染/召回死亡的根因）
- **[critical] 启动F1 / [high] 安装F3**（`utils/service_manager.py:63-67,207-223`）：`workspace_dir()` 无 `config_path` 调 `resolve_workspace()`→从 `Path.cwd()` 向上找 `hebb.json`，把**安装时 cwd** 烤进 plist/unit 的 `WorkingDirectory`，且**不写 `HEBB_HOME`**；启动时 `_serve` 又从该 cwd 重新解析 workspace。在 repo 或任何含 hebb.json 的目录里跑 `hebb service install`，8321 守护就被钉到该项目的 DB；换目录重装会静默切库（表观数据丢失、召回死亡）。与内部备忘 `service-install-binds-cwd` 记录的真实事故吻合。
- **[medium] 启动F10**（`service_manager.py:229-246`）：launchd install 重装前**无条件 bootout** 正在跑的守护、不告知 DB 即将变更、不 drain 在途请求。

**统一修复方向**: OS 服务必须用与安装 cwd 无关的确定性 workspace——安装时解析并固化绝对 `HEBB_HOME`（默认 `~/.hebb` 或 `--home`），写进 launchd `EnvironmentVariables` / systemd `Environment=` / Task XML，并在安装输出里打印绑定的 workspace；重装检测已有注册、对比新旧 DB 路径、需确认或 `--force`。

### C5 · 遗忘过激 + 召回门槛错配
- **[high] 遗忘F1 / 巩固F2**（`scheduler/forgetting_job.py:29-47`）：`importance_weight = importance_score/5.0`，`importance_score∈[0,10]` 可合法为 0（LLM/巩固/`MemoryCreate ge=0.0` 都允许），乘积为 0→`compute_ttl_hours=0`→expires_at 不变（已过期）→**下一次 sweep（默认 30 分钟内）当场删除**，无最小 TTL 地板、无新建宽限。衰减项也会让 ~10 天未访问的旧记忆 TTL 跌破 sweep 间隔。
- **[high] 召回F3**（`retrieval/searcher.py:222-238`）：rerank 后 pool 的 `score` 是 cross-encoder sigmoid，tail 仍是 composite `disp_score`——两种分布。strict 召回（MCP 与 Claude Code hook **都硬编码 strict_recall=True**）统一套 `recall_min_score=0.8` 地板，bge-reranker 对正确但非字面命中的短对话记忆常 <0.8（与自家 MemBench Hit@1≈0.49 一致），**两条生产召回面会静默返回空集**。
- **[medium] 召回F2**（`retrieval/searcher.py:126`）：`build_lexical_query` 不传 `idf`，每词权重 1.0——`lexical_relevance` 整套"relevance=Σidf·matched/Σidf"的校准前提不成立，退化为词覆盖；`make_idf/corpus_size/keyword_doc_freqs`（两个 store 都实现了）是**死代码**。strict 0.8 门槛读的是未校准分。
- **[high] embedding F4**（`storage/sqlite_store.py:236-244`）：`cosine=1-d²/2` 只在单位向量成立；只有 `LocalEmbedder` 归一，`ApiEmbedder`/`CustomHttpEmbedder` 原样返回。用 DashScope/Cohere/自建网关等未归一 provider 时，相似度被 `max(0,…)` 夹成 ~0，向量命中在 RRF/rerank 里被洗掉。
- **[low] 遗忘F2**（`searcher.py:148`）：检索 recency 硬编码 `0.99^hours`，忽略配置的 `decay_factor`（仅用于遗忘 TTL）；调小 decay 只延长存活不改排序，且 0.99/小时让几天前的记忆迅速被埋。

**统一修复方向**: TTL 设可配最小地板、`importance_score==0` 当中性 5.0、新记忆给宽限；strict 门槛在单一尺度上施加（pool 与 tail 分别阈值，或全集统一打分后再 floor）并为 bge sigmoid 重定门槛；接通 IDF 或删除死 API 并改文档；在 Api/CustomHttp embedder 或存储边界统一做单位归一；recency 暴露半衰期配置。

### C6 · 图通道形同虚设 / 跨 partition 泄漏
- **[medium] 召回F4**（`graph/knowledge_graph.py:226-243`）：`search_tags` 判断"整条小写 query 是否为单个 tag 的子串"。tag 是单概念短词，正常多词查询几乎永不命中→`_graph_search` 长期返回 `[]`。"3-路并行召回"实为 2 路。
- **[medium] 召回F1**（`searcher.py:101,417-446`）：`_graph_search` **不接 `partition_ids`、不按 partition 过滤**（vector/keyword 都过滤）；当图通道偶然命中时会把别的 partition 的记忆注入结果——隔离/保密缺口（触发面因 F4 而窄）。

**统一修复方向**: 按 query token 逐个匹配 tag，或把 graph 从头部 RRF 移除只保留 `_graph_expand_from_results`，并据实更新文档（与内部备忘 `bionic-recall-pseudo-claim` 一致）；把 `partition_ids` 贯穿 `_graph_search`。

---

## 四、其余确认缺陷（按维度）

### 安装
- **[high] 安装F4**（`service_manager.py:347,358`）：systemd `ExecStart={cmd}` 用 `' '.join` 拼接，binary/python 路径含空格则按词拆分启动失败（Windows wrapper 有逐参引号，Linux 没有）。修复：`shlex.quote` 每个 token。
- **[medium] 安装F5 / [low] 启动F9**（`service_manager.py:193-208`）：launchd plist 把 workspace 路径裸插进 XML `<string>`，含 `&`/`<`/`>` 即生成非法 XML，`launchctl bootstrap` 拒绝。修复：`xml.sax.saxutils.escape`。（systemd 是 INI，不适用 XML 转义——其真正隐患是 F4。）
- **[low] 安装F6**（`integrations/codex/cli.py:19-48`）：`--scope user|project` 是空摆设，从不传给 `codex mcp add/remove`，project 与 user 等价。修复：透传或直接删掉该选项。
- **[low] 安装F7**（`service_manager.py:545-564`）：Windows uninstall 只删任务注册，留下 `hebb-serve.cmd`/`HebbMind.xml` 孤儿。修复：删 wrapper/XML 并尝试 rmdir。
- **[low] 安装F8**（`cli/commands/setup.py:42-73`）：setup 在 prefetch+verify **之前**就把 model/dim/provider 写进 hebb.json，下载失败则配置指向不存在的模型，且重跑不会自愈。修复：verify 成功后再单次落配置。
- **[low] 安装F10**（`service_manager.py:211-214`）：launchd `KeepAlive=<true/>`（任何退出都重启）+ 5s ThrottleInterval，坏配置下紧密崩溃循环、无退避、不上报真因。修复：`KeepAlive={SuccessfulExit:false}`，`_serve` 快速失败并在 status/doctor 暴露。

### 启动
- **[high] 启动F2**（`service_manager.py:211-266`）：macOS `service stop` 因 `KeepAlive=true` 实为**空操作**（仅 SIGTERM，launchd 秒级重启）；`restart` 用 `kickstart -k` 恰好能用而掩盖。修复：`stop()` 用 `bootout`，或 KeepAlive 条件化。
- **[medium] 启动F6**（`scheduler/manager.py:134-145`）：`auto_upgrade_mode='auto'` 文档承诺自动升级，但 boot 只跑 `_run_upgrade_check`（纯版本查询），无 apply 代码（设计文档自承 "PR-2"）。修复：实现 apply 或把 `auto` 暂别名为 `notify`。

### 写入
- **[low] 写入F8**（`sqlite_store.py:48-82`）：写入路径**全程无去重**（无内容哈希、无 (partition,session,turn) 唯一约束），叠加 F5 重试与 hook 每轮触发会累积重复。修复：对 ingest/hook 源加 (partition,session,turn) 唯一索引或内容哈希 `INSERT OR IGNORE`。
- **[low] 写入F10**（`ingest/normalizer.py:47-52`）：ingest 只调 `strip_noise()`，没用更强的 `clean_user_input()`（strip code/html/base64 + greeting 过滤），导致导入把代码块/HTML/base64 整段当记忆存（仅截到 10000 字）。修复：normalize 改用 `clean_user_input()`。

### 召回
- **[low] 召回F8**（`server/routers/search.py:51-53`）：REST `/search`（含 console Search 页）默认开 access-strengthening，浏览/反复查询会改写 recency 与遗忘 TTL，把"人看了几次"误当"agent 用了几次"。修复：仅对 strict/agent 面强化，或 console 走只读端点。

### 巩固
- **[medium] 巩固F4**（`agents/consolidation_agent.py:122-138`）：非 session 路径缺空输出守卫（session 路径有），LLM 空回复也照写内容再删源；conflict-update 写进 LLM 给的 id 无关系校验、不重嵌。修复：加空决策守卫；conflict 只针对召回到的 id 并重嵌。
- **[medium] 巩固F8**（`consolidation_agent.py:315-322`，两后端、3 处 135/319/511）：conflict-update 改 content + FTS 但**从不重写 memory_embeddings**，向量停留旧文本。修复：任何 conflict-update 后 `update_embedding` 重嵌。
- **[low] 巩固F1**（`consolidation_agent.py:326-361`）：SQL 即时 commit 而 kg 仅批末 `save()`，崩溃窗口内 graph 引用已删 id、新记忆未打 tag，无 reconcile。（注：孤儿节点运行时无害，检索 `if memory:` 跳过死 id。）修复：每 SQL 单元前 save，启动加 `reconcile(store)`。

### 遗忘
- **[medium] 遗忘F5**（`scheduler/manager.py:113-125`）：每次 sweep 对全部非 HIPPOCAMPUS 记忆**逐条 commit** 重写 expires_at（"仅为可见性"）+ 逐条删除，无批处理无 LIMIT，万级语料下 O(N) 串行 commit 阻塞 HTTP。修复：单 UPDATE/executemany 批量，仅在实质变化时落 expires_at，批量删除。
- **[medium] 遗忘F6**（`server/routers/admin.py:68-78`）：手动 `/forget` 直接 `delete_expired()`，删任何 `expires_at<now` 的行，与策略/强化脱钩——被强化（`last_accessed_at` 更新但 `expires_at` 未重算）的记忆仍会被删。修复：`/forget` 先跑策略重算，或强化时同步刷新 expires_at。
- **[low] 遗忘F9**（`sqlite_store.py:219-288`）：`search_by_vector/search_by_keyword` 裸 `except Exception: return []`，删除/巩固故障导致连接损坏时召回静默归零、无日志。修复：只捕获特定 vec0/sqlite 错误，未知异常 `error` 级带 `exc_info` 再返回。

### embedding
- **[low] embedding F5**（`embedding/http_custom.py:192-195`）：`CustomHttpEmbedder` 的 `httpx.AsyncClient` 无 `close()`，lifespan/`HebbMemory.close()` 都不关 embedder，重启/反复 test 泄漏连接池。修复：协议加 `aclose()` 并在 lifespan/close 调用。
- **[medium] embedding F8**（`embedding/factory.py:129-155`）：API/custom provider 维度启动时探测，探测失败**静默回退到猜测的 384**；端点恢复后真实 1024 维写入全失败（F2）直到重启。修复：探测失败则返回 NoopEmbedder 或重试，doctor 校验声明维度 vs 实际。
- **[low] embedding F9**（`cli/commands/memory.py:163-224`）：reembed 用 `OFFSET` 分页扫一个会变动的表，并发 insert/delete 会重现或跳过 id，"稳定工作集"注释言过其实。修复：keyset 分页（`WHERE id>last_id`）。
- **[low] LLM配置F6 / embedding 关联**（`server/app.py:38-39`）：启动检测到的真实维度只钉到内存 settings，**从不回写 hebb.json**，导致 `config get`/`/config`/model status 报陈旧维度。修复：检测后与文件不一致即持久化。

### LLM 配置
- **[high] LLM配置F2**（`config/settings.py:34-39` vs `embedding/factory.py:76-81`）：文档承诺 embedding key/url 回退到 llm_*，**实现明确不回退**；只设 llm_* 而选 `embedding_provider='api'` 时缺 base_url→返回 NoopEmbedder→向量召回静默关闭，仅一条 log。修复：实现回退，或改文档并在 doctor 暴露 NoopEmbedder 降级。
- **[medium] LLM配置F3**（`scheduler/manager.py:87-98`）：API `consolidate()` 有 `if not llm_model: skip` 守卫，**调度路径没有**，`model=None` 直达 litellm，开箱即装每天刷一次完整 traceback。修复：调度路径加同样守卫。
- **[medium] LLM配置F4**（`cli/commands/doctor.py:57-60`；前端 `settings.js:274` 同病）：doctor 说巩固门槛是 `llm_api_key`，真实门槛是 `llm_model`——本地/代理模型（无 api_key）被误报禁用，设了 key 但无 model 反而显示 OK。修复：以 `llm_model` 为准。
- **[medium] LLM配置F5**（`config/loader.py:113-136`）：`update_config_field` 对 hebb.json 非原子读-改-全量重写，无文件锁无 temp-rename；server PUT 与 CLI set 跨进程互踩，崩溃中途留下损坏 json 致所有命令失败。修复：写 temp + `os.replace` 原子落盘 + 文件锁。
- **[low] LLM配置F7**（`config/routers/config.py:146-237`）：掩码检测把"含 `****` 子串"当占位符，真实含 `****` 的密钥会被静默替换为存储值/None。修复：用不可碰撞的哨兵或显式 `use_stored_key` 布尔。
- **[low] LLM配置F9**（`config/loader.py:1-8`）：模块 docstring 称"无环境变量覆盖"，但同模块读 `HEBB_AUTO_UPGRADE`/`HEBB_HOME` 覆盖。修复：更正 docstring 列出 env 覆盖与优先级。

### hook
- **[low] hook F2**（`integrations/claude_code/recall.py:87-118`）：HTTP 调用有 try/except，但**结果处理块在外面**，`r["memory"]`/`mem["content"]` 硬取键，响应结构漂移即抛 traceback 到 Claude Code（破坏"hook 不得干扰宿主"约定）。修复：结果迭代也包 try/except 或用 `.get` 跳过。
- **[low] hook F3**：同 C0-2，`.codex/hooks.json` 的 `hebb cc write` 失效（git 跟踪、会随仓库发出）。
- **[low] hook F4**（`integrations/claude_code/stop.py:87-99`）：Stop 写入无去重/幂等，Claude Code 对同一末轮重复触发 Stop 时重复建记忆（有 `metadata.turn` 可去重却未用）。修复：服务端按 (source,session_id,turn) upsert 或 hook 端先查再 POST。
- **[low] hook F6**（`recall.py:87-99`）：取 `_TOP_K_FETCH=20`→剔当前 session→截 `_TOP_K_RETURN=10`，长 session 主导前 20 时跨 session 召回被剔到不足 10（恰是跨 session 召回最有价值的场景）。修复：把 session 排除下推到 search 请求，或自适应过取。

### console
- **[high] console F3 / F4**（`memories.js:39-53`, `search.js:69-112`）：Memories 与 Search 页把 agent 可影响的 `content`/`tags` 裸插 `innerHTML`（兄弟组件 `partitions.js/graph.js` 都用 `esc()`），构成**存储型 XSS**；叠加 F1 零鉴权可被链到取密钥/改配置。（`partition_id` 因 `^mem_[a-z0-9_]+$` 校验不可注入。）修复：所有用户派生字段统一走 `esc()`，textarea 用 DOM 赋值。
- **[low] console F10**（`memories.js/search.js/graph.js/settings.js`）：大量界面文案硬编码英文绕过 `t()`，切 ZH 后 Memories/Search/Settings/Graph 仍是英文。修复：文案全走 `t()` 并补齐 ZH 键，加 lint 检测模板里的裸字符串。

---

## 五、被证伪或显著降级（20 条，供回溯）

skeptic 重读源码后判为 not-a-bug 或机制错误（择要）：

- **安装F9 / console F9** `_coerce_value` 误类型化：实际有类型保护，字符串字段不被破坏。
- **启动F4** graph save 迭代时被改：所有 kg mutator 同步无 await，asyncio 不会在迭代中插入。
- **启动F5** boot embedder 失败仍写空向量：实际有保护。
- **启动F7** 升级 trigger naive datetime：tz 处理无实际问题。
- **写入F9 / 遗忘F10** delete/purge 返回值忽略向量/FTS：graph 清理无条件跑，行为正确。
- **召回F5** RRF 硬编码 3 通道：通道禁用时不会过度除（实测无误）。
- **召回F6** 时间解析把年当日：解析路径无此误读。
- **召回F7 / embedding F6** reranker/HF 进程级 env race：单线程下不构成竞态。
- **召回F9** 3 路"并行"实为串行：正确但属性能 nuance 非正确性 bug。
- **召回F10** FTS 回退含 stopword：blend/coverage 已 strip，无实质偏差。
- **遗忘F7** importance 归一尺度不一致（/10 vs /5）：实际一致。
- **遗忘F8** 巩固每次新建 LLMClient 不关：有 timeout/retry，无泄漏后果。
- **embedding F3** reembed 失败不丢 id：幂等，无害。
- **embedding F10** CustomHttp 整批一请求无上限：有 per-text 模式兜底。
- **LLM配置F8** `save_settings` 丢 None 键：阻止显式 unset，属设计取舍非 bug。
- **hook F1** turn anchor 用 `list.index` 值等：重读后不构成索引错乱。
- **hook F5** hook 缺 fd 级 stdout 守卫：仅刻意写入路径，现状有保护。

> 注：部分"证伪"实为"现象存在但 auditor 机制描述不准/已被上游守卫"，非"完全无问题"。

---

## 六、修复优先级建议

**P0（发布阻断 / 安全红线，建议本周）**
1. C0-1 Docker `hebb start` → `_serve` + 冒烟测试
2. C0-2 plugin.json / .codex/hooks.json → `hebb claude-code ...` + 命令解析测试
3. C2 默认绑 `127.0.0.1` + admin/config 鉴权 + `/reveal`/test 端点不外发真实密钥 + 收紧 CORS
4. C3 维度变更不再静默 DROP 向量表（拒启动或自动重嵌）+ Edit 拒空内容
5. C5 遗忘 TTL 最小地板 + importance=0 视为中性（防当场删除）

**P1（数据完整性 / 召回质量，2–3 周）**
6. C1 后台任务独立连接 + 写入显式事务/回滚 + 统一 kg 锁
7. C4 安装固化绝对 `HEBB_HOME` 写入 unit，重装需确认
8. C5 strict 0.8 门槛改单尺度 + bge sigmoid 重定门槛；非本地 embedder 单位归一
9. console XSS：统一 `esc()`
10. 写入：partition 校验、批量 ingest 单事务、zip strict、去重

**P2（一致性 / 文档 / 体验）**
11. C6 图通道：按 token 匹配或下线 + partition 过滤 + 文档据实
12. IDF 接通或删除死代码；recency 半衰期可配；doctor/embedding key 回退口径修正
13. systemd `shlex.quote` / plist XML 转义 / Windows uninstall 清理 / KeepAlive 条件化 / macOS stop 真停
14. i18n 补齐；CLI/server 掩码统一；hook 结果处理加 try/except 与去重
