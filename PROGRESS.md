# 项目进度

## 2026-07-15：阶段一与阶段二基线

### 已完成

- 只读检查仓库结构、README、启动配置、前后端入口、数据库、审查任务、风险和报告代码。
- 从当前 FastAPI 应用成功生成 OpenAPI，盘点 95 个 API 操作。
- 确认鸿蒙端可复用的登录、用户、合同、任务进度、风险、历史和报告能力。
- 新增六份长期协作文档；未修改业务代码，未安装依赖。

### 验证记录

- `PYTHONPATH=src .venv/Scripts/python.exe -c "from contract_review.main import app; app.openapi()"`：成功，说明当前环境可导入应用并生成接口契约。
- `git -c safe.directory=D:/CodexProjects/contract-review-system status --short --branch`：成功；创建文档前工作树无已显示改动。
- 本轮没有启动服务、没有调用真实 LLM、没有运行完整 pytest、没有执行前端或 HarmonyOS 编译，因此不声称这些检查通过。

### 当前阶段

阶段二“项目文档和计划”完成，下一步是阶段三“移动端核心 API 契约确认”。

### 当前阻塞

- `harmony_app/` 尚不存在，且当前机器上的 DevEco Studio/SDK 状态尚未验证。
- 异步审查 API 的输入是服务端文件路径，移动设备不能直接提供该路径；需要选择最小后端补充方案。
- 同步 `/reviews` 和异步 `/review-tasks` 两条审查路径并存，需要确定鸿蒙首版主路径。

## 2026-07-15：HarmonyOS 原生工程骨架

### 已完成

- 在 `harmony_app/` 创建 `ContractReview` 标准 Stage 模型工程，Bundle Name 为 `com.example.contractreview`。
- 使用 ArkTS、ArkUI 和 Entry HAP 模块。
- 创建首页、合同上传模拟页、审查结果页和历史记录页，并完成页面路由。
- 创建模型、模拟服务、组件、常量、状态和工具目录；当前不连接后端、不读取真实合同。
- 使用本机 DevEco Studio 6.1、SDK API 23 和 Hvigor 6.23.6 完成真实 debug 构建。

### 验证记录

- 构建命令：`D:\DevEco Studio\tools\hvigor\bin\hvigorw.bat assembleHap --mode module -p product=default -p module=entry@default -p buildMode=debug --no-daemon`
- 结果：`BUILD SUCCESSFUL`，ArkTS 类型检查、资源编译、HAP 打包均成功。
- 修复：补齐应用/启动图标资源，并将已弃用的全局 router API 替换为 `UIContext.getRouter()`。
- 未验证：尚未在模拟器或真机安装运行，因为项目没有签名配置。

### 当前阻塞

- 需要在 DevEco Studio 中为 `entry` 配置自动签名后才能安装运行。
- SDK 打包工具在系统 Java 26 下有 `sun.misc.Unsafe` 弃用警告；本次不影响构建。

### 下一步

在 DevEco Studio 中启用自动签名并在 Phone 模拟器或真机运行四页路由流程。
