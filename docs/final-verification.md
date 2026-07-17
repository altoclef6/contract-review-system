# 最终验收记录

最近复核日期：2026-07-17

> AI辅助合同风险审查，不构成正式法律意见，重要合同应由专业法务或律师结合交易背景进行人工复核。

## 已完成

- 企业级应用框架、工作台、合同中心、三栏审查阅读器和风险台账。
- 合同安全上传、版本历史、授权下载、归档、恢复和删除确认。
- 风险持久化、严格状态流转、人工复核、评论、分配和审计。
- 真实审查任务阶段、幂等键、取消、有限重试、过期识别和模型失败规则降级。
- 60 条确定性规则及安全配置中心；规则设置实际进入审查流程。
- 结构化知识库的来源类型、效力状态、历史版本和失效过滤。
- 中文合同段落级版本对比、风险相似匹配和 `uncertain_match` 安全降级。
- 报告下载、用户和权限管理页面均连接现有真实后端接口。
- 生产配置校验、非 root 后端镜像、Nginx 安全头和云部署指南。

## 验证结果

- 后端：`101 passed, 0 failed`；测试依赖改用 `httpx2` 后无弃用警告。
- 覆盖率：整体 `83.81%`，由全新隔离环境中的 `pytest-cov` 真实测量，门槛为 80%。
- Ruff 通过；Mypy 严格检查 124 个后端源文件通过；`pip check` 与 `pip-audit` 通过。
- 前端：`vue-tsc -b` 和 `vite build` 通过，2408 个模块完成转换；`pnpm audit` 未发现已知漏洞。
- 构建产物：Vue 核心 174.41 kB；主入口 232.87 kB；按需加载的图表 chunk 554.08 kB（gzip 189.47 kB）。Element Plus 已改为组件级自动导入。
- Alembic：单一 head `20260713_0007`；全新临时 SQLite 数据库完成全链升级、回退一版和再升级；带既有用户/合同数据的 `0006 → head → 0006` 往返保持数据。
- Docker Compose：使用非真实验证变量执行 `docker compose config --quiet` 通过。
- Docker 镜像：未进行真实测量。本机 Docker Desktop Linux daemon 未启动，连接命名管道失败。
- 本地运行服务：`/api/v1/health` 可访问；工作台、任务、风险、规则、知识、版本对比、反馈和报告下载路由均已出现在实时 OpenAPI。
- 密钥扫描：`.env` 未被 Git 跟踪；当前树高置信模式 0 命中；历史中的一个 AWS 形状命中已确认是 pnpm 锁文件完整性哈希误报。最终结论仍以 CI Gitleaks 为准。

## 部分完成或限制

- 完整法规数据库必须由部署组织提供合法、可靠并持续维护的数据源；当前测试数据不会被描述为正式法律数据库。
- 真实模型 Precision、Recall、Token 和成本未进行真实测量；Mock 结果不作为模型准确率。
- OCR 坐标取决于解析引擎。缺失坐标时界面只展示真实文本偏移，不伪造 PDF 坐标。
- 默认 Docker Compose 使用单个 `solo` worker，适合首次部署验证；扩大并发前需在预发布环境验证共享任务存储竞争、队列积压和取消时序。
- Legal 的部门/组织授权范围仍需结合实际组织结构建模；当前依照现有角色和资源所有权规则。
- ECharts 仍是最大单一图表依赖；已采用核心模块与所需图表类型导入，并只在仪表盘路由加载。

## 云端上线前人工检查

1. 按 [cloud-deployment.md](cloud-deployment.md) 配置 HTTPS、域名、备份和强密钥。
2. 在服务器执行 `docker compose config --quiet`、`docker compose build` 和 `docker compose up -d`。
3. 使用虚构合同完成登录、上传、任务阶段、风险复核、版本对比和报告下载闭环。
4. 验证普通用户无法枚举或下载其他用户合同、风险、任务和报告。
5. 检查日志不包含合同全文、密码、Token 或模型 Key。
6. 配置 PostgreSQL、命名卷和对象文件备份，并完成一次隔离恢复演练。

## 本地恢复方法

恢复前应先保存需要保留的本地工作；不要直接执行 `git reset --hard`、`git clean` 或强制 checkout。发布候选分支提交后应以 `git revert <commit>` 为回滚单位，并按备份恢复文档处理数据库与数据卷。

## 建议提交拆分（未执行）

1. `feat: add enterprise dashboard contract center and review workspace`
2. `feat: persist risk review workflow and audit trail`
3. `feat: add resilient asynchronous review tasks`
4. `feat: add rule knowledge version comparison and feedback centers`
5. `fix: harden production deployment configuration`
6. `test: cover authorization workflows and review lifecycle`
7. `docs: add verified deployment and acceptance guidance`

建议 PR 标题：`feat: complete enterprise contract review workflow and deployment readiness`

建议 PR 描述：完成合同上传、异步审查、可解释风险、人工复核、规则与知识管理、版本对比和报告导出闭环；补充 RBAC/IDOR 测试、迁移验证、前端构建优化和云部署说明。真实模型效果和生产压力测试仍需在用户自有环境执行。
