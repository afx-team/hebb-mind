# Docker 部署

Hippocampus 提供了开箱即用的 Docker 部署方案。

## 快速启动

```bash
docker compose -f docker/docker-compose.yml up
```

服务启动后访问 `http://localhost:8321/` 即可使用。

## 环境变量

Docker 部署通过环境变量配置 LLM，在启动前设置：

```bash
export HIPPOCAMPUS_LLM_API_KEY=sk-your-key
export HIPPOCAMPUS_LLM_MODEL=openai/gpt-4o-mini

docker compose -f docker/docker-compose.yml up
```

可用的环境变量：

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `HIPPOCAMPUS_LLM_API_KEY` | - | LLM API 密钥 |
| `HIPPOCAMPUS_LLM_MODEL` | `openai/gpt-4o-mini` | LLM 模型标识 |
| `HIPPOCAMPUS_LLM_BASE_URL` | - | 自定义 LLM 端点 |
| `HIPPOCAMPUS_GITHUB_CLIENT_ID` | - | GitHub OAuth Client ID |
| `HIPPOCAMPUS_GITHUB_CLIENT_SECRET` | - | GitHub OAuth Client Secret |
| `HIPPOCAMPUS_JWT_SECRET` | `change-me-in-production` | JWT 签名密钥 |

## 数据持久化

容器使用 Docker 命名卷 `hippocampus-data` 持久化数据库和知识图谱文件。即使容器重启，数据也不会丢失。

## 后台运行

```bash
docker compose -f docker/docker-compose.yml up -d
```

## 查看日志

```bash
docker compose -f docker/docker-compose.yml logs -f
```

## 停止服务

```bash
docker compose -f docker/docker-compose.yml down
```
