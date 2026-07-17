# ENTERPRISE UPGRADE REPORT

生成日期：2026-07-13。分支：`feature/enterprise-contract-review-v2`。未执行 `git push`。

> AI辅助合同风险审查，不构成正式法律意见，重要合同应由专业法务或律师结合交易背景进行人工复核。

## 1. 原项目问题

- 生产环境缺少集中式强配置校验，模型凭据加密与 JWT 使用同一密钥且采用自制 XOR 算法。
- 合同接口只有接口级 RBAC，没有逐资源所有权校验，存在直接对象引用越权风险。
- 规则检查散落在 Agent 内，规则定义、版本、稳定评分和命中原文缺乏统一契约。
- 风险和知识依据缺少可持久化、可版本化的统一数据库模型。
- 现有样本不足以支持用户要求的 Gold Standard、消融实验和真实模型基准。

## 2. 已完成修改

- 新增生产环境必填项、弱密钥、弱密码、Debug 和默认数据库口令校验。
- 使用 Fernet 认证加密保存模型 API Key；接口只返回脱敏值；旧 XOR 密文在读取时原地安全迁移。
- 对畸形 JWT 编码和载荷统一转为受控认证错误。
- 为合同列表、详情、修改、收藏、归档、删除、恢复和版本增加所有者校验；管理员保留全局权限。
- 新增独立确定性规则引擎、60 条重点规则、稳定评分公式、命中偏移、去重和单规则错误隔离，并接入现有 Compliance Checker。
- 新增统一可解释风险 Schema、结构化知识文档 Schema、数据库模型和 Alembic 迁移。
- 新增生产配置、密钥密文、规则确定性、评分、错误隔离和 IDOR 测试。

## 3. 未完成修改

以下项目仍未实现，不应视为已交付：登录分布式限流；Legal 分配范围模型；全部非合同资源 IDOR 审计；知识库向量检索；完整七节点 Multi-Agent 结构化重构；真实 Celery 阶段恢复和幂等；合同文本 diff 和风险映射；全部前端管理页与 E2E；真实模型消融；完整供应链扫描扩充。

## 4. 阶段 Commit SHA

- `e089e10` — `chore: create enterprise upgrade safety baseline`
- `ce55f9f` — `fix: enforce production security and encrypt model credentials`
- `1064017` — `feat: add deterministic explainable contract rule engine`
- `d34a225` — `fix: prevent contract resource idor`
- `867c0ef` — `fix: revoke tokens after security-sensitive account changes`
- `f75a6da` — `fix: harden document upload and review downloads`
- `cdbac5a` — `test: add fictional contract fixtures and gold labels`
- `55e1006` — `test: add multi-agent benchmark framework`
- `bd7b945` — `feat: add legal knowledge version tracking`
- `9a78a48` — `fix: remove decorative particles and simulated review progress`
- `41bbfc9` — `test: enforce verified authorization and coverage baseline`
- `862fddd` — `docs: publish verified architecture and metrics`
- `31268ef` — `ci: add reproducible security and quality checks`
- `6057b75` — `feat: add contract version remediation workflow`
- `37e207f` — `refactor: clarify multi-agent responsibilities`

## 5. 新增和修改文件

新增：`docs/PROJECT_BASELINE_REPORT.md`、`src/contract_review/rules/*`、`src/contract_review/schemas/risk.py`、`src/contract_review/schemas/knowledge.py`、`tests/test_production_config_security.py`、`tests/test_rule_engine.py`、迁移 `20260713_0003`。

修改：配置、安全、数据库模型、模型配置服务、LLM/Review 调用、Compliance Checker、合同服务和路由、相关测试、`.env.example` 与 `requirements.txt`。

## 6. 数据库迁移

- `20260710_0001`：原企业 Schema。
- `20260710_0002`：原应用状态。
- `20260713_0003`：可解释风险与版本化知识文档，当前唯一 head。
- `20260713_0004`：合同版本文件哈希、父版本关系和版本类型。
- `20260713_0005`：合同商业字段。
- `20260713_0006`：风险人工复核状态与审计字段。
- `20260713_0007`：异步审查任务，当前唯一 head。

## 7-12. 验证结果（2026-07-17 发布候选复核）

- 当前测试总数：100。
- 通过：100。
- 失败：0。
- 真实覆盖率：83.81%，发布门槛为 80%。
- Ruff 通过；Mypy 严格检查 124 个源文件通过；Python 与 Node 依赖审计未发现已知漏洞。
- 前端构建：成功，2408 modules；组件按需加载后最大图表 chunk 为 554.08 kB（gzip 189.47 kB）。
- Alembic 单一 head；全新库升级/回退/再升级与带既有数据的往返均通过。
- Docker：`docker compose config --quiet` 通过；后端镜像构建因本机 Docker Desktop daemon 未运行而未完成，错误为无法连接 `dockerDesktopLinuxEngine`。

## 13-16. 安全、规则和样本

- Token family 单次轮换/重放撤销、密码变更会话失效、跨实例登录限流、跨资源 IDOR 回归、上传结构限制和异步幂等均已实现并有自动测试；真实多实例故障注入仍需预发布环境验证。
- Git 历史高置信模式检查发现一个锁文件完整性哈希中的 AWS 形状误报；当前树无高置信命中。专用 Gitleaks 由 GitHub Actions 执行，不能把模式扫描描述为零风险证明。
- 当前规则数量：60，全部为确定性触发指标，不是绝对法律结论。
- 测试合同数量：20 类完全虚构样本，配套 20 份 Gold 标签。

## 17-22. 评测与消融

- 真实评测结果：确定性部分标注基准，11 个文本样本；TP 26、FP 132、FN 0、Precision 0.1646、Recall 1.0000、F1 0.2826。该结果不是法律审查准确率。
- Mock 评测结果：仅验证 A/C/D 消融结构，所有模型指标均写为“未进行真实测量”。
- 平均审查耗时：确定性规则本地单次测量 0.530 ms；完整审查未进行真实测量。
- 平均 Token：未进行真实测量。
- 单份合同成本：未进行真实测量。
- Multi-Agent 对比：框架可运行；A/C/D 真实模型指标未进行真实测量，B 仅有确定性规则指标。

## 23. 已知限制

规则中的“缺失条款”会将未出现指标的合同标为待人工复核，适合作为召回优先的初筛，尚未用完整 Gold Standard 校准误报。风险结果、人工复核状态和审计已持久化，但部分聚合服务仍使用 JSON 兼容存储。现有知识 Markdown 不能代表完整、权威或持续更新的法律数据库。浏览器仍把令牌保存在 `localStorage`，在迁移至 HttpOnly/SameSite Cookie 前必须把 XSS 防护作为生产硬门禁。

## 24. 用户必须手动完成

1. 在生产 `.env` 设置独立高强度 `JWT_SECRET_KEY`、`BOOTSTRAP_ADMIN_PASSWORD`、`DATABASE_URL`、`POSTGRES_PASSWORD`、`MODEL_CREDENTIAL_ENCRYPTION_KEY`。
2. 撤销任何曾公开或误提交的真实密钥（本次扫描未发现高置信命中，但不能替代组织级凭据审计）。
3. 提供合法、授权的法规/制度数据源，并由法务确认版本和效力。
4. 在隔离环境运行真实模型评测；不得把 Mock 指标作为模型准确率。

## 25. 启动命令

```powershell
Set-Location D:\CodexProjects\contract-review-system
Copy-Item .env.example .env  # 仅在没有现有 .env 时执行；当前已有 .env，不要覆盖
docker compose up -d --build
```

本地测试：

```powershell
$env:PYTHONPATH="src"
python -m alembic upgrade head
python -m pytest -q
Set-Location frontend
pnpm run build
```

## 26. 回滚方法

不要使用破坏性 reset。应用代码以发布候选提交为单位执行 `git revert`；数据库默认采用向前修复。任何 downgrade 前必须先备份、在生产副本演练并确认不会丢失数据，具体步骤见 `docs/BACKUP_RESTORE_ROLLBACK.md`。

## 27. 下一阶段建议

优先级顺序：预发布多实例故障注入 → HttpOnly/SameSite Cookie 与 CSRF 设计 → 合法法规数据源 → 完整 Gold 数据与法务校准 → 恶意文档沙箱/CDR → 生产容量与恢复演练。

## 28. 适合写入简历的项目描述

在 FastAPI + Vue 3 合同审查平台中落地企业级安全加固与可解释规则审查：引入 Fernet 凭据认证加密、生产配置门禁、资源级授权和 60 条确定性合同风险规则；建立可追溯风险/法规版本数据模型与 Alembic 迁移，并以自动化测试验证规则确定性、密钥不落明文和跨用户 IDOR 防护。

## 29-30. 面试官可能追问的 20 个问题与参考回答

1. **为什么规则优先于 LLM？** 规则可重复、可测试、成本低，适合明确红线；LLM只补语义判断。
2. **如何保证同输入同结果？** 固定规则版本、正则与公开评分公式，不引入随机数。
3. **为什么选择 Fernet？** 它提供成熟的认证加密，能同时发现密文篡改，避免自创算法。
4. **API Key 为什么不能读取？** 管理员只需覆盖和验证，读取原文会扩大泄露面。
5. **旧密文如何迁移？** 识别无 `fernet:` 前缀的旧格式，在内存解密后立即重新加密写回，不记录明文。
6. **如何防 IDOR？** 权限检查必须同时包含资源 ID、当前用户、角色和授权关系；本轮合同使用所有者或管理员规则。
7. **为什么越权返回 404？** 避免通过 403 区分资源存在性，减少枚举信息。
8. **风险分数如何解释？** 严重程度映射固定基础分，再乘以受限范围的证据可靠性权重。
9. **没有法律依据怎么办？** 依据留空并强制人工复核，禁止模型补造法条。
10. **规则误报如何处理？** Gold Standard 校准、按合同类型启停、人工驳回反馈和版本化规则。
11. **高风险为何默认人工复核？** 高影响结论需要结合交易背景，AI不能替代专业判断。
12. **怎样定位原文？** 保存命中文本、字符偏移和段落索引；PDF/OCR后续补页码与坐标。
13. **如何防日志泄密？** SecretStr、脱敏输出、禁止完整 Prompt/合同和 Key 进入日志与审计详情。
14. **Token 还缺什么？** 已有持久 token version、refresh family 单次轮换和重放撤销；仍需把浏览器 refresh token 迁移到 HttpOnly/SameSite Cookie，并完成 CSRF 设计。
15. **并发任务如何防重复扣费？** 幂等键、阶段事务、结果唯一约束和调用前后可恢复状态。
16. **知识库如何处理失效法规？** 状态与有效期过滤，默认只检索 effective，结果携带 document_id 和条号。
17. **为什么没有声称 70% 覆盖率？** 没有实际运行 coverage 就不能填写推测数字。
18. **前端当前风险是什么？** 图表 chunk 仍偏大，令牌仍在 `localStorage`；人工复核与版本闭环页面已经连接后端，但仍需预发布人工流程验证。
19. **Docker 验证到什么程度？** Compose 语法通过，镜像构建和完整服务启动未真实测量。
20. **下一步最重要是什么？** 在预发布环境完成多实例故障、备份恢复、恶意文档与权限矩阵演练，再由法务校准规则和知识来源。
