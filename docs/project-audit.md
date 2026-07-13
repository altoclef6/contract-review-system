# 项目审计报告

> 审计日期：2026-07-13
> 审计范围：当前本地工作区 `D:\CodexProjects\contract-review-system`
> 分支：`feature/enterprise-contract-review-v2`
> 基线提交：`0c7104c5c62fd48e2f834dae95fa6cbe2d4808e3`
> 审计方式：源码、配置、迁移、测试、构建产物与本地命令的只读核查。未读取 `.env`，未调用真实模型，未修改业务代码。

## 1. 执行摘要

项目已经具备可演示的合同审查主链路、JWT/RBAC、合同元数据管理、60 条确定性规则、LangGraph 多节点编排、结构化知识样例、模型密钥加密、五类报告导出、版本文本对比和 58 个后端测试。但当前仍是“企业级模型与演示级运行存储并存”的过渡架构：SQLAlchemy/Alembic 定义了 12 张表，而用户、合同、审查、工作流、通知、模型配置和 Prompt 等核心服务主要仍写入本地 JSON 文件；同步 `/reviews` 又独立于合同与版本资源运行，风险表和知识表尚未接入实际业务读写。

最优先的问题不是扩展更多合同类型，而是修复资源授权边界、迁移可复现性和业务数据闭环：阅读器 PDF 接口未按审查记录所有者校验，法律角色可读取全局分析历史，工作流可绑定未校验的合同/审查 ID；首个 Alembic 迁移使用“当前 ORM 元数据”动态建表，可能与后续显式迁移重复；上传、审查、风险、人工复核、版本整改和报告没有统一持久化关联。

## 2. 当前技术架构

### 2.1 技术栈

| 层级 | 当前实现 | 审计结论 |
| --- | --- | --- |
| 前端 | Vue 3、TypeScript、Vite、Vue Router、Pinia、Axios、Element Plus、ECharts | 页面可用但覆盖面有限，无前端测试；全量 Element Plus 和 ECharts 导入造成大 chunk |
| API | FastAPI，统一 `/api/v1` 前缀，Pydantic Schema | 多数管理接口使用 `ApiResponse`，审查接口仍返回旧式裸结构，响应不完全统一 |
| 身份认证 | 自实现 HS256 JWT、PBKDF2-SHA256、角色权限映射、token version | 基础闭环存在；refresh token 缺少单令牌撤销/轮换，登录限流只在单进程内存中 |
| 业务存储 | `JsonDocumentStore` + 文件目录 | 是当前大部分服务的真实数据源，不适合多实例并发和生产恢复 |
| 数据库 | SQLAlchemy 2、PostgreSQL、Alembic | 12 张表模型存在，但除审计日志等少数路径外未成为真实业务主存储 |
| AI 编排 | LangGraph：分类、提取、规则、检索、合规、校验、精炼、协调 | 节点职责已有拆分，但节点契约和遥测不统一，RAG 结果没有真正注入合规分析 Prompt |
| 规则 | 独立 `rules` 模块，60 条默认规则 | 确定性、可定位、错误隔离已实现；数值条件、自定义规则、按合同类型加载和持久化未完成 |
| 文档处理 | pypdf、python-docx、Pillow、Tesseract、LibreOffice | 支持主要格式；缺少可靠页段坐标、OCR 置信度、复杂 PDF/图像资源限制和保留策略 |
| 异步 | Celery + Redis 配置、4 个任务入口 | OCR/提醒可执行；分析和导出任务是占位返回，前端仍使用同步请求 |
| 部署 | 非 root 后端镜像、Nginx 前端、PostgreSQL、Redis、worker、beat、健康检查 | Compose 语法有效；生产运行依赖迁移正确性，API 文档仍公开代理 |
| CI | pytest/coverage、ruff、mypy、pip-audit、前端 build、Docker build、gitleaks | 基础链路完整；无前端 lint/typecheck/test、无 Alembic 空库升级测试、无 E2E |

### 2.2 当前真实数据流

1. 前端上传文件到同步 `POST /api/v1/reviews`。
2. 后端保存随机文件名，校验扩展名、MIME、魔数和 DOCX 压缩包结构。
3. 文档加载器提取文本；LangGraph 执行分类、提取、确定性规则、知识检索和可选 LLM 节点。
4. 协调器形成旧式中文报告结构，`ReportService` 导出 JSON、DOCX、PDF、Markdown、XLSX。
5. `HistoryService` 将审查摘要写入 `data/history.json`，文件与报告保存在本地目录。
6. 前端直接显示同步响应；阅读器再用 `review_id` 读取报告、原 PDF 和文本位置。

该链路没有创建或关联数据库中的 `contracts`、`contract_versions`、`reviews`、`risk_findings` 记录，也没有可恢复的阶段任务状态。

## 3. 前端页面和路由清单

| 路由 | 页面 | 当前功能 | 权限/缺口 |
| --- | --- | --- | --- |
| `/login` | `LoginView.vue` | 登录、密码显隐 | 表单源码预填演示管理员凭据；“忘记密码”无真实交互 |
| `/dashboard` | `DashboardView.vue` | 分析统计、近期审查、ECharts 图表 | Employee 没有 `reviews:history`，却可进入页面；错误被静默吞掉 |
| `/contracts` | `ContractsView.vue` | 搜索、分页式合同列表、跳转上传 | 缺详情、编辑、归档、删除、恢复、版本和对比入口 |
| `/review` | `ReviewView.vue` | 文件选择、合同类型、同步审查、指标和风险展示 | 不创建合同/版本；进度只表示当前请求活动，不来自后端任务状态 |
| `/reader/:reviewId` | `ReaderView.vue` | PDF 预览、风险文本定位 | 后端文件接口存在 P0 IDOR；Blob URL 未释放；异常无明确状态 |
| `/assistant` | `AssistantView.vue` | 会话列表、提问、上下文连续对话 | 绑定审查记录时未验证审查记录所有权 |
| `/workflows` | `WorkflowsView.vue` | 工作流列表、状态动作 | 无创建 UI；`start_ai_review` 不触发真实 AI 审查；Legal 未按分配范围限制 |
| `/settings` | `SettingsView.vue` | 管理员新增/启用模型、Legal/Admin 查看 Prompt | 模型缺编辑/删除；Prompt 缺 CRUD；无规则和知识库管理 |

前端只有一个 Pinia Store：`stores/auth.ts`。它管理登录状态和本地用户；任务、合同、风险、通知均没有独立状态模型。路由守卫只对 `/settings` 检查角色，其余权限主要依赖后端拒绝，导致无权限用户仍能看到不可用页面。

### 3.1 API 请求封装

`frontend/src/api.ts` 使用 Axios，基址为 `/api/v1`，默认超时 120 秒；access token、refresh token 和用户对象存入 `localStorage`，401 后自动刷新一次。风险包括：

- XSS 成功时可直接读取两个 token；更稳妥的生产方案是 HttpOnly/SameSite Cookie 或短期 access token 配合受保护 refresh cookie。
- 刷新失败调用 `localStorage.clear()`，会清除同源其他应用数据。
- 多个并发 401 没有 refresh single-flight，可能发生重复刷新和状态竞争。
- 页面大量使用空 `catch {}`，接口失败没有企业级错误反馈或重试入口。

## 4. 后端接口清单

下表路径均位于 `/api/v1`。除健康检查、注册、登录、刷新和忘记密码外，业务接口要求认证。

| 模块 | 接口 | 当前状态 |
| --- | --- | --- |
| 健康 | `GET /health` | 已实现 |
| 认证 | `POST /auth/register`、`POST /auth/login`、`POST /auth/refresh`、`GET /auth/me`、`POST /auth/change-password`、`POST /auth/forgot-password` | 基础流程已实现；忘记密码仅返回统一提示，无重置交付闭环 |
| 用户管理 | `GET /admin/users`、`PATCH /admin/users/{id}/role`、`PATCH /admin/users/{id}/disabled`、`POST /admin/users/{id}/reset-password`、`GET /admin/roles` | Admin 后端已实现；前端无页面 |
| 合同 | `POST/GET /contracts`、`GET/PATCH/DELETE /contracts/{id}`、`POST /contracts/{id}/favorite|archive|restore` | JSON 持久化；所有者隔离基本存在；前端只展示列表 |
| 合同版本 | `POST/GET /contracts/{id}/versions`、`POST /contracts/{id}/versions/compare` | 文本版本和风险映射已实现；不接真实文件上传，前端无入口 |
| 审查 | `POST/GET /reviews`、`GET /reviews/{id}`、`GET /reviews/{id}/download` | 同步主链路可用，历史按所有者隔离；响应未完全使用统一结构 |
| 分析历史 | `GET /analysis-history`、`GET /analysis-history/statistics`、`GET /analysis-history/{id}` | Admin/Legal 可读；Legal 是全局范围而非分配范围 |
| 阅读器 | `GET /reader/{review_id}/file`、`GET /reader/{review_id}/locations` | 文本定位可用；未按审查记录所有者授权，构成 P0 IDOR |
| 模型配置 | `GET /model-configs/providers|active|{id}`、`POST/GET/PATCH/DELETE /model-configs`、`POST /model-configs/{id}/active` | Admin-only；API Key 加密且仅脱敏返回；真实存储仍是 JSON |
| 模型验证 | `POST /llm/validate` | 已实现；受认证保护 |
| Prompt | `GET/POST /prompt-templates`、`GET/PATCH/DELETE /prompt-templates/{id}`、`POST /prompt-templates/{id}/default` | Legal/Admin 后端 CRUD 已实现；前端只读 |
| 工作流 | `POST/GET /workflows`、`GET /workflows/{id}`、`POST /workflows/{id}/actions` | 状态机与通知可用；资源绑定和分配授权不完整 |
| 通知 | `GET /notifications`、`POST /notifications/{id}/read`、`POST /notifications/read-all` | 用户隔离已实现；前端只有未读数 |
| 对话 | `POST/GET /chats`、`GET/DELETE /chats/{id}`、`POST /chats/{id}/messages` | 会话所有者隔离存在；创建时绑定 `review_id` 只校验存在性，不校验所有权 |
| Prompt/模型监控 | `GET /monitoring/status`、`GET /monitoring/metrics` | status 为 Admin；Prometheus 端点无应用鉴权，依赖部署边界 |

## 5. 数据库表、字段和关系

ORM 当前定义 12 张表。模型使用外键，但没有 ORM `relationship()`，实际业务服务也未全面使用这些表。

| 表 | 关键字段 | 关系与真实使用状态 |
| --- | --- | --- |
| `users` | id、email、full_name、password_hash、role、is_active、last_login_at、created_at、updated_at | 被合同、版本、审查、工作流、通知引用；当前用户服务仍用 `users.json` |
| `contracts` | id、title、category、status、creator_id、tags、favorite/archive/delete、current_version、expires_at、时间戳 | `creator_id -> users.id`；当前合同服务用 JSON |
| `contract_versions` | id、contract_id、version、file_name/path/type/size、text_content、created_by、file_hash、parent_version_id、version_type、时间戳 | 合同级联删除；自关联父版本；`(contract_id, version)` 唯一；当前版本服务嵌在合同 JSON 中 |
| `reviews` | id、contract_id、contract_version_id、creator_id、status、model、prompt_snapshot、duration、token、risk score/level、result、error、时间戳 | 指向合同、版本、用户；当前审查历史用 `history.json`，上传审查不建立这些外键 |
| `risk_findings` | id、contract_id、review_task_id、title、category、severity、score、source、confidence、原文/标准化文本、location、explanation、legal_basis、recommendation、revision、human-review、agent/rule/knowledge IDs、status、AI/人工意见、时间戳 | 指向合同和 reviews；统一风险模型存在但流水线不写表，亦无人工复核 API |
| `knowledge_documents` | id、title、source_type、jurisdiction、authority、version、生效/失效日期、status、article、content、URL、checksum、时间戳 | 无外键；当前知识服务读取目录内 JSON/Markdown，不读该表 |
| `model_configs` | id、name、provider、api_key_cipher、base_url、model_name、temperature、max_tokens、is_active、时间戳 | 当前模型配置服务用加密 JSON |
| `prompt_templates` | id、name、contract_type、stage、system_prompt、version、enabled/default、时间戳 | 当前 Prompt 服务用 JSON |
| `workflows` | id、contract_id、status、current_step、submitted_by、legal_reviewer_id、manager_reviewer_id、history、时间戳 | 外键可表达分配，但当前 JSON 服务未严格执行分配范围 |
| `notifications` | id、user_id、type、title、content、is_read、payload、时间戳 | 指向用户；当前通知用 JSON |
| `audit_logs` | id、actor_id、action、target、details、created_at | `actor_id` 未声明外键；审计服务可写 JSONL/数据库，覆盖面不完整 |
| `app_state` | key、value、updated_at | 通用状态表 |

### 5.1 迁移状态

- `20260710_0001`：调用 `Base.metadata.create_all()` 创建“当前全部模型”。
- `20260710_0002`：显式创建 `app_state`。
- `20260713_0003`：显式创建 `knowledge_documents` 和 `risk_findings`。
- `20260713_0004`：为 `contract_versions` 增加 `file_hash`、`parent_version_id`、`version_type`。
- 当前唯一 head：`20260713_0004`。

P0 风险：基线迁移导入当前 ORM 后再 `create_all()`，它会随代码模型漂移；在全新数据库上可能提前创建后续迁移负责的表/列，随后 `0002`—`0004` 重复创建。`alembic heads` 只能证明版本图单头，不能证明空库可升级。应把 `0001` 固化为当时的显式 DDL，并在临时 PostgreSQL 空库中加入 `upgrade head -> downgrade/upgrade` 测试。

## 6. 核心能力真实完成状态

| 能力 | 状态 | 说明 |
| --- | --- | --- |
| 登录 | 部分完成 | 登录、注册、刷新、改密、禁用用户可用；忘记密码无交付链路，refresh 无单令牌撤销 |
| RBAC | 部分完成 | 角色权限枚举清晰；资源级授权在阅读器、分析历史、对话绑定、工作流绑定/分配上不完整 |
| 合同中心 | 部分完成 | 后端 JSON CRUD/归档/恢复/版本存在；前端仅列表，审查上传未形成合同记录 |
| 合同版本 | 部分完成 | 哈希、父版本、类型、文本 diff 和风险映射存在；无文件级版本持久化 UI，历史审查未关联版本 |
| 审查 | 可演示 | 同步上传到多节点报告可运行；没有真实异步状态、幂等、取消、恢复和任务持久化 |
| 风险 | 模型完成、闭环未完成 | Schema/表/定位工具存在；未写入风险表，无接受/驳回/修改/解决 API 与 UI |
| 规则 | 部分完成 | 60 条确定性规则接入；全部标记 `contract_type=all`，数值条件未实现，无企业自定义 CRUD |
| 知识库 | 部分完成 | 结构化 Schema、测试数据、有效状态过滤、关键词检索存在；数据库/API/UI、向量适配和可靠来源治理未完成 |
| 报告 | 基本完成 | 5 种格式可生成和鉴权下载；只基于旧式报告字典，人工终稿与版本闭环未进入报告 |
| 人工复核 | 未完成 | 表字段存在，缺 Service/API/UI/审计闭环 |
| 审计 | 部分完成 | 登录和部分关键操作可记录；资源读取、管理员敏感访问和人工复核未形成完整覆盖矩阵 |

## 7. 后端已实现但前端未展示的功能

- 用户列表、角色调整、禁用/启用、管理员重置密码和角色权限清单。
- 合同详情、更新、收藏、归档、软删除、恢复。
- 合同版本新增、列表、文本差异、旧风险到新版本的整改映射。
- Prompt 模板新增、编辑、设默认和删除。
- 模型配置详情、编辑和删除。
- 通知列表、单条已读和全部已读。
- 工作流创建。
- 系统状态监控页面所需的后端数据。
- Markdown、Excel 等报告格式（当前 UI 主要按后端默认下载路径工作，缺格式选择）。

## 8. README 与代码一致性

### 一致部分

- Vue/FastAPI/LangGraph/规则引擎、60 条规则、模型密钥加密、结构化知识样例、5 种报告、20 份生成样本与 Gold 标签均有代码或数据支持。
- README 已主动声明风险持久化、Legal 分配、OCR 坐标和 Celery 编排尚未完成，这与源码一致。

### 不一致或容易误解部分

- README 的 PostgreSQL 架构描述容易让读者认为核心业务已使用数据库；实际主要是 JSON 文件存储。
- README 记录“55 tests passed”，当前源码静态计数和本地虚拟环境实测均为 58 个测试。
- README 的 83.65% 覆盖率是历史记录；本阶段没有重新执行 coverage，不能视为当前测量。
- README 记录前端构建通过，但本阶段指定 `pnpm run build` 被本机 pnpm 供应链策略在依赖检查阶段阻止；仓库中存在 2026-07-13 的历史 `dist`，不能替代本次构建。
- README 描述移除粒子效果，而仓库仍保留 `ParticleField.vue`，审查进行态也有局部粒子动画；全局 CSS 仍存在大量旧主题和背景素材规则。
- README 的“异步任务”表述应明确区分“Celery 基础设施存在”与“审查/导出任务仍为占位”。

## 9. 当前安全问题

### P0 / 高风险

1. **阅读器 IDOR**：`/reader/{review_id}/file` 和 locations 只检查通用合同读取权限，未检查审查记录 `owner_id` 或授权范围。已登录 Employee 猜到 ID 后可能读取他人合同 PDF。
2. **对话绑定越权**：创建会话绑定 `review_id` 时只校验记录存在，不校验所有者；随后会把报告内容作为 LLM 上下文。
3. **工作流资源注入**：创建工作流接受 `contract_id/review_id`，未校验资源存在性及调用者访问权；Legal 还可以处理所有流程而非分配给自己的流程。
4. **Alembic 空库升级不可复现风险**：动态基线迁移可能让全新生产环境初始化失败。

### P1 / 中风险

- Legal 的分析历史列表、统计和详情是全局数据，没有“分配给我/授权部门”的资源范围。
- access/refresh token 均存 `localStorage`；后端 CSP 还允许内联 style，主应用中间件的 CSP 对 script/style 都包含 `'unsafe-inline'`。
- refresh token 没有 jti 持久化、轮换复用检测或单令牌撤销；改密依靠 token version 使全部旧 token 失效。
- 登录限流是单进程内存计数，横向扩容或重启后失效，也没有账号维度组合限流。
- 公开注册只要求 8 位密码；生产环境强密码只约束 bootstrap 管理员，未统一应用于用户注册/改密。
- 管理员重置密码接口把临时密码返回响应；应限制展示、强制首次改密并避免代理/审计记录响应体。
- `/monitoring/metrics` 无应用鉴权；虽然当前标签没有合同全文或用户标识，仍需由网络层限制。
- `/docs` 和 `/openapi.json` 在 Nginx 中始终代理，缺少生产开关。

## 10. 文件上传与下载风险

已实现：扩展名白名单、最大 50 MB、MIME、魔数、随机存储名、文件名元数据分离、DOCX ZIP 条目数/解压总量/压缩比/路径穿越校验、Pillow verify、鉴权下载和 Nginx `nosniff`。

仍需处理：

- `application/octet-stream` 接受范围较宽，应结合真实魔数和格式解析结果收紧。
- PDF 只校验大小和 `%PDF`，缺少页数、对象数、解压流、递归对象和解析 CPU/超时限制。
- 图片未显式设置像素总量/解压炸弹策略；应捕获 Pillow decompression bomb 告警并限制宽高。
- LibreOffice 转换用户文档时缺少进程级沙箱/资源配额。
- 解析、OCR、Agent 或报告失败后，已保存上传文件不一定清理；成功文件也没有保留期限和归档策略。
- 未做恶意软件扫描或隔离区设计。
- OCR 结果没有置信度、页码/段落/坐标完整链路，扫描件低质量时无法可靠要求人工确认。
- XLSX 报告写入用户文本前应防范以 `= + - @` 开头的公式注入。

## 11. 密钥和日志风险

- `.env` 被 `.gitignore` 和 `.dockerignore` 排除，本阶段未读取；当前 Git 未跟踪 `.env`。
- 模型 API Key 使用 Fernet 认证加密并只返回脱敏值，这是当前较成熟的安全实现。
- 非生产环境允许用 JWT secret 派生模型加密密钥，降低密钥隔离；生产环境已强制独立主密钥。
- `/reviews` 保留可通过请求头传入临时 LLM Key 的兼容路径，必须确保反向代理、APM 和访问日志不记录该头；更建议移除此生产能力。
- 审计服务会写登录邮箱、IP、目标和 details 到 JSONL/数据库，尚无脱敏字段白名单、保留期限、访问 API 和完整性保护。
- 普通日志禁止合同全文/Prompt 的目标尚未形成自动测试；异常链也应加入 secret redaction。
- Git 历史敏感信息扫描不是本阶段目标；CI 已配置 gitleaks，但不能据此证明历史绝无密钥。

## 12. 规则、知识库与 Agent 审计

### 规则引擎

- 默认注册表有 60 条规则；规则结果可包含原文和偏移，执行异常不会中断整份合同。
- 条件实现支持 regex、keyword、missing、all、any；Schema 中声明的 numeric 目前没有对应 evaluator。
- 所有规则的合同类型均为 `all`，没有体现软件开发/技术服务的专属加载策略。
- 规则只由代码硬编码，数据库没有规则表，无法企业自定义、启停、版本回滚和审计。
- 去重主要按 `rule_id`，同类风险跨规则/Agent 的语义合并仍有限。
- 缺失型规则可能对短文本产生大量命中；总分按累计权重很快饱和 100，需要基准集校准但不得用随机分数。

### 知识库

- 结构化 JSON 检索能过滤 expired/repealed，并保留 document ID、article 和状态；只有关键词检索，没有向量适配器。
- 目录内 Markdown 走另一条非结构化路径，缺少状态、版本、authority、URL 等字段，可能绕过结构化治理。
- 示例数据明确标注测试用途，这是正确做法；目前不能宣传为完整或权威法律数据库。
- 无知识 CRUD/API/UI，无更新、修订、校验和人工发布流程。

### Multi-Agent / LangGraph

- 图节点职责为 coordinator → classifier → extractor → rule checker → knowledge retriever → compliance checker → validator → refiner → coordinator。
- classifier、rule、knowledge、validator 有 Pydantic 结构，但 extractor/compliance/refiner/coordinator 的节点契约仍混用自由字典。
- 仅部分节点写 `NodeTelemetry`；缺少统一 token、成本、模型、重试次数和开始/结束时间。
- LLM JSON 客户端失败时返回 `None`，可安全降级到规则结果，但没有有限重试、指数退避和结构化修复流程。
- 知识检索在合规分析前执行，但 `knowledge_hits` 没有注入 Compliance Analyst Prompt；因此当前 RAG 主要进入报告展示，没有真正约束 LLM 结论。
- LLM 风险依据可退化成泛化的“常见企业内控要求”，Validator 未验证 document ID 是否真实存在；必须禁止把该文本当成法律依据。

## 13. 测试薄弱区域

当前 58 个后端测试覆盖认证、合同所有者隔离、规则、知识状态、模型密钥、文件魔数/DOCX ZIP、报告格式、工作流、通知和基础 Agent Schema。明显缺口：

- 阅读器文件/定位的跨用户 IDOR 负向测试。
- 对话绑定他人 `review_id`、工作流绑定他人合同、Legal 分配范围测试。
- refresh token 轮换/撤销/复用、并发刷新、分布式限流测试。
- 空 PostgreSQL 从 base 执行 `alembic upgrade head` 的真实集成测试。
- 风险表持久化、人工接受/驳回/修改、审计记录和历史不覆盖测试。
- Celery 分阶段状态、幂等、重试、取消、worker 重启和 Redis 故障测试。
- PDF/图片压缩炸弹、解析超时、残留文件清理、恶意公式导出测试。
- LangGraph 非法 JSON 修复、超时重试、RAG 依据真实性和 Prompt 注入隔离测试。
- 前端没有单元、组件、权限路由、失败态或 E2E 测试脚本。
- 当前测试广泛使用临时 JSON 和 Mock，不能等同 PostgreSQL、Redis、Celery、OCR 或真实模型集成验证。

## 14. 前端大 chunk 的主要来源

仓库现有历史 `dist`（不是本阶段新构建）最大资产：

- `index-D7SFHbLG.js`：1,071,334 bytes，主要来自全量 `ElementPlus` 注册和完整 CSS/公共依赖。
- `DashboardView-DwgtCizB.js`：1,037,889 bytes，主要来自 `import * as echarts from 'echarts'`。
- `index-D4_OOqsz.css`：410,594 bytes，包含 Element Plus 全量样式和 54 KB、多个世代叠加的项目全局 CSS。

优化应采用 ECharts 按需模块、Element Plus 自动按需导入或明确组件注册、路由级拆包和 CSS 清理；先建立 bundle budget，再逐项调整，避免一次性重写。

## 15. 页面视觉问题

- `styles.css` 约 54 KB/99 行，实际是高度压缩的多套主题叠加，包含绿色/粉色/深色、切角、粒子、背景图和蓝色企业覆盖，存在 17 处 `!important`；维护和回归风险高。
- `ParticleField.vue` 是随机 canvas 点云组件，目前未见页面导入，属于遗留代码；审查加载态另有局部粒子动画，视觉规范不统一。
- 多个页面把模板、脚本和样式压成极少行，难以审查、复用和无障碍维护。
- Dashboard、Contracts、Reader 等页面吞掉接口错误，缺空状态/失败状态/重试；企业体验不完整。
- Login 源码预填默认管理员邮箱和密码，不适合生产展示。
- 导航可见性与后端权限不一致；Employee 可进入 Dashboard 后收到 403 或空白。
- Reader 双栏能力有限，没有稳定条款高亮、风险筛选、人工意见区和版本对比。

## 16. 产品业务闭环问题

当前流程实际是“上传临时文件 → 同步生成报告 → 本地历史查看”，尚未形成企业合同生命周期闭环：

- 上传审查不创建合同和不可变版本，合同中心与审查工作台是两套数据。
- 风险没有持久化和人工状态，无法统计 AI 建议接受率、驳回率或整改结果。
- 版本对比只在独立服务中存在，没有把旧风险映射到新审查并保留人工结论。
- 工作流状态动作没有触发真实审查，Legal 也没有明确指派队列。
- 报告只消费 AI/规则结果，不能区分 AI 原始建议和人工最终意见。
- 知识和规则没有管理员维护、审批、版本发布与审计闭环。
- 监控缺任务阶段、OCR/LLM 失败、成本、积压、人工复核等业务指标的真实数据源。

## 17. P0、P1、P2 优化计划

### P0：先保证授权、迁移和真实数据闭环

1. 建立统一 `ResourceScopeService`，修复 Reader、Chat review binding、Workflow binding、Legal history/assignment 的 IDOR。
2. 固化 Alembic 基线，增加临时 PostgreSQL 空库升级测试。
3. 让上传首先创建/选择 Contract 和 ContractVersion；Review/Risk/Report 以数据库记录和外键为主。
4. 新增风险持久化、人工复核状态 API、操作审计和历史不可覆盖约束。
5. 建立真实异步 ReviewTask 阶段状态、幂等键、重试/取消和前端恢复。
6. 补齐上述安全与端到端测试，再开放企业部署。

### P1：完善规则、知识、版本和企业页面

1. 三栏审查工作区：原文、风险、依据/人工意见，支持页段定位。
2. 合同详情、版本上传、对比、整改映射和历史审查 UI。
3. 规则表、规则版本、企业自定义启停和命中审计。
4. 知识条目 CRUD、有效性状态、来源校验、混合检索适配器；将命中片段真正注入分析节点。
5. 用户管理、通知中心、模型/Prompt 完整管理和监控页面。
6. 完整的错误、空、加载、权限和键盘可访问状态。

### P2：性能、治理和体验优化

1. ECharts/Element Plus 按需导入、CSS 分层、bundle budget 和前端缓存策略。
2. OCR 坐标/置信度、表格恢复质量、文件隔离/杀毒/保留期限。
3. Token/成本遥测、模型路由基准、缓存与分段摘要，禁止虚假性能指标。
4. refresh token 轮换、Redis 分布式限流、安全头和 API 文档开关。
5. 前端单元/组件/E2E、真实 PostgreSQL/Redis/Celery 集成测试和可重复 benchmark。

## 18. 可能需要新增的数据表和字段

以下是计划建议，不代表已实现；所有变更必须使用 Alembic：

| 建议对象 | 目的 |
| --- | --- |
| `review_tasks` | task_id、contract/version、idempotency_key、阶段状态、进度来源、重试、错误码、取消、阶段时间、worker/celery ID |
| `review_stage_runs` | 节点级开始/结束、模型、tokens、成本、重试、状态；不保存完整 Prompt/合同 |
| `contract_assignments` | 合同到 Legal/部门/用户的明确授权范围和有效期 |
| `contract_access_grants` | 临时/只读/编辑授权，支持资源范围校验 |
| `rules`、`rule_versions` | 自定义规则、发布版本、启停、条件、建议、依据、创建者和审计 |
| `knowledge_document_versions` | 知识版本正文、校验和、效力状态、发布者，避免覆盖历史 |
| `risk_review_events` | 风险接受/驳回/修改/解决的事件流，保留 AI 原值和人工终值 |
| `refresh_tokens` | jti 哈希、用户、设备、到期、撤销、轮换链和复用检测 |
| `report_artifacts` | 报告格式、文件哈希、生成者、源 review、人工终稿版本、状态 |

现有表建议补字段：`users.must_change_password`；`reviews.task_id/started_at/completed_at/cost`；`contract_versions.parse_status/parse_confidence/ocr_confidence/storage_key`；`knowledge_documents.published_by/published_at/is_test_data`；`workflows` 增加明确 assignment/version/review 外键一致性约束。

## 19. 可能需要新增的接口

- `/contracts/{id}/uploads` 或版本文件上传，统一建立不可变版本。
- `/review-tasks` 创建、查询、取消、重试和阶段日志；用幂等键防重复。
- `/reviews/{id}/risks` 列表及 `/risks/{id}/review` 人工接受、驳回、修改、解决。
- `/contracts/{id}/assignments` 授权与指派管理。
- `/rules`、`/rules/{id}/versions`、启停、发布和试运行。
- `/knowledge-documents` CRUD、版本、生效/失效、检索预览和来源校验。
- `/contracts/{id}/versions/{id}/compare` 与整改映射确认。
- `/reports` 生成任务、格式选择、状态和受权下载。
- `/notifications` 前端完整消费接口已经足够，可补分页游标/删除策略。
- `/auth/logout`、refresh token 撤销和会话列表。

## 20. 可能需要新增或完善的页面

- 用户与角色管理、合同详情、合同版本、版本对比。
- 三栏审查工作区、人工复核队列、风险详情/事件历史。
- 规则中心、知识库管理、通知中心、系统监控。
- 设置页完善模型编辑/删除、Prompt CRUD；不是创建重复页面，而是复用现有设置框架。

## 21. 各阶段兼容与回滚风险

| 阶段 | 主要兼容风险 | 回滚原则 |
| --- | --- | --- |
| 企业框架 | 路由/菜单权限改变导致旧深链失效 | 保留旧路由重定向，UI 变更独立回滚 |
| 工作台 | 统计口径从 JSON 切数据库后数值变化 | 记录口径版本，保留只读旧统计适配器 |
| 合同中心 | JSON 到 DB 迁移可能丢 ID/版本关系 | 先只读导入、校验哈希/数量，再切主存储；保留导入批次回滚 |
| 三栏审查 | 旧报告缺统一风险/定位字段 | 提供旧报告兼容转换器，不覆盖历史文件 |
| 风险复核 | 状态机和人工意见不可逆覆盖 | 使用事件表追加，不原地覆盖 AI 原值 |
| 异步任务 | 同步 API 调用方和前端超时逻辑受影响 | 保留受控同步开发模式，生产只走持久化任务；提供 feature flag |
| 规则/知识 | 新规则导致风险数量和评分改变 | 规则/知识版本固定到 review，支持回滚到已发布版本 |
| 版本对比 | 文本归一化变化导致 diff 映射漂移 | 保存算法版本和原始文本，允许人工修正映射 |
| 性能安全 | token 存储和 CSP 改造可能影响登录/组件 | 分阶段双栈迁移，安全头先 report-only 验证 |
| 最终验收 | 环境依赖、OCR、模型造成非确定失败 | 将确定性、Mock、真实模型结果分开验收，保留安全降级 |

## 22. 本阶段验证结果

| 检查 | 指定命令结果 | 补充诊断 |
| --- | --- | --- |
| 后端 | `python -m pytest -q` 失败：系统 Python 3.12 未安装 `pytest` | `.venv\Scripts\python.exe -m pytest -q`：**58 passed，1 warning，17.90s**；warning 为 Starlette TestClient/httpx 弃用提示 |
| 前端 | `pnpm run build` 失败，未进入 Vite：本机 pnpm 供应链策略报 `ERR_PNPM_IGNORED_BUILDS`，阻止 `esbuild@0.28.1` 安装脚本 | 未执行 `pnpm approve-builds`，因为本阶段不修改依赖策略。现有 dist 仅作为历史产物，不记为本次通过 |
| 数据库 | `python -m alembic heads` 失败：系统 Python 未安装 `alembic` | `.venv\Scripts\python.exe -m alembic heads`：`20260713_0004 (head)`；本阶段未执行空库 upgrade |
| Docker | `docker compose config --quiet`：**通过，退出码 0** | 未构建镜像、未启动服务 |

本阶段未调用真实 LLM、OCR benchmark 或付费服务，没有测量模型准确率、Token、成本、前端性能和真实 PostgreSQL 迁移成功率。
