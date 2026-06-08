# 切换 Embedding 模型

`hebb setup` 第一次运行时会根据系统语言挑一个**小**的 Embedding 模型，且仅在尚未缓存时下载。默认（`--profile default`）是 `all-MiniLM-L6-v2`（384 维，英文）或 `intfloat/multilingual-e5-small`（384 维，多语言）；高质量的 bge 档 —— `BAAI/bge-large-en-v1.5` / `BAAI/bge-m3`（均 1024 维）—— 需通过 `hebb setup --profile best` 主动选用。之后任何时候 —— 即便服务已经在跑、已经写了一堆记忆 —— 都可以切到任何 [sentence-transformers](https://www.sbert.net/docs/pretrained_models.html) 兼容模型，或任何 LiteLLM 兼容的云端 Embedding API。已缓存的模型会直接复用，只有缺失的才下载。

一个常见的升级是从小默认模型换到 bge 档以获得更强检索 —— 这是一次**维度变化**（384 → 1024），请按下表「维度变了」那一行操作。

切换分三种情况，按你的实际情况看下表对应小节。

| 情况 | 发生了什么 | 需要做什么 |
|------|-----------|-----------|
| **同维度，换模型**（例如 `all-MiniLM-L6-v2` → `intfloat/multilingual-e5-small`，都是 384 维） | 已有向量仍可用，但语义已不同 | 改配置 → 重启 → 建议再 reembed 一次保持一致 |
| **维度变了**（例如 `all-MiniLM-L6-v2` 384 → `BAAI/bge-large-en-v1.5` 1024） | 启动时向量表会自动重建，旧向量丢失 | 改配置 → 重启 → **执行 `hebb memory reembed`** |
| **本地 ↔ API 切换** | provider、base_url、api_key 一起变 | 用 Web 控制台批量改，或 CLI 逐项 `config set`，然后重启 |

## 路径 A — CLI 一行流（推荐）

`hebb model prefetch --model <id>` 一条命令搞定：更新 `embedding_model` / `embedding_provider` / `embedding_dim`，下载并验证维度。

```bash
# 切到多语言 bge-m3（1024 维）
hebb model prefetch --model BAAI/bge-m3 --region auto

# 重启服务生效
hebb service restart

# 维度变了的话，重新计算所有已有记忆的向量
hebb memory reembed
```

`--region auto` 会同时探测 HuggingFace 官方源和 `hf-mirror.com`，挑响应快的；要强制可用 `--region cn`（镜像）或 `--region global`（官方）。

## 路径 B — CLI 逐项

如果模型已经在本地缓存，只想改配置：

```bash
hebb config set embedding_provider local
hebb config set embedding_model intfloat/multilingual-e5-large
hebb config set embedding_dim 1024          # 你知道维度时再设
hebb service restart
hebb memory reembed                          # 维度变了才需要
```

切到 API：

```bash
hebb config set embedding_provider api
hebb config set embedding_model openai/text-embedding-3-small
hebb config set embedding_base_url https://api.openai.com/v1
hebb config set embedding_api_key sk-...
hebb config set embedding_dim 1536
hebb service restart
hebb memory reembed
```

## 路径 C — Web 控制台

打开 <http://localhost:8321/#settings>，展开 **Embedding Configuration**：

1. **挑预设**：下拉框里选已知模型，或选 *Custom* 自己填模型 ID。
2. **Test Embedding**：本地模型未缓存时会后台下载，进度条实时更新；已缓存或 API 一次请求就返回。
3. **Save**：需要重启的字段会触发"立即重启？"弹窗，确认后服务自动重启、轮询 `/health`、页面自动刷新。
4. 如果维度变了，去终端执行 `hebb memory reembed`。（Web 控制台直接触发 reembed 在 roadmap 上。）

## reembed 到底做什么

`hebb memory reembed` 会扫描存储里所有记忆，**用当前配置**的 embedder 重新编码 content，然后把新向量写回。

```bash
hebb memory reembed                       # 所有分区
hebb memory reembed --partition mem_user  # 只处理一个分区
hebb memory reembed --dry-run             # 只统计不写入
hebb memory reembed --batch-size 128 -y   # 加大批量、跳过确认
hebb memory reembed --restart             # 强制丢弃已有断点重新开始
```

### 中断后续跑

命令会在 `<workspace>/reembed.checkpoint.json` 写一份小小的断点文件，每处理 ~32 条 flush 一次。**Ctrl-C、合盖、断电、进程被杀**都没关系 —— **再跑一次同样的命令**就会从断点继续，已处理的不会重做。

断点的身份是三元组 `(target_model, target_dim, partition_id)`。如果下次任意一项变了（换了 `embedding_model`、改了维度、加了 `--partition` 范围），旧断点会被**自动丢弃**，重新做完整扫描 —— 这正是你要的"新升级覆盖旧升级"语义。即便身份一致，也可以用 `--restart` 强制丢弃。

成功跑完后断点文件会被自动删除。典型流程：

```
$ hebb memory reembed
Re-embed every memory in all partitions using model 'BAAI/bge-m3' (dim=1024)? [y/N]: y
Scanning memories…
  Re-embedding ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 100% • 0:02:14
Re-embedded this run: 1283
Re-embed complete: 1283 memories updated. Checkpoint removed.
```

47% 时按 Ctrl-C：

```
$ hebb memory reembed
^C
Interrupted. Checkpoint saved with 678 memories remaining.

$ hebb memory reembed
Resuming previous reembed for model BAAI/bge-m3 (dim=1024): 605/1283 (47.2%) already done, 678 remaining.
  Re-embedding ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 100% • 0:01:11
Re-embed complete: 678 memories updated. Checkpoint removed.
```

## 常见问题

**Web 控制台下载卡住。** 在 Embedding 区域把 `hf_endpoint` 改成 `https://hf-mirror.com` → Save（这个字段不需要重启） → 再点 Test。或者在终端跑 `hebb model prefetch --region cn`，等价。

**`update_embedding` 报维度不匹配。** 改了 `embedding_dim` 后没重启服务 —— 向量表还是旧维度。先 `hebb service restart` 再 `hebb memory reembed`。

**敲 `hebb` 提示 command not found。** 见 [安装 → 如果还没装 pipx](./installation.md#如果还没装-pipx)。

## 相关文档

- [配置参考](./configuration.md) —— 完整 `embedding_*` 字段列表
- [多模型支持](../advanced/multi-model.md) —— 本地 vs API 取舍、语言选择
- [存储后端](../advanced/storage-backends.md) —— 向量表内部实现（SQLite vec0 / pgvector）
