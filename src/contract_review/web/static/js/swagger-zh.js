window.ui = SwaggerUIBundle({
  url: "/openapi.json",
  dom_id: "#swagger-ui",
  deepLinking: true,
  displayOperationId: false,
  defaultModelsExpandDepth: 1,
  defaultModelExpandDepth: 1,
  docExpansion: "list",
  filter: true,
  persistAuthorization: true,
  presets: [
    SwaggerUIBundle.presets.apis,
    SwaggerUIBundle.SwaggerUIStandalonePreset
  ],
  layout: "BaseLayout"
});

const dictionary = new Map([
  ["Available authorizations", "接口授权"],
  ["Authorize", "授权"],
  ["Close", "关闭"],
  ["Value:", "访问令牌："],
  ["Value", "访问令牌"],
  ["HTTPBearer (http, Bearer)", "登录令牌（访问令牌）"],
  ["HTTPBearer", "登录令牌"],
  ["登录令牌 (http, Bearer)", "登录令牌（访问令牌）"],
  ["Try it out", "调试接口"],
  ["Cancel", "取消"],
  ["Execute", "执行"],
  ["Clear", "清空"],
  ["Reset", "重置"],
  ["Parameters", "参数"],
  ["No parameters", "无参数"],
  ["Request body", "请求体"],
  ["Responses", "响应"],
  ["Server response", "服务端响应"],
  ["Response body", "响应内容"],
  ["Response headers", "响应头"],
  ["Request URL", "请求地址"],
  ["Curl", "命令行请求"],
  ["Code", "状态码"],
  ["Details", "详情"],
  ["Description", "说明"],
  ["Example Value", "示例值"],
  ["Schema", "数据结构"],
  ["Schemas", "数据模型"],
  ["Models", "数据模型"],
  ["required", "必填"],
  ["string", "文本"],
  ["integer", "整数"],
  ["number", "数字"],
  ["boolean", "布尔值"],
  ["array", "数组"],
  ["object", "对象"],
  ["Successful Response", "请求成功"],
  ["Validation Error", "参数校验错误"],
  ["Undocumented", "未写入文档"],
  ["Loading...", "加载中..."],
  ["No operations defined in spec!", "当前文档没有可用接口"],
  ["Filter by tag", "按标签筛选"],
  ["Search", "搜索"],
  ["Media type", "媒体类型"],
  ["Example", "示例"],
  ["Examples", "示例"],
  ["Download file", "下载文件"]
]);

function translateText(value) {
  const trimmed = value.trim();
  if (!trimmed) return value;
  let translated = dictionary.get(trimmed);
  if (!translated) {
    translated = trimmed
      .replace(/\bAvailable authorizations\b/g, "接口授权")
      .replace(/\bHTTPBearer\b/g, "登录令牌")
      .replace(/\(http, Bearer\)/g, "（访问令牌）")
      .replace(/\bValue:\b/g, "访问令牌：")
      .replace(/\brequired\b/g, "必填")
      .replace(/\bRequest body\b/g, "请求体")
      .replace(/\bNo parameters\b/g, "无参数")
      .replace(/\bParameters\b/g, "参数")
      .replace(/\bResponses\b/g, "响应")
      .replace(/\bExample Value\b/g, "示例值")
      .replace(/\bSchema\b/g, "数据结构");
  }
  if (translated === trimmed) return value;
  return `${value.match(/^\s*/)[0]}${translated}${value.match(/\s*$/)[0]}`;
}

function translateNode(root) {
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, {
    acceptNode(node) {
      const parent = node.parentElement;
      if (!parent) return NodeFilter.FILTER_REJECT;
      if (["SCRIPT", "STYLE", "TEXTAREA"].includes(parent.tagName)) return NodeFilter.FILTER_REJECT;
      return NodeFilter.FILTER_ACCEPT;
    }
  });
  const nodes = [];
  while (walker.nextNode()) nodes.push(walker.currentNode);
  for (const node of nodes) {
    const nextValue = translateText(node.nodeValue);
    if (nextValue !== node.nodeValue) node.nodeValue = nextValue;
  }
}

function polishAuthorizationDialog() {
  document.querySelectorAll("input[placeholder='Filter by tag']").forEach((input) => {
    input.setAttribute("placeholder", "按接口分组筛选");
  });

  document.querySelectorAll(".auth-container input").forEach((input) => {
    input.setAttribute("placeholder", "粘贴登录接口返回的 access_token");
    input.setAttribute("aria-label", "访问令牌");
  });

  document.querySelectorAll(".auth-container h4").forEach((title) => {
    if (title.textContent.includes("登录令牌") && !title.dataset.polished) {
      title.dataset.polished = "true";
      const hint = document.createElement("p");
      hint.className = "auth-token-hint";
      hint.textContent = "调用 /api/v1/auth/login 后复制 data.access_token 到这里。";
      title.insertAdjacentElement("afterend", hint);
    }
  });
}

function localizeSwagger() {
  translateNode(document.body);
  polishAuthorizationDialog();
}

const observer = new MutationObserver(localizeSwagger);
observer.observe(document.body, { childList: true, subtree: true, characterData: true });
window.addEventListener("load", localizeSwagger);
setInterval(localizeSwagger, 800);
