# 新手运行指南

## 你需要先运行什么环境

这个项目不用安装本地大模型，也不用显卡跑模型。你只需要：

1. Python 3.10 或更高版本。
2. 项目自带虚拟环境 `.venv`。
3. `.env` 里的 DeepSeek 或 OpenAI 兼容 API Key。
4. 可选：Tesseract OCR，用来识别扫描件图片合同。当前电脑已经装好。

## 每次启动项目

打开 VS Code 后，确认左侧打开的是：

```text
D:\CodexProjects\contract-review-system
```

然后在 VS Code 下方终端执行：

```powershell
.\run_server.ps1
```

看到类似下面内容就说明启动成功：

```text
Uvicorn running on http://127.0.0.1:8000
```

然后打开浏览器：

```text
http://127.0.0.1:8000/
```

## 进入页面后先做什么

新版页面会先让你绑定个人 AI 接口，类似登录：

1. 服务商选择 `DeepSeek`。
2. `API Key` 输入你的 DeepSeek Key。
3. 模型名称默认用 `deepseek-chat`。
4. Base URL 默认用 `https://api.deepseek.com/v1`。
5. 点击“进入审查工作台”。

绑定后才能进入合同审查页面。后续上传合同时，系统会把这次绑定的模型配置随请求发送给后端，用于本次 Multi-Agent 审查。

点击“进入审查工作台”时，系统会先真实调用一次模型验证 Key 是否可用。验证失败时不会进入工作台，需要检查：

1. API Key 是否复制完整。
2. Base URL 是否正确，例如 DeepSeek 是 `https://api.deepseek.com/v1`。
3. 模型名称是否正确，例如 DeepSeek 是 `deepseek-chat`。
4. 账户余额或额度是否可用。

如果你要换 Key，进入工作台后点击右上角“重新绑定”。

## 关闭项目

如果终端还开着，按 `Ctrl + C`。

如果你不知道哪个终端在运行，就在项目目录执行：

```powershell
.\stop_server.ps1
```

## 第一次重新装环境时才需要

平时不用重复执行。只有虚拟环境坏了或换电脑时才需要：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## AI Key 放在哪里

AI 配置在项目根目录的 `.env` 文件里，例如：

```text
ENABLE_LLM=true
LLM_PROVIDER=deepseek
LLM_MODEL_NAME=deepseek-chat
LLM_BASE_URL=https://api.deepseek.com/v1
DEEPSEEK_API_KEY=你的 key
```

页面绑定的 Key 会优先用于本次审查；`.env` 里的 Key 是本地默认兜底配置。

不要把 `.env` 上传到 GitHub 或发给别人。
