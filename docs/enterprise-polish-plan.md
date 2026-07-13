# 企业级完善实施计划

> 基线：2026-07-13 项目审计。本文是后续分阶段实施计划，不代表功能已经完成。每个阶段必须单独开始、单独验证、结束后等待用户确认；不得自动进入下一阶段。

## 通用实施约束

- 保持当前分支，不自动创建/切换分支，不提交、不 push、不创建 PR，除非用户在具体阶段明确授权。
- 每阶段开始记录根目录、分支、HEAD、`git status`、未提交文件、预计文件和冲突风险。
- 不读取、覆盖或提交 `.env`，不接触真实合同、密钥、日志、数据库和上传文件。
- 优先扩展现有组件、Service、Schema 和路由；接口演进优先向后兼容，不创建空壳页面。
- 数据库结构只通过 Alembic；数据迁移先校验再切换，保留旧数据只读回退路径。
- 每阶段至少运行定向后端测试、全量 `pytest`、前端 build；涉及迁移时检查 heads 和临时 PostgreSQL upgrade；涉及 Docker 时检查 Compose。
- AI 不可用时保留确定性规则结果并明确标注；禁止用定时器、随机数、Mock 或写死数据伪装真实进度和指标。

## 阶段 1：企业级应用框架

### 修改范围

统一应用壳、导航、角色可见性、页面状态和设计 token；修复登录页默认凭据展示与前端权限路由，不改变主要业务 API。

### 预计文件

`frontend/src/views/AppLayout.vue`、`LoginView.vue`、`frontend/src/router.ts`、`stores/auth.ts`、`api.ts`、`styles.css`；可能新增 `components/PageState.vue`、`composables/usePermission.ts` 和前端测试配置。

### 数据库变化

无。

### API 变化

原则上无；若需要菜单权限，复用 `/auth/me` 的角色/权限或仅向响应追加兼容字段。

### 页面变化

导航按后端权限隐藏；统一 403/404/空/加载/失败状态；登录不预填生产凭据；保留现有 LegalTech 配色和布局。

### 测试方法

路由权限、登录恢复、401 刷新 single-flight、接口错误组件测试；`pnpm run build`；后端认证回归。

### 验收标准

Employee 不再进入无权页面；刷新后登录和深链恢复；所有主页面有明确失败态；1366/1440/1920 和窄屏无横向溢出。

### 风险

旧本地 token 状态与新 Store 迁移冲突；通过兼容读取和一次性安全清理降低风险，禁止 `localStorage.clear()` 清空无关数据。

## 阶段 2：企业工作台

### 修改范围

把 Dashboard 改为按角色展示真实合同、任务、风险、人工待办和系统指标；优化 ECharts 按需导入。

### 预计文件

`frontend/src/views/DashboardView.vue`、图表组件、`src/contract_review/api/v1/endpoints/analysis_history.py`、`services/history_service.py`、监控 Schema/Service 与测试。

### 数据库变化

若阶段 3 尚未切数据库，本阶段不新增业务表；统计查询为后续 DB 切换预留仓储接口。

### API 变化

新增或扩展 `/dashboard/summary`，按用户授权范围返回聚合值；现有分析历史接口保持兼容。

### 页面变化

真实 KPI、待办队列、近期合同、失败/空状态；不展示无法从后端计算的成本或成功率。

### 测试方法

按 Admin/Legal/Employee 验证统计范围；空数据和接口失败组件测试；chunk size 对比；全量 build。

### 验收标准

指标均能追溯后端数据；Legal/Employee 看不到越权聚合；Dashboard chunk 明显下降且设置 bundle budget。

### 风险

当前 JSON 历史缺少部分指标字段；缺失指标显示“未进行真实测量”，不得估算。

## 阶段 3：合同中心

### 修改范围

让合同、文件和版本形成统一主记录；补齐详情、编辑、归档、删除、恢复、版本上传和授权范围。

### 预计文件

合同模型/Schema/Service/路由、文件存储服务、`ContractsView.vue`、合同详情和版本组件、数据导入脚本、Alembic migration、IDOR 测试。

### 数据库变化

新增 `contract_assignments`、`contract_access_grants` 或等价授权模型；补 `contract_versions.storage_key/parse_status/parse_confidence/ocr_confidence`。设计一次性 JSON→DB 导入记录和校验表/字段。

### API 变化

保留现有合同 CRUD；新增版本文件上传、授权/指派、详情聚合接口；统一逐资源 scope 校验和安全 404。

### 页面变化

合同列表真实分页、详情抽屉/页、版本时间线、归档站和授权管理；复用现有布局。

### 测试方法

空 PostgreSQL migration；JSON 导入数量/哈希/ID 校验；Employee owner、Legal assigned、Admin audited 的 IDOR 矩阵；上传下载安全回归。

### 验收标准

新上传文件必属于合同和不可变版本；所有合同读取/写入/批量操作逐项授权；旧 JSON 数据可验证导入且原文件保留只读回退。

### 风险

JSON 中嵌套版本与数据库模型不完全一致。必须先 dry-run 和生成差异报告，不在迁移中删除源文件。

## 阶段 4：三栏审查工作区

### 修改范围

将当前审查页和 Reader 整合为“原文/风险/依据与建议”三栏工作区，上传审查必须基于合同版本，兼容旧 review 深链。

### 预计文件

`ReviewView.vue`、`ReaderView.vue`、新的工作区子组件、文档解析/定位 Schema、reader/reviews 路由与 Service、PDF worker 配置和测试。

### 数据库变化

补充版本解析产物、页/段/坐标或独立 `document_segments` 表；Review 与 contract/version 外键改为必需或分阶段约束。

### API 变化

新增按页/段读取解析内容、定位风险和受权原文件流接口；保留 `/reader/{review_id}` 兼容入口并修复 owner/assignment 校验。

### 页面变化

左栏原文、中央风险、右栏依据/建议；点击风险定位页段；低置信 OCR 显示人工确认；完整 loading/error/empty 状态。

### 测试方法

PDF/DOCX/图片定位；跨用户 Reader IDOR；Blob URL 释放；键盘操作、窄屏降级和组件测试；真实文件仅使用虚构样本。

### 验收标准

每个风险能定位原文或明确显示“无法可靠定位”；任何用户不能通过 review ID 读取未授权文件；旧报告仍可查看。

### 风险

旧报告缺结构化 location。通过只读兼容转换器降级到文本搜索，不伪造页码或坐标。

## 阶段 5：风险持久化和人工复核

### 修改范围

把统一 `ExplainableRisk` 接入数据库和前端；实现接受、驳回、修改和解决状态，保留 AI 原始值与人工终值。

### 预计文件

`database/models.py`、risk Schema/Repository/Service/路由、审计服务、Review pipeline、工作区风险组件、复核队列页面和测试。

### 数据库变化

使用现有 `risk_findings` 并新增 `risk_review_events`；必要时增加 `version_id/reviewer_id/reviewed_at/algorithm_version`，全部使用 Alembic。

### API 变化

新增 `/reviews/{id}/risks`、`/risks/{id}`、`/risks/{id}/review` 和批量复核；批量操作逐项授权。

### 页面变化

风险筛选、原文定位、依据、AI 原建议、人工终意见和事件历史；高风险默认待人工复核。

### 测试方法

状态机、并发更新、审计、IDOR、历史不可覆盖、报告只消费已验证风险；前端接受/驳回/修改流程测试。

### 验收标准

每个风险有来源、原文或明确缺失标记；高风险待复核；人工动作可审计且不能覆盖 AI 原始建议；报告区分 AI 与人工结论。

### 风险

旧风险字典字段不一致。建立确定性转换和 schema version，转换失败记录原因而不是写虚假默认值。

## 阶段 6：异步审查任务

### 修改范围

将同步审查拆成持久化阶段任务，接入 Celery/Redis；前端进度完全来自后端状态，支持重试、取消、恢复和幂等。

### 预计文件

Celery jobs/app、ReviewTask 模型/Schema/Service/路由、LangGraph runner、ReviewView/Store、监控指标、Docker Compose 和测试。

### 数据库变化

新增 `review_tasks`、`review_stage_runs`；唯一幂等键，阶段时间、重试、Celery task ID、取消和安全错误摘要。

### API 变化

`POST /review-tasks`、`GET /review-tasks/{id}`、cancel、retry；旧 `POST /reviews` 在开发模式可兼容同步，生产不静默退化。

### 页面变化

真实阶段进度、刷新恢复、明确同步开发模式标识、失败原因、重试/取消按钮。

### 测试方法

Celery eager Mock 结构测试 + Redis/Celery 集成；幂等、重复投递、超时、指数退避、worker 重启、取消、Redis 不可用。

### 验收标准

无定时器假进度；相同幂等键不重复扣费/写风险；失败任务状态可解释；生产 Redis/Celery 不可用时明确失败。

### 风险

同步客户端兼容和重复执行。使用 outbox/事务边界、唯一约束和 feature flag 分阶段切换。

## 阶段 7：规则中心和知识库

### 修改范围

把硬编码规则与目录知识升级为可版本化、可发布、可审计的企业管理能力；保留 60 条规则作为只读种子版本。

### 预计文件

rules registry/loaders/evaluators、知识 Service、数据库模型、管理路由、Settings/规则/知识页面、导入校验脚本和测试。

### 数据库变化

新增 `rules`、`rule_versions`、`knowledge_document_versions`、发布/创建者字段；现有知识表补 `is_test_data` 和发布状态。

### API 变化

规则 CRUD/版本/启停/试运行；知识 CRUD/版本/发布/失效/检索预览；返回 document ID、article、状态和命中片段。

### 页面变化

规则列表与版本编辑、知识条目和效力状态、测试数据显著标签、检索预览；Employee 不展示管理入口。

### 测试方法

规则确定性、numeric evaluator、版本回滚、过期/废止过滤、企业制度与法律分类、低分阈值、Prompt 注入和依据真实性。

### 验收标准

Review 固定规则/知识版本；LLM 只能引用检索返回的真实 ID；未命中可靠依据时降级并要求人工复核。

### 风险

规则版本改变结果口径，知识数据可能不权威。禁止网络自动抓取后冒充完整法律库，发布必须人工审核。

## 阶段 8：合同版本对比和反馈分析

### 修改范围

把现有文本 diff 和风险映射接入版本页面，形成原始、修改、复审、最终版本整改闭环，并基于人工事件计算反馈指标。

### 预计文件

版本比较 Service/Schema/路由、合同详情/对比组件、风险映射组件、报告与统计 Service、测试。

### 数据库变化

补版本回滚事件、比较算法版本、风险映射确认字段；不覆盖任何原文件或历史 review。

### API 变化

版本对比详情、风险映射确认、建议复制、回滚记录；反馈统计按授权范围聚合。

### 页面变化

条款新增/删除/修改对比，风险 unresolved/partial/resolved/new 标记，人工映射修正和反馈趋势。

### 测试方法

版本不可变、哈希、父链、diff 稳定性、旧风险映射、历史不覆盖、授权和统计口径测试。

### 验收标准

新版本不覆盖旧文件/风险/人工意见；每个整改状态可追溯；AI 接受/驳回率仅从真实人工事件计算。

### 风险

自动文本匹配可能误映射。低置信映射必须人工确认，保存算法版本和修正记录。

## 阶段 9：性能、安全、测试和文档

### 修改范围

集中解决 bundle、token、限流、上传隔离、迁移 CI、监控、测试和 README 真实性。

### 预计文件

前端 imports/Vite 配置/CSS、认证和中间件、文件安全、监控、CI、Docker/Nginx、测试、README 和运维文档。

### 数据库变化

新增 refresh token/session 表及必要安全索引；可能补审计保留/完整性字段。

### API 变化

logout/session revoke、监控部署保护、API docs 开关；旧 token 迁移提供明确过渡期。

### 页面变化

会话管理、安全错误提示、性能优化；不大改视觉结构。

### 测试方法

后端 coverage、核心安全 coverage、ruff、mypy、前端 lint/typecheck/unit/E2E、Docker build、secret/dependency scan、空库 migration、虚构样本端到端。

### 验收标准

所有 CI 项真实通过；前端 chunk 符合预算；核心 IDOR/上传/token 用例通过；README 只写实测数据；生产非 root、Debug 关闭、文档可配置关闭。

### 风险

安全头和 Cookie 迁移可能破坏登录或第三方模型调用；采用 report-only、双栈 token 过渡和可回滚配置。

## 阶段 10：最终验收

### 修改范围

不增加新功能；仅修复验收阻塞、生成真实报告和明确未完成项。

### 预计文件

测试/验收脚本、README、`ENTERPRISE_UPGRADE_REPORT.md`，以及针对失败的最小修复文件。

### 数据库变化

不计划新增；验证所有 migration 在全新 PostgreSQL 可执行。

### API 变化

不计划新增；冻结并导出接口清单和兼容说明。

### 页面变化

不计划新增；逐页人工验收登录、工作台、合同、审查、复核、版本、规则、知识、模型、审计和监控。

### 测试方法

全新环境 README 启动、全套 CI、本地 Docker、虚构合同 E2E；分别运行 deterministic benchmark、mocked integration，真实模型 benchmark 仅在用户主动提供可用配置且授权调用时执行。

### 验收标准

后端启动、前端构建、Compose 和镜像、迁移、核心测试、规则接入、风险定位、密钥加密、IDOR、上传下载、结构化 Agent、LLM 降级、真实任务进度、Gold 数据和评测脚本全部有可复核证据。

### 风险

OCR、模型、操作系统字体和外部服务导致环境差异。报告必须写真实原因；无法测量的数据统一写“未进行真实测量”，不得猜测或把 Mock 当真实指标。

## 阶段顺序与门禁

阶段 1–2 可在不迁移业务数据的前提下改善框架；阶段 3 是后续审查/风险/异步闭环的数据基础；阶段 4–6 依赖统一合同版本和资源授权；阶段 7–8 依赖风险持久化；阶段 9 在功能稳定后集中硬化；阶段 10 只验收。

任何阶段出现失败时，应在当前阶段修复或明确记录安全降级，不得带着已知阻塞自动进入下一阶段。每阶段结束后停止，等待用户确认。
