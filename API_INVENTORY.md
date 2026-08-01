# API 清单

更新时间：2026-07-15

## 公共约定

- 基础前缀：`/api/v1`，来自 `Settings.api_v1_prefix`。
- 鉴权：除表中标为“否”的接口外，使用 `Authorization: Bearer <access_token>`。
- 常规响应：大部分新接口为 `ApiResponse<T>`；旧 `/reviews` 返回直接模型/对象，尚未统一。
- 校验错误：FastAPI 422；业务接口另有 400、401、404、409 等。
- 文件上传：`/reviews` 和合同版本上传使用 `multipart/form-data`。
- 接口文档：应用提供 `/docs` 自定义页面，OpenAPI 由 FastAPI 动态生成。

## 鸿蒙端核心接口

| 方法 | 路径 | 输入 | 返回 | 登录 | 当前判断 |
|---|---|---|---|---|---|
| POST | `/auth/login` | `LoginRequest` | `ApiResponse<TokenResponse>` | 否 | 可复用 |
| GET | `/auth/me` | 无 | `ApiResponse<UserPublic>` | 是 | 可复用 |
| POST | `/auth/refresh` | `RefreshTokenRequest` | `ApiResponse<TokenResponse>` | 否 | 可复用 |
| POST | `/contracts` | `ContractCreate` JSON | `ApiResponse<ContractRecord>` | 是 | 可复用 |
| POST | `/contracts/{id}/versions/upload` | multipart 文件 | `ApiResponse<ContractVersion>` | 是 | 可复用 |
| POST | `/contracts/{id}/versions/{version_id}/review` | 路径参数 | `ApiResponse<ReviewTaskRecord>` | 是 | 可复用，推荐主入口 |
| GET | `/review-tasks/{task_id}` | 路径参数 | `ApiResponse<ReviewTaskRecord>` | 是 | 可轮询进度 |
| GET | `/review-tasks/{task_id}/events` | 路径参数 | 任务事件列表 | 是 | 可展示阶段事件 |
| GET | `/reviews/{review_id}` | 路径参数 | 完整报告对象 | 是 | 可复用，返回未统一 |
| GET | `/risks?review_id=...` | 分页与筛选 | `ApiResponse<RiskListResponse>` | 是 | 可复用 |
| GET | `/risks/{risk_id}` | 路径参数 | `ApiResponse<RiskRecord>` | 是 | 含解释、建议与原文 |
| GET | `/analysis-history` | 分页与筛选 | `ApiResponse<AnalysisHistoryPage>` | 是 | 可复用 |
| GET | `/reviews/{review_id}/download?file_type=pdf` | 路径/查询 | 文件 | 是 | 可复用 |

## 全量操作索引

下表由 2026-07-15 当前 OpenAPI 生成结果核对。参数与完整字段应以对应 schema 和端点文件为准。

| 模块 | 操作 |
|---|---|
| 认证 | `POST /auth/register`、`POST /auth/login`、`POST /auth/refresh`、`GET /auth/me`、`POST /auth/change-password`、`POST /auth/forgot-password` |
| 管理 | `GET /admin/users`、`PATCH /admin/users/{user_id}/role`、`PATCH /admin/users/{user_id}/disabled`、`POST /admin/users/{user_id}/reset-password`、`GET /admin/roles` |
| 合同 | `POST/GET /contracts`、`GET/PATCH/DELETE /contracts/{contract_id}`、`POST /contracts/{contract_id}/favorite`、`archive`、`restore`、`POST/GET /contracts/{contract_id}/versions`、`GET /contracts/{contract_id}/overview` |
| 合同文件与审查 | `POST /contracts/{contract_id}/versions/upload`、`GET /contracts/{contract_id}/versions/{version_id}/download`、`POST /contracts/{contract_id}/versions/{version_id}/review`、`POST /contracts/{contract_id}/versions/compare` |
| 工作台 | `GET /dashboard/summary` |
| 模型配置 | `GET /model-configs/providers`、`GET/POST /model-configs`、`GET /model-configs/active`、`GET/PATCH/DELETE /model-configs/{config_id}`、`POST /model-configs/{config_id}/active` |
| Prompt | `GET/POST /prompt-templates`、`GET/PATCH/DELETE /prompt-templates/{template_id}`、`POST /prompt-templates/{template_id}/default` |
| 审批 | `GET/POST /workflows`、`GET /workflows/{workflow_id}`、`POST /workflows/{workflow_id}/actions` |
| 通知 | `GET /notifications`、`POST /notifications/{notification_id}/read`、`POST /notifications/read-all` |
| 阅读器 | `GET /reader/{review_id}/file`、`GET /reader/{review_id}/workspace`、`GET /reader/{review_id}/locations?text=...` |
| 异步任务 | `POST/GET /review-tasks`、`GET /review-tasks/{task_id}`、`POST /review-tasks/{task_id}/cancel`、`retry`、`GET /review-tasks/{task_id}/events` |
| 风险 | `GET /risks`、`GET /risks/{risk_id}`、`POST /risks/{risk_id}/confirm`、`reject`、`start-remediation`、`mark-remediated`、`close`、`assign`、`comments`、`PUT /risks/{risk_id}/revised-clause` |
| 规则 | `GET /rules`、`GET/PATCH /rules/{rule_id}` |
| 知识库 | `GET/POST /knowledge`、`GET/PATCH /knowledge/{entry_id}`、`GET /knowledge/{entry_id}/history` |
| 版本对比 | `POST /version-comparisons/{contract_id}` |
| 风险反馈 | `POST/GET /risk-feedback`、`GET /risk-feedback/statistics` |
| 监控 | `GET /monitoring/status`、`GET /monitoring/metrics` |
| AI 对话 | `GET/POST /chats`、`GET/DELETE /chats/{session_id}`、`POST /chats/{session_id}/messages` |
| 分析历史 | `GET /analysis-history`、`GET /analysis-history/statistics`、`GET /analysis-history/{review_id}` |
| 系统 | `GET /health`、`POST /llm/validate` |
| 同步审查/报告 | `POST/GET /reviews`、`GET /reviews/{review_id}`、`GET /reviews/{review_id}/download` |

## 关键 schema 摘要

- `TokenResponse`：access_token、refresh_token、expires_in、user。
- `ReviewTaskRecord`：task_id、status、current_stage、progress、review_id、result_summary、错误字段和时间戳。
- `RiskRecord`：风险等级、标题、命中原文、位置、解释、建议、法律依据、状态、修订条款。
- `ReviewResponse`：review_id、风险发现、报告路径和错误信息；由旧同步审查入口直接返回。
- 报告下载支持：json、docx、pdf、markdown、xlsx。

## 端点文件映射

- 认证/用户：`src/contract_review/api/v1/endpoints/auth.py`、`admin.py`
- 合同/上传：`contracts.py`，文件校验在 `utils/file_utils.py` 与 `services/document_loader.py`
- 同步审查：`reviews.py`、`services/review_service.py`
- 异步任务：`review_tasks.py`、`services/review_task_service.py`、`tasks/jobs.py`
- 风险：`risks.py`、`services/risk_service.py`
- 历史/报告：`analysis_history.py`、`services/history_service.py`、`services/report_service.py`

## 已确认缺口

1. `/review-tasks` 的 `ReviewTaskCreate` 使用服务端 `file_path`；它不是面向移动设备的直接上传接口。
2. `/reviews` 是可直接上传的同步接口，但不适合可靠展示细粒度异步进度。
3. `/reviews` 与多数新接口的响应包装不一致，鸿蒙网络层需要兼容或后端做最小统一。
4. OpenAPI 证明契约可生成，不等于每个接口已做运行态验证；阶段三需逐项补齐脱敏样例。
