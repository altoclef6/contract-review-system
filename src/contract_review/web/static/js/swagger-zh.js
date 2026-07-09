window.ui = SwaggerUIBundle({
  url: "/openapi.json",
  dom_id: "#swagger-ui",
  deepLinking: true,
  displayOperationId: false,
  defaultModelsExpandDepth: 2,
  defaultModelExpandDepth: 2,
  presets: [
    SwaggerUIBundle.presets.apis,
    SwaggerUIBundle.SwaggerUIStandalonePreset
  ],
  layout: "BaseLayout"
});

const dictionary = new Map([
  ["Try it out", "试一下"],
  ["Cancel", "取消"],
  ["Execute", "执行"],
  ["Clear", "清空"],
  ["Reset", "重置"],
  ["Authorize", "授权"],
  ["Close", "关闭"],
  ["Parameters", "参数"],
  ["No parameters", "无参数"],
  ["Request body", "请求体"],
  ["Responses", "响应"],
  ["Server response", "服务器响应"],
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
  ["file", "合同文件"],
  ["File", "合同文件"],
  ["string", "文本"],
  ["integer", "整数"],
  ["number", "数字"],
  ["boolean", "布尔值"],
  ["array", "数组"],
  ["object", "对象"],
  ["Successful Response", "请求成功"],
  ["Validation Error", "参数校验错误"],
  ["Undocumented", "未写入文档"],
  ["Loading...", "加载中..."]
]);

function translateText(value) {
  const trimmed = value.trim();
  if (!trimmed) return value;
  let translated = dictionary.get(trimmed);
  if (!translated) {
    translated = trimmed
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

const observer = new MutationObserver(() => translateNode(document.body));
observer.observe(document.body, { childList: true, subtree: true, characterData: true });
window.addEventListener("load", () => translateNode(document.body));
setInterval(() => translateNode(document.body), 800);
