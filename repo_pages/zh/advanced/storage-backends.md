# 存储后端

Hebb Mind 支持两种存储后端：SQLite（默认）和 PostgreSQL。

## SQLite（默认）

零配置开箱即用，适合本地开发和单机部署。

**特点：**

- 无需额外安装数据库
- 数据存储在单个 `hebb.db` 文件中
- 向量检索使用 `sqlite-vec` 扩展
- 全文搜索使用 `FTS5` 索引
- 适合中小规模数据（万级记忆）

**配置：**

```json
{
  "storage_type": "sqlite"
}
```

这是默认配置，`hebb setup` 后无需修改即可使用。SQLite 数据库文件 `hebb.db` 自动存储在工作目录中。

## PostgreSQL + pgvector

适合生产环境和大规模数据场景。

**特点：**

- 高并发读写
- 向量检索使用 `pgvector` 扩展（支持 HNSW 索引）
- 全文搜索使用 `tsvector` + BM25
- 连接池管理
- 适合大规模数据和多实例部署

**安装扩展：**

```bash
pipx install 'hebb-mind[pg]'    # 或在 venv 内：pip install -U 'hebb-mind[pg]'
```

**配置：**

```json
{
  "storage_type": "postgresql",
  "pg_url": "postgresql://user:password@localhost:5432/hebb",
  "pg_pool_min": 2,
  "pg_pool_max": 10
}
```

通过 CLI 配置：

```bash
hebb config set storage_type postgresql
hebb config set pg_url "postgresql://user:password@localhost:5432/hebb"
```

**PostgreSQL 前置条件：**

确保 PostgreSQL 已安装 pgvector 扩展：

```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

首次启动时，Hebb Mind 会自动执行数据库迁移，创建所需的表和索引。

## 后端切换

切换存储后端需要修改 `storage_type` 和相关配置后重启服务。注意：切换后端不会自动迁移数据。如需迁移，可通过 API 导出记忆后重新导入。

```bash
# 切换到 PostgreSQL
hebb config set storage_type postgresql
hebb config set pg_url "postgresql://user:pass@localhost/hebb"
hebb service restart
```

## Docker 部署

使用官方 Docker 镜像进行容器化部署。

### 快速启动

```bash
docker run -d \
  -p 8321:8321 \
  -v hebb-data:/data \
  -e HEBB_HOME=/data \
  -e HEBB_LANGUAGE=auto \
  -e HEBB_REGION=auto \
  -e HEBB_LLM_API_KEY=sk-your-key \
  ghcr.io/afx-team/hebb-mind:latest
```

### Docker Compose

```yaml
services:
  hebb:
    image: ghcr.io/afx-team/hebb-mind:latest
    ports:
      - "8321:8321"
    volumes:
      - hebb-data:/data
    environment:
      - HEBB_HOME=/data
      - HEBB_LANGUAGE=auto
      - HEBB_REGION=auto
      - HEBB_LLM_API_KEY=${LLM_API_KEY}
      - HEBB_LLM_MODEL=openai/gpt-4o-mini

  # 可选：PostgreSQL 后端
  postgres:
    image: pgvector/pgvector:pg16
    environment:
      POSTGRES_DB: hebb
      POSTGRES_USER: hebb
      POSTGRES_PASSWORD: hebb
    volumes:
      - pg-data:/var/lib/postgresql/data

volumes:
  hebb-data:
  pg-data:
```

### 环境变量

| 变量 | 配置项 | 说明 |
|------|--------|------|
| `HEBB_HOME` | `home` | 工作目录覆盖，数据文件存储在此目录 |
| `HEBB_LANGUAGE` | setup 参数 | `auto`、`en`、`zh` 或 `multi`，容器初始化时选择默认 Embedding 模型 |
| `HEBB_REGION` | setup 参数 | `auto`、`cn` 或 `global`，容器初始化时选择模型下载源 |
| `HEBB_LLM_API_KEY` | `llm_api_key` | LLM 服务 API Key |
| `HEBB_LLM_MODEL` | `llm_model` | 模型标识（通过 LiteLLM） |
| `HEBB_LLM_BASE_URL` | `llm_base_url` | 自定义 API 端点 |
| `HEBB_STORAGE_TYPE` | `storage_type` | `sqlite` 或 `postgresql` |
| `HEBB_PG_URL` | `pg_url` | PostgreSQL 连接串 |
| `HEBB_PORT` | `port` | 服务端口（默认 8321） |

## 后台运行与开机自启

Hebb Mind 统一以操作系统后台服务方式运行，唯一入口是：

```bash
hebb service install     # 注册并启动（launchd / systemd / 任务计划程序）
hebb service uninstall   # 卸载
```

`install` 会自动写入平台原生的服务配置并立即启动。默认是**用户级**安装
（无需 `sudo` 或管理员权限）；如需系统级常驻并支持开机自启，请加
`--scope system`。

| 平台 | `hebb service install`（默认 `--scope user`）写入的资源 |
|------|--------------------------------------------------|
| macOS | `~/Library/LaunchAgents/com.hebb.server.plist`（launchd LaunchAgent） |
| Linux | `~/.config/systemd/user/hebb.service`（`systemctl --user` 单元） |
| Windows | 用户级计划任务 `HebbMind`（登录触发，`LeastPrivilege`） |

`--scope system` 会写入到 `/Library/LaunchDaemons/`、
`/etc/systemd/system/`，或注册以 SYSTEM 账号运行的计划任务 —— 均需要管理员
权限，且对所有用户都开机自启。

服务管理器实际执行的是 `hebb _serve`（内部隐藏的前台入口，不属于公开 CLI）。
控制命令与各平台日志路径见
[CLI 参考 → hebb service](../api/cli.md#hebb-service)。

### 生产环境建议

- 生产环境使用 PostgreSQL 后端
- 使用国产模型（通义千问、智谱 GLM、Kimi）时设置 `HEBB_LLM_BASE_URL`
- 挂载持久卷到 `/data` 以保留记忆数据
- 使用 `--restart unless-stopped` 实现自动恢复
