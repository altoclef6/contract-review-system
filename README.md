# 企业内部 AI 合同审查与合规管理平台

面向企业内部法务和业务团队的合同风险初筛平台，当前重点支持软件开发合同、技术服务合同、信息系统建设合同和软件外包合同。系统组合确定性规则、结构化知识检索和可选 Multi-Agent 分析，并保留风险原文、字符位置、规则来源和人工复核标记。

> AI辅助合同风险审查，不构成正式法律意见，重要合同应由专业法务或律师结合交易背景进行人工复核。

## 当前真实能力

- JWT 登录、刷新、RBAC、密码修改和 Token 版本失效。
- 合同创建、列表、版本、归档、删除和恢复；非管理员按所有者隔离。
- PDF、DOC、DOCX 和图片解析；DOCX 进行 ZIP 结构和压缩炸弹检查。
- 60 条确定性软件/技术合同规则，固定评分公式、错误隔离和原文偏移定位。
- 可选 LLM 补充分析；不可用时保留确定性规则结果，不虚构模型结论。
- 模型 API Key 使用 Fernet 认证加密，接口仅返回脱敏值。
- 结构化知识条目支持版本、效力状态、来源类型、条号和 `document_id`。
- JSON、DOCX、PDF、Markdown 和 XLSX 报告导出。
- 20 类完全虚构测试样本、20 份 Gold 标签和可执行评测/消融框架。

## 架构

```mermaid
flowchart LR
    U["企业用户"] --> V["Vue 3 前端"]
    V --> API["FastAPI API"]
    API --> A["JWT / RBAC / 资源授权"]
    API --> P["安全文档解析"]
    P --> R["确定性规则引擎"]
    R --> K["结构化知识检索"]
    K --> G["LangGraph 审查流程"]
    G --> O["可解释风险与报告"]
    API --> DB["PostgreSQL / Alembic"]
    API --> C["Redis / Celery 扩展"]
```

## 审查流程

```mermaid
flowchart TD
    L["登录"] --> U["上传合同"]
    U --> S["扩展名、MIME、魔数、Office ZIP 安全检查"]
    S --> E["文本/OCR 提取"]
    E --> D["60 条确定性规则"]
    D --> K["有效知识条目检索"]
    K --> M["可选 LLM 语义补充"]
    M --> V["去重、校验、原文定位"]
    V --> H["人工复核与报告"]
```

## 目录

```text
frontend/                  Vue 3 企业前端
migrations/                Alembic 迁移
samples/generated/         20 类完全虚构测试样本
samples/expected_results/  Gold 标签
scripts/                   数据生成、评测、消融脚本
src/contract_review/
  agents/                  现有 Agent 节点
  api/                     FastAPI 路由与鉴权
  database/                SQLAlchemy 模型
  rules/                   确定性规则引擎
  schemas/                 Pydantic API/领域契约
  services/                业务服务
tests/                     后端自动化测试
```

## 安全设计

- 生产环境强制配置 JWT、管理员密码、数据库、PostgreSQL 密码和模型凭据主密钥。
- 模型密钥只允许覆盖，数据库/JSON 存储中不保存明文。
- 修改密码、管理员重置、禁用账号和角色变化都会使旧 Token 失效。
- 合同和审查报告同时校验接口权限与资源所有权；越权统一返回不可枚举响应。
- 上传文件使用随机服务端文件名，并验证扩展名、MIME、文件魔数和 DOCX 内部结构。
- `.env`、上传文件、报告、日志、本地数据库和 coverage 产物不会进入 Git。

## 数据处理

原始文件保存在不可直接由 Nginx 执行的上传目录。审查风险尽量保存命中文本、字符偏移和段落索引；PDF 阅读器支持页码位置。当前 OCR 坐标、合同版本风险迁移和完整数据库风险持久化仍在 Roadmap。

## 快速启动

要求 Python 3.10+、Node.js 22+、pnpm。不要覆盖已有 `.env`。

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
$env:PYTHONPATH="src"
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m uvicorn contract_review.main:app --reload
```

前端：

```powershell
Set-Location frontend
pnpm install
pnpm run dev
```

## Docker 启动

在 `.env` 中替换全部占位值后执行：

```powershell
docker compose config --quiet
docker compose up -d --build
docker compose ps
```

生产环境不得启用 Debug，不得使用示例密码或共享 JWT/模型加密密钥。

## OCR 与 DOC 依赖

- 图片和扫描 PDF：安装 Tesseract，并安装 `chi_sim` 与 `eng` 语言包；可配置 `TESSERACT_CMD` 和 `TESSDATA_DIR`。
- 旧 `.doc`：安装 LibreOffice，或设置 `LIBREOFFICE_CMD`。依赖缺失会返回清楚错误，不会伪造解析成功。

## 模型配置

系统可在没有模型 Key 时运行确定性规则。启用模型时，通过管理员模型配置页覆盖 Key，或在本地 `.env` 设置供应商配置。生产环境必须设置独立 `MODEL_CREDENTIAL_ENCRYPTION_KEY`。不要在请求日志、浏览器存储或提交记录中保存完整 Key。

## 测试与真实指标

```powershell
$env:PYTHONPATH="src"
python -m pytest -q --cov=contract_review --cov-report=term
python scripts/evaluate_review.py
python scripts/benchmark_ablation.py
Set-Location frontend
pnpm run build
```

2026-07-13 本地验证：

- 后端测试：50 项，50 通过，0 失败。
- 后端整体覆盖率：83%。
- 前端 typecheck/build：通过；仍有大 chunk 警告。
- Alembic：单一 head `20260713_0003`。
- Docker Compose 语法：通过；完整镜像构建未进行真实测量。

## 评测结果

当前 Gold 为早期部分标注，结果只能作为规则回归基线，不能视为法律审查准确率：

- benchmark：deterministic benchmark
- 文本样本：11
- TP / FP / FN：26 / 132 / 0
- Precision / Recall / F1：0.1646 / 1.0000 / 0.2826
- 平均耗时：0.530 ms；P50：0.189 ms；P95：3.876 ms（单次本地测量）
- Token、模型成本、法律依据可追溯率：未进行真实测量

误报偏高主要来自召回优先的“缺失条款”规则和不完整 Gold 标注，需要法务校准。

## Multi-Agent 对比

`scripts/benchmark_ablation.py` 提供 A 单 Prompt、B 规则+单 Prompt、C Multi-Agent、D Multi-Agent+RAG+规则结构。当前仅 B 运行确定性基准；A/C/D 没有真实模型数据，指标均明确为“未进行真实测量”。

## 已知限制

- Agent 仍是现有四节点流程，尚未完成七职责的全面结构化重构。
- Celery 任务仍是扩展入口，尚未提供完整阶段状态、取消、恢复和幂等 API。
- 风险数据库模型已存在，但现有同步审查结果尚未全部写入风险表。
- Legal 的“分配给我”授权关系尚未形成独立数据库模型。
- 完整法规库需要组织提供合法、可靠、持续维护的数据源。
- 前端已经移除粒子和伪进度，但真实异步阶段轮询仍在 Roadmap。

## Roadmap

1. 七节点结构化 LangGraph、重试遥测和 JSON 修复。
2. Celery/Redis 幂等任务状态、取消与恢复。
3. 合同版本文本 diff、风险映射和整改闭环。
4. 风险人工确认/驳回/修改 API 与前端页面。
5. 合法法规数据导入、混合检索和更新审计。
6. 扩充法务 Gold 标注并运行真实模型消融。

## 截图与演示视频

仓库不提交虚构产品截图。录制演示前使用测试账号和 `samples/generated/`：登录 → 上传虚构合同 → 查看风险与原文 → 导出报告。录制画面不得出现 `.env`、真实 Key、邮箱、真实合同或日志。

## 面试重点

- 为什么确定性规则优先，以及如何稳定评分和定位原文。
- Fernet 认证加密、旧密文迁移和 Token 版本撤销。
- 如何用 RBAC + 所有权防止 IDOR。
- 为什么不虚构覆盖率、法规和模型指标。
- 如何从同步原型演进到可恢复、幂等的异步审查平台。
