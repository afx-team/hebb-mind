# 存储后端

Hippocampus 支持两种存储后端：SQLite（默认）和 PostgreSQL。

## SQLite（默认）

零配置开箱即用，适合本地开发和单机部署。

**特点：**

- 无需额外安装数据库
- 数据存储在单个 `hippocampus.db` 文件中
- 向量检索使用 `sqlite-vec` 扩展
- 全文搜索使用 `FTS5` 索引
- 适合中小规模数据（万级记忆）

**配置：**

```json
{
  "storage_type": "sqlite",
  "db_path": "hippocampus.db"
}
```

这是默认配置，`hippocampus init` 后无需修改即可使用。

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
pip install afx-hippocampus[pg]
```

**配置：**

```json
{
  "storage_type": "postgresql",
  "pg_url": "postgresql://user:password@localhost:5432/hippocampus",
  "pg_pool_min": 2,
  "pg_pool_max": 10
}
```

通过 CLI 配置：

```bash
hippocampus config set storage_type postgresql
hippocampus config set pg_url "postgresql://user:password@localhost:5432/hippocampus"
```

**PostgreSQL 前置条件：**

确保 PostgreSQL 已安装 pgvector 扩展：

```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

首次启动时，Hippocampus 会自动执行数据库迁移，创建所需的表和索引。

## 后端切换

切换存储后端需要修改 `storage_type` 和相关配置后重启服务。注意：切换后端不会自动迁移数据。如需迁移，可通过 API 导出记忆后重新导入。

```bash
# 切换到 PostgreSQL
hippocampus config set storage_type postgresql
hippocampus config set pg_url "postgresql://user:pass@localhost/hippocampus"
hippocampus restart
```
