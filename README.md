# 基于 Multi-Agent 协同的企业级多源合同智能审查系统

本项目采用 `src/` 布局，后端入口为 FastAPI，合同审查流程由 LangGraph 编排。系统只调用外部大语言模型 API，不包含任何本地大模型加载逻辑。

## 工程结构

```text
contract-review-system/
├── .env.example
├── .gitignore
├── .vscode/
│   ├── launch.json
│   ├── settings.json
│   └── tasks.json
├── pyproject.toml
├── requirements.txt
├── README.md
├── data/
│   ├── reports/
│   │   └── .gitkeep
│   ├── tessdata/
│   │   └── .gitkeep
│   └── uploads/
│       └── .gitkeep
├── src/
│   └── contract_review/
│       ├── __init__.py
│       ├── main.py
│       ├── agents/
│       │   ├── __init__.py
│       │   ├── base.py
│       │   ├── compliance_checker.py
│       │   ├── coordinator.py
│       │   ├── extractor.py
│       │   └── refiner.py
│       ├── api/
│       │   ├── __init__.py
│       │   └── v1/
│       │       ├── __init__.py
│       │       ├── router.py
│       │       └── endpoints/
│       │           ├── __init__.py
│       │           ├── health.py
│       │           └── reviews.py
│       ├── core/
│       │   ├── __init__.py
│       │   ├── config.py
│       │   ├── exception_handlers.py
│       │   ├── exceptions.py
│       │   └── logging.py
│       ├── graph/
│       │   ├── __init__.py
│       │   ├── graph_builder.py
│       │   ├── routing.py
│       │   └── state.py
│       ├── knowledge/
│       │   ├── enterprise_controls.md
│       │   └── laws_cn.md
│       ├── llm/
│       │   ├── __init__.py
│       │   └── factory.py
│       ├── prompts/
│       │   ├── __init__.py
│       │   ├── compliance.py
│       │   ├── extraction.py
│       │   └── refinement.py
│       ├── schemas/
│       │   ├── __init__.py
│       │   ├── contract.py
│       │   └── review.py
│       ├── services/
│       │   ├── __init__.py
│       │   ├── document_loader.py
│       │   ├── report_service.py
│       │   └── review_service.py
│       └── utils/
│           ├── __init__.py
│           ├── file_utils.py
│           └── id_generator.py
└── tests/
    ├── __init__.py
    └── test_health.py
```

## 本地运行

```bash
python -m venv .venv
pip install -r requirements.txt
copy .env.example .env
uvicorn contract_review.main:app --reload --app-dir src
```

Windows PowerShell 也可以直接运行：

```powershell
.\run_server.ps1
```

启动后打开：

- 产品页面：http://127.0.0.1:8000/
- 接口文档：http://127.0.0.1:8000/docs

演示样例：

- `samples/demo_procurement_contract_risky.docx`：一份故意保留多处风险的中文采购合同，可直接上传测试。

停止后台服务：

```powershell
.\stop_server.ps1
```

## 当前正式开发版能力

- FastAPI 提供 RESTful 接口和 Swagger 文档。
- 提供中文产品页面，可直接上传合同并查看审查结果。
- LangGraph 编排 Coordinator、Extractor、Compliance Checker、Refiner 四类 Agent。
- 支持 PDF、Word(.docx)、图片扫描件合同输入。
- 支持中文 OCR，当前开发机已配置 Tesseract 与 `chi_sim` 语言包。
- Extractor Agent 会用规则 + AI 增强提取合同主体、合同金额、履行期限、付款条款、违约责任、争议解决、保密条款和解除终止条款。
- Compliance Checker Agent 会用规则 + AI 增强识别主体、金额、期限、付款、违约责任、争议解决、保密和终止机制风险。
- Refiner Agent 会针对风险点生成修改建议和参考条款，AI 可用时会生成更贴近合同语境的建议。
- Coordinator Agent 会汇总最终审查报告，并保存 JSON 报告到 `data/reports/`。
- `.env` 中 `ENABLE_LLM=true` 时启用外部大模型；设置为 `false` 时只使用本地规则审查。
- 内置风险评分体系，输出风险分、安全分、风险等级、维度评分和处置建议。
- 内置轻量 RAG 依据检索，基于法律规则摘要和企业内控规则为审查报告提供依据片段。
- 支持审查历史记录，最近审查会展示在首页右侧。
- 支持报告导出：JSON、Word(.docx)、PDF。
- 支持 Agent 协同轨迹，报告中会记录各节点动作和输出摘要。

## 比赛材料入口

项目已经补充可直接用于毕业设计答辩和大学生比赛打磨的说明材料：

- [新手运行指南](docs/BEGINNER_RUN_GUIDE.md)
- [比赛优化指南](docs/COMPETITION_GUIDE.md)
- [系统演示脚本](docs/DEMO_SCRIPT.md)
- [技术架构说明](docs/TECHNICAL_ARCHITECTURE.md)

建议后续把这三份文档整理成 PPT、项目说明书和演示视频脚本。

## 比赛展示亮点

- 多源输入：PDF、Word、图片 OCR 合同均可进入同一审查链路。
- Multi-Agent 协作：协调、提取、合规、修订四类 Agent 分工明确。
- RAG 可解释：风险点会关联法律规则和企业内控依据，减少黑盒感。
- 风险量化：用风险分和维度评分把审查结果做成可比较指标。
- 可交付报告：一键导出 PDF、Word 和 JSON，适合答辩现场展示。
- 低算力可运行：本地不加载大模型，通过 DeepSeek/OpenAI 兼容 API 调用外部模型。
- 过程可追踪：Agent 协同轨迹、历史记录和导出报告共同构成审查留痕。

OCR 图片合同需要额外安装 Tesseract OCR 可执行程序，并在 `.env` 中按需设置
`TESSERACT_CMD` 和 `TESSDATA_DIR`。当前开发机已安装 Tesseract，并在 `data/tessdata`
准备了 `chi_sim`、`eng`、`osd` 语言数据。
