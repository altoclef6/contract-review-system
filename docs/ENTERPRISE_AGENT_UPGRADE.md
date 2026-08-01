# 企业协作与 Agent 升级说明

## 当前架构

- 后端：FastAPI、Pydantic、SQLAlchemy、Alembic；Web 模式可选 PostgreSQL，桌面模式使用 SQLite。
- 前端：Vue 3、TypeScript、Pinia、Vue Router、Element Plus。
- 原有业务：合同、版本、审查任务、风险、报告、规则、知识库、审批、通知和普通 AI 对话。
- 原有账号在非数据库模式使用 JSON；本次升级后，启用数据库时账号、企业和部门均使用数据库。

## 本阶段已完成

- 新增 `companies`、`departments`，用户增加 `company_id`、`department_id`、`job_title`、`token_version`。
- 合同及核心审查资源增加租户字段；合同服务先校验企业，再按角色校验本人或企业范围。
- 角色扩展为系统管理员、企业管理员、法务负责人、法务、企业成员，并增加企业、部门、成员、审计和 Agent 权限码。
- 新增企业概览、部门创建、企业成员列表和成员创建 API。
- 审计日志增加企业、资源、请求、IP、User-Agent 和结果字段。
- 新增持久化 Agent 任务、步骤、工具调用和事件表。
- 新增 Agent 状态机、工具白名单、企业范围查询和高风险工具人工确认。
- 新增前端“AI 工作台”和“企业与成员”页面。
- 新增全局 AI 浮球与右侧上下文抽屉，可识别当前页面、合同 ID 和风险 ID。

## 迁移

迁移文件：`migrations/versions/20260729_0008_enterprise_tenancy_agents.py`

```powershell
$env:DATABASE_ENABLED = "true"
python -m alembic upgrade head
python -m alembic current
```

升级前应先备份数据库。生产环境应在维护窗口执行，并先在数据库副本完成
`upgrade -> downgrade -> upgrade` 演练。本迁移保留旧记录；旧合同的 `company_id`
为空，需要管理员在正式开放多租户访问前执行数据归属回填。

## 环境变量与密钥

必须通过环境变量或部署平台 Secret 注入：

- `JWT_SECRET_KEY`
- `BOOTSTRAP_ADMIN_EMAIL`
- `BOOTSTRAP_ADMIN_PASSWORD`
- `DATABASE_URL`
- `MODEL_CREDENTIAL_ENCRYPTION_KEY`
- `LLM_API_KEY`、`OPENAI_API_KEY` 或 `DEEPSEEK_API_KEY`

浏览器端不保存 API Key。模型密钥只在后端读取；前端只调用本系统 API。

## 测试账号

系统只自动创建一个启动管理员，账号由 `BOOTSTRAP_ADMIN_EMAIL` 和
`BOOTSTRAP_ADMIN_PASSWORD` 指定。不要在源码或文档中写入真实密码。

启动管理员登录后可在“企业与成员”中创建：

- 企业管理员：`company_admin`
- 法务负责人：`legal_manager`
- 法务成员：`legal`
- 企业成员：`member`

测试环境建议使用一次性密码，测试结束后立即删除测试数据库。

## 权限边界

| 角色 | 数据范围 | 组织管理 | Agent 执行 | 高风险确认 |
|---|---|---:|---:|---:|
| 系统管理员 | 当前企业及系统管理范围 | 是 | 是 | 是 |
| 企业管理员 | 当前企业 | 是 | 是 | 是 |
| 法务负责人 | 当前企业合同 | 成员管理 | 是 | 是 |
| 法务成员 | 当前企业合同 | 否 | 是 | 是 |
| 企业成员 | 本人合同 | 否 | 是 | 否 |

前端角色限制仅用于交互提示，最终权限始终由后端依赖与资源访问校验决定。

## Agent 工具

| 工具 | 风险级别 | 是否确认 |
|---|---|---:|
| `contract.search` | low | 否 |
| `contract.read` | low | 否 |
| `contract.compare_versions` | low | 否 |
| `clause.find` | low | 否 |
| `knowledge.search` | low | 否 |
| `risk.summarize` | low | 否 |
| `report.generate` | high | 是 |

当前状态：`created -> planning -> running -> waiting_confirmation ->
completed`。拒绝高风险工具后进入 `cancelled`，异常进入 `failed`。

## 启动

```powershell
python -m alembic upgrade head
python -m uvicorn contract_review.main:app --host 127.0.0.1 --port 8000
cd frontend
pnpm install
pnpm dev
```

桌面端仍使用原 Tauri 启动方式。本阶段只更新源码和前端构建产物，未生成新的
Windows EXE。

## 验证结果

- 新增企业化服务测试：3 passed。
- 认证与新增企业化测试：8 passed。
- 合同、跨资源授权、Dashboard 隔离回归：8 passed。
- Alembic 全新 SQLite 升级到 `20260729_0008` 成功，创建 20 张表。
- `vue-tsc -b` 通过。
- `vite build` 通过。

完整测试套件一次性运行时，现有桌面启动令牌测试污染全局环境，导致随后接口统一
返回 401；隔离运行相关旧测试均通过。该测试隔离问题尚未在本阶段修改。

## 尚未完成

- 将所有历史 AI 调用统一迁移到单一 AI Service，并落库逐次 Token/成本统计。
- 企业知识库对所有旧数据的租户回填与公共法规库分层。
- 合同共享、访客授权和自定义角色编辑器。
- Agent 的真实合同检索、条款定位、知识检索和报告生成适配器；当前框架会持久化
  计划、步骤、工具调用、证据标志和确认记录，但安全工具仍是受控占位执行器。
- Agent 工具失败后的用户触发重试 API。
- 生成新 EXE、安装包及桌面端升级验证。

这些项目不能视为已完成，也不应在对外说明中作为现有能力宣传。
