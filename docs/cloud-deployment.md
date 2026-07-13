# 云服务器部署指南

本文档用于将当前项目部署到一台 Linux 云服务器。系统提供 AI 辅助合同风险审查，不构成正式法律意见，重要合同应由专业法务或律师结合交易背景进行人工复核。

## 1. 部署前准备

- 建议使用 4 核 CPU、8 GB 内存及 40 GB 以上磁盘；OCR 和 LibreOffice 会增加内存占用。
- 安装 Docker Engine 与 Docker Compose v2。
- 仅向公网开放 80/443；PostgreSQL、Redis 和后端 8000 端口无需公网开放。
- 准备域名和 HTTPS 证书。生产合同可能包含敏感信息，不应使用纯 HTTP 传输。

## 2. 配置环境变量

在服务器项目根目录由 `.env.example` 复制出 `.env`，只在服务器本地填写。不要提交 `.env`。

必须替换以下值：

- `POSTGRES_PASSWORD`：数据库强密码。
- `JWT_SECRET_KEY`：至少 32 个随机字符。
- `BOOTSTRAP_ADMIN_PASSWORD`：至少 12 个字符的强密码。
- `MODEL_CREDENTIAL_ENCRYPTION_KEY`：服务端模型凭据加密主密钥。
- `ALLOWED_ORIGINS`：前端的完整 HTTPS 来源，例如 `https://contracts.example.com`。
- `TRUSTED_HOSTS`：允许的域名，例如 `contracts.example.com`。

如使用 DeepSeek 兼容接口，配置：

```dotenv
LLM_PROVIDER=deepseek
LLM_MODEL_NAME=deepseek-chat
LLM_BASE_URL=https://api.deepseek.com/v1
DEEPSEEK_API_KEY=在服务器本地填写
ENABLE_LLM=true
```

模型不可用时，任务会保留确定性规则结果并明确记录 AI 未完成，不会伪造 AI 结论。若暂不使用外部模型，将 `ENABLE_LLM=false`。

## 3. 配置检查和启动

```bash
docker compose config --quiet
docker compose build
docker compose up -d
docker compose ps
docker compose logs --tail=100 backend worker
```

启动时后端会执行 `alembic upgrade head`。生产模式不会回退到进程内同步任务，Redis/Celery 异常会明确返回任务错误。

健康检查：

```bash
curl --fail http://127.0.0.1:8080/api/v1/health
```

## 4. HTTPS 与反向代理

容器前端默认映射到服务器 `8080`。建议由宿主机 Nginx、Caddy 或云负载均衡终止 TLS，再代理到 `127.0.0.1:8080`。将安全组中的 8080 端口限制为本机或内网访问。

上传上限需在外层代理同步设为至少 50 MB，并保留较长的读取超时。不要让 `/data`、上传目录或报告目录成为静态目录。

## 5. 数据与备份

以下命名卷需要持久化备份：

- `postgres_data`：关系数据库。
- `redis_data`：任务队列持久化数据。
- `app_data`：上传文件、报告和兼容数据存储。

备份前应暂停写入或使用数据库一致性备份。恢复演练应在隔离环境进行，不要用真实合同做演示。

## 6. 更新与回滚

更新前记录当前 commit、备份数据库和命名卷，然后执行：

```bash
docker compose build
docker compose up -d
docker compose ps
```

代码回滚应切回已验证 commit 后重新构建镜像。数据库回滚优先从备份恢复；不要在未验证迁移可逆性时直接执行 Alembic downgrade。

## 7. 上线验收

- 登录、修改初始管理员密码并验证退出。
- 上传虚构测试合同，观察真实任务阶段，确认规则风险可在模型失败时保留。
- 验证合同下载、报告下载和无权访问均受权限控制。
- 验证风险确认、驳回、整改、评论与审计日志。
- 验证规则中心、知识库、版本对比和用户权限页面。
- 检查容器日志不包含合同全文、密码或模型密钥。
- 设置数据库、磁盘、队列积压和容器健康告警。
