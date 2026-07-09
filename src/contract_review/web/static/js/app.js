const dom = {
  gate: document.getElementById("api-gate"),
  shell: document.getElementById("review-shell"),
  bindForm: document.getElementById("api-bind-form"),
  provider: document.getElementById("api-provider"),
  apiKey: document.getElementById("api-key"),
  apiModel: document.getElementById("api-model"),
  apiBaseUrl: document.getElementById("api-base-url"),
  bindStatus: document.getElementById("api-bind-status"),
  modelState: document.getElementById("model-state"),
  rebind: document.getElementById("rebind-api"),
  form: document.getElementById("review-form"),
  file: document.getElementById("contract-file"),
  button: document.getElementById("submit-btn"),
  status: document.getElementById("status"),
  result: document.getElementById("result"),
  badge: document.getElementById("result-badge"),
  history: document.getElementById("history-list"),
};

const API_CONFIG_KEY = "contract_review_llm_config";

function getApiConfig() {
  try {
    return JSON.parse(localStorage.getItem(API_CONFIG_KEY) || "null");
  } catch {
    return null;
  }
}

function maskKey(value) {
  if (!value) return "未绑定";
  if (value.length <= 10) return "已绑定";
  return `${value.slice(0, 4)}...${value.slice(-4)}`;
}

function providerDefaults(provider) {
  if (provider === "deepseek") {
    return { model: "deepseek-chat", baseUrl: "https://api.deepseek.com/v1" };
  }
  if (provider === "openai") {
    return { model: "gpt-4.1-mini", baseUrl: "https://api.openai.com/v1" };
  }
  return { model: "gpt-4.1-mini", baseUrl: "https://api.example.com/v1" };
}

function applyProviderDefaults() {
  const defaults = providerDefaults(dom.provider.value);
  dom.apiModel.value = defaults.model;
  dom.apiBaseUrl.value = defaults.baseUrl;
}

function showGate(config = null) {
  dom.gate.classList.remove("is-hidden");
  dom.shell.classList.add("is-hidden");
  if (config) {
    dom.provider.value = config.provider || "deepseek";
    dom.apiModel.value = config.model || providerDefaults(dom.provider.value).model;
    dom.apiBaseUrl.value = config.baseUrl || providerDefaults(dom.provider.value).baseUrl;
    dom.apiKey.value = config.apiKey || "";
  }
}

function enterWorkspace(config) {
  dom.gate.classList.add("is-hidden");
  dom.shell.classList.remove("is-hidden");
  dom.modelState.textContent = `${config.providerLabel || config.provider} / ${config.model} / ${maskKey(config.apiKey)}`;
  loadHistory();
}

function buildReviewHeaders() {
  const config = getApiConfig();
  const headers = {};
  if (!config) return headers;
  if (config.apiKey) headers["X-LLM-API-Key"] = config.apiKey;
  if (config.provider) headers["X-LLM-Provider"] = config.provider;
  if (config.model) headers["X-LLM-Model"] = config.model;
  if (config.baseUrl) headers["X-LLM-Base-Url"] = config.baseUrl;
  return headers;
}

async function validateApiConfig(config) {
  const response = await fetch("/api/v1/llm/validate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      provider: config.provider,
      api_key: config.apiKey,
      model_name: config.model,
      base_url: config.baseUrl,
    }),
  });
  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.detail || "API Key 验证失败");
  }
  return data;
}

function riskClass(level) {
  if ((level || "").includes("高")) return "risk-high";
  if ((level || "").includes("中")) return "risk-mid";
  return "risk-low";
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function compactTitle(item, fallback) {
  const raw = item["短标题"] || item["风险标题"] || item["风险类别"] || item["修改建议"] || fallback;
  const cleaned = String(raw).replace(/[，。；：:,.]/g, " ").trim();
  if (cleaned.length <= 8) return cleaned;
  return cleaned.slice(0, 8);
}

function displaySourceName(value) {
  const source = String(value || "依据");
  const dictionary = {
    "enterprise_controls.md": "企业内控标准",
    "laws_cn.md": "法律法规依据",
  };
  return dictionary[source] || source.replace(/\.md$/i, "");
}

function renderList(items, renderer, emptyText) {
  if (!Array.isArray(items) || items.length === 0) {
    return `<div class="empty-state"><span>${emptyText}</span></div>`;
  }
  return `<div class="card-grid">${items.map(renderer).join("")}</div>`;
}

function toggleGroup(containerId, button) {
  const details = Array.from(document.querySelectorAll(`#${containerId} details`));
  if (!details.length) return;
  const shouldOpen = details.some((item) => !item.open);
  details.forEach((item) => {
    item.open = shouldOpen;
  });
  button.textContent = shouldOpen ? "全部收起" : "全部展开";
}

function renderRiskDetail(item) {
  if (!item) {
    return `
      <div class="risk-detail-empty">
        <strong>选择风险点</strong>
        <span>点击左侧任一风险卡片，右侧会显示完整问题、依据和修改方向。</span>
      </div>
    `;
  }
  return `
    <div class="risk-detail-top">
      <span class="badge ${riskClass(item["风险等级"])}">${escapeHtml(item["风险等级"] || "未评级")}</span>
      <b>${escapeHtml(item["风险编号"] || "风险点")}</b>
    </div>
    <h4>${escapeHtml(item["风险标题"] || compactTitle(item, "风险详情"))}</h4>
    <div class="risk-detail-field">
      <label>风险类别</label>
      <p>${escapeHtml(item["风险类别"] || "未分类")}</p>
    </div>
    <div class="risk-detail-field">
      <label>问题说明</label>
      <p>${escapeHtml(item["问题说明"] || "暂无问题说明")}</p>
    </div>
    <div class="risk-detail-field">
      <label>相关条款</label>
      <p>${escapeHtml(item["相关条款"] || "未识别到明确条款")}</p>
    </div>
    <div class="risk-detail-field">
      <label>审查依据</label>
      <p>${escapeHtml(item["审查依据"] || "暂无审查依据")}</p>
    </div>
    <div class="risk-detail-field">
      <label>修改方向</label>
      <p>${escapeHtml(item["修改方向"] || "暂无修改方向")}</p>
    </div>
  `;
}

function selectRisk(index) {
  const source = window.__latestRiskFindings || [];
  const item = source[index];
  const detail = document.getElementById("risk-detail-panel");
  if (!detail || !item) return;
  detail.innerHTML = renderRiskDetail(item);
  document.querySelectorAll(".risk-card").forEach((card) => card.classList.remove("is-active"));
  const active = document.querySelector(`.risk-card[data-risk-index="${index}"]`);
  if (active) active.classList.add("is-active");
}

function renderRiskCard(item, index) {
  return `
    <article class="result-card risk-card ${index === 0 ? "is-active" : ""}" data-risk-index="${index}">
      <div class="card-top">
        <div class="card-title">${escapeHtml(compactTitle(item, "风险点"))}</div>
        <span class="badge ${riskClass(item["风险等级"])}">${escapeHtml(item["风险等级"] || "未评级")}</span>
      </div>
      <p class="compact-text">${escapeHtml(item["问题说明"] || item["修改方向"] || "")}</p>
      <button class="inspect-button" type="button" onclick="selectRisk(${index})">查看详情</button>
    </article>
  `;
}

function renderRiskBoard(items) {
  if (!Array.isArray(items) || items.length === 0) {
    return `<div class="empty-state"><span>未发现明显风险点。</span></div>`;
  }
  window.__latestRiskFindings = items;
  return `
    <div class="risk-workbench">
      <div class="risk-list-panel">
        <div class="risk-card-list">
          ${items.map((item, index) => renderRiskCard(item, index)).join("")}
        </div>
      </div>
      <aside id="risk-detail-panel" class="risk-detail-panel">
        ${renderRiskDetail(items[0])}
      </aside>
    </div>
  `;
}

function mergeKnowledgeItems(items) {
  if (!Array.isArray(items)) return [];
  const groups = new Map();
  for (const item of items) {
    const source = item["来源"] || "依据";
    const content = String(item["内容"] || "").trim();
    const score = Number(item["匹配分"] || 0);
    if (!groups.has(source)) {
      groups.set(source, {
        "来源": source,
        "匹配分": score,
        "条目数": 0,
        "内容列表": [],
      });
    }
    const group = groups.get(source);
    group["匹配分"] = Math.max(group["匹配分"], score);
    if (content && !group["内容列表"].some((text) => text.includes(content) || content.includes(text))) {
      group["内容列表"].push(content);
      group["条目数"] += 1;
    }
  }
  return Array.from(groups.values()).sort((a, b) => Number(b["匹配分"]) - Number(a["匹配分"]));
}

function renderKnowledgeDetail(item) {
  if (!item) {
    return `
      <div class="risk-detail-empty">
        <strong>选择依据</strong>
        <span>点击左侧依据来源，右侧会集中展示合并后的依据片段。</span>
      </div>
    `;
  }
  const snippets = item["内容列表"] || [];
  return `
    <div class="risk-detail-top">
      <span class="badge">匹配 ${escapeHtml(item["匹配分"] || "0")}</span>
      <b>${escapeHtml(item["条目数"] || snippets.length || 0)} 条</b>
    </div>
    <h4>${escapeHtml(displaySourceName(item["来源"]))}</h4>
    <div class="knowledge-snippets">
      ${snippets.map((text, index) => `
        <div class="knowledge-snippet">
          <label>依据 ${index + 1}</label>
          <p>${escapeHtml(text)}</p>
        </div>
      `).join("") || `<p class="detail-text">暂无依据内容。</p>`}
    </div>
  `;
}

function selectKnowledge(index) {
  const source = window.__latestKnowledgeItems || [];
  const item = source[index];
  const detail = document.getElementById("knowledge-detail-panel");
  if (!detail || !item) return;
  detail.innerHTML = renderKnowledgeDetail(item);
  document.querySelectorAll(".knowledge-card").forEach((card) => card.classList.remove("is-active"));
  const active = document.querySelector(`.knowledge-card[data-knowledge-index="${index}"]`);
  if (active) active.classList.add("is-active");
}

function renderKnowledgeCard(item, index) {
  const snippets = item["内容列表"] || [];
  const summary = snippets[0] || "";
  return `
    <article class="result-card knowledge-card ${index === 0 ? "is-active" : ""}" data-knowledge-index="${index}">
      <div class="card-top">
        <div class="card-title">${escapeHtml(displaySourceName(item["来源"]))}</div>
        <span class="badge">${escapeHtml(item["条目数"] || snippets.length || 0)} 条</span>
      </div>
      <p class="compact-text">${escapeHtml(summary)}</p>
      <button class="inspect-button" type="button" onclick="selectKnowledge(${index})">查看依据</button>
    </article>
  `;
}

function renderKnowledgeBoard(items) {
  const merged = mergeKnowledgeItems(items);
  if (!merged.length) {
    return `<div class="empty-state"><span>暂无依据检索结果。</span></div>`;
  }
  window.__latestKnowledgeItems = merged;
  return `
    <div class="knowledge-workbench">
      <div class="knowledge-list-panel">
        <div class="knowledge-card-list">
          ${merged.map((item, index) => renderKnowledgeCard(item, index)).join("")}
        </div>
      </div>
      <aside id="knowledge-detail-panel" class="knowledge-detail-panel">
        ${renderKnowledgeDetail(merged[0])}
      </aside>
    </div>
  `;
}

function renderSuggestionChat(item) {
  if (!item) {
    return `
      <div class="chat-empty">
        <strong>选择修改建议</strong>
        <span>点击左侧建议，右侧会以对话形式输出建议理由和参考条款。</span>
      </div>
    `;
  }
  return `
    <div class="chat-message assistant">
      <span class="chat-role">AI 修改助理</span>
      <p>我建议优先处理「${escapeHtml(item["风险类别"] || item["对应风险编号"] || "该条风险")}」。</p>
    </div>
    <div class="chat-message user">
      <span class="chat-role">修改方向</span>
      <p>${escapeHtml(item["修改建议"] || "暂无修改建议。")}</p>
    </div>
    <div class="chat-message assistant">
      <span class="chat-role">参考条款</span>
      <p>${escapeHtml(item["建议条款"] || "暂无参考条款。")}</p>
    </div>
  `;
}

function selectSuggestion(index) {
  const source = window.__latestSuggestions || [];
  const item = source[index];
  const detail = document.getElementById("suggestion-chat-panel");
  if (!detail || !item) return;
  detail.innerHTML = renderSuggestionChat(item);
  document.querySelectorAll(".suggestion-card").forEach((card) => card.classList.remove("is-active"));
  const active = document.querySelector(`.suggestion-card[data-suggestion-index="${index}"]`);
  if (active) active.classList.add("is-active");
}

function renderSuggestionCard(item, index) {
  return `
    <article class="result-card suggestion-card ${index === 0 ? "is-active" : ""}" data-suggestion-index="${index}">
      <div class="card-top">
        <div class="card-title">${escapeHtml(compactTitle(item, "建议"))}</div>
        <span class="badge">${escapeHtml(item["对应风险编号"] || item["来源"] || "建议")}</span>
      </div>
      <p class="compact-text">${escapeHtml(item["修改建议"] || "")}</p>
      <button class="inspect-button" type="button" onclick="selectSuggestion(${index})">发送到右侧</button>
    </article>
  `;
}

function renderSuggestionBoard(items) {
  if (!Array.isArray(items) || items.length === 0) {
    return `<div class="empty-state"><span>暂无修改建议。</span></div>`;
  }
  window.__latestSuggestions = items;
  return `
    <div class="suggestion-workbench">
      <div class="suggestion-list-panel">
        <div class="suggestion-card-list">
          ${items.map((item, index) => renderSuggestionCard(item, index)).join("")}
        </div>
      </div>
      <aside class="suggestion-chat">
        <div class="chat-head">
          <strong>AI 修改助理</strong>
          <span>建议输出</span>
        </div>
        <div id="suggestion-chat-panel" class="chat-body">
          ${renderSuggestionChat(items[0])}
        </div>
      </aside>
    </div>
  `;
}

function renderTrace(trace) {
  if (!Array.isArray(trace) || trace.length === 0) {
    return `<div class="empty-state"><span>暂无 Agent 协同轨迹。</span></div>`;
  }
  return `
    <div class="trace-grid">
      ${trace.map((item) => `
        <div class="trace-item">
          <b>${escapeHtml(item["节点"] || "Agent 节点")}</b>
          <span>${escapeHtml(item["动作"] || "")}</span>
          <em>${escapeHtml(item["输出"] || item["状态"] || "")}</em>
        </div>
      `).join("")}
    </div>
  `;
}

function renderResult(data) {
  const report = data.final_report || {};
  const stats = report["风险统计"] || {};
  const score = report["风险评分"] || {};
  const dimensions = score["维度评分"] || {};
  const knowledge = report["依据检索"] || [];
  const trace = data.agent_trace || report["Agent协同轨迹"] || [];
  const level = report["总体风险等级"] || "未评估";
  const findings = data.risk_findings || [];
  const suggestions = data.revision_suggestions || [];

  dom.badge.textContent = data.status || "已完成";
  dom.badge.className = `badge ${riskClass(level)}`;
  dom.result.innerHTML = `
    <div class="summary-grid">
      <div class="metric"><label>总体风险</label><strong class="${riskClass(level)}">${escapeHtml(level)}</strong></div>
      <div class="metric"><label>风险分</label><strong class="${riskClass(level)}">${score["风险分"] ?? "-"}</strong></div>
      <div class="metric"><label>安全分</label><strong class="risk-low">${score["安全分"] ?? "-"}</strong></div>
      <div class="metric"><label>风险数量</label><strong>${stats["风险数量"] ?? findings.length}</strong></div>
    </div>

    <section class="section-block">
      <div class="section-head"><h3>审查摘要</h3></div>
      <p class="detail-text">${escapeHtml(report["审查摘要"] || "暂无摘要")}</p>
      <p class="detail-text">报告路径：${escapeHtml(data.report_path || "未保存")}</p>
      <div class="export-row">
        ${renderExportLinks(data)}
      </div>
    </section>

    <section class="section-block">
      <div class="section-head"><h3>Agent 协同轨迹</h3></div>
      ${renderTrace(trace)}
    </section>

    <section class="section-block">
      <div class="section-head"><h3>风险维度</h3></div>
      <div class="dimension-grid">
        ${Object.entries(dimensions).map(([name, value]) => `
          <div class="dimension-card">
            <b>${escapeHtml(name)}</b>
            <div class="bar"><i style="width:${Math.min(100, Number(value) || 0)}%"></i></div>
            <p class="detail-text">${Number(value) || 0} 分</p>
          </div>
        `).join("") || `<div class="empty-state"><span>暂无维度评分。</span></div>`}
      </div>
    </section>

    <section class="section-block">
      <div class="section-head">
        <h3>风险点</h3>
        <span class="section-note">点击风险卡片，右侧独立查看详情</span>
      </div>
      <div id="risk-list">${renderRiskBoard(findings)}</div>
    </section>

    <section class="section-block">
      <div class="section-head">
        <h3>修改建议</h3>
        <span class="section-note">点击左侧建议，右侧以对话形式输出条款</span>
      </div>
      <div id="suggestion-list">${renderSuggestionBoard(suggestions)}</div>
    </section>

    <section class="section-block">
      <div class="section-head">
        <h3>依据检索</h3>
        <span class="section-note">同来源依据已合并，点击左侧查看完整片段</span>
      </div>
      <div id="knowledge-list">${renderKnowledgeBoard(knowledge)}</div>
    </section>

    <section class="section-block">
      <details>
        <summary>查看完整 JSON</summary>
        <pre>${escapeHtml(JSON.stringify(data, null, 2))}</pre>
      </details>
    </section>
  `;
  loadHistory();
}

function renderExportLinks(data) {
  const reviewId = data.review_id;
  if (!reviewId) return "";
  return ["pdf", "docx", "json"].map((type) => (
    `<a class="export-link" href="/api/v1/reviews/${reviewId}/download?file_type=${type}" target="_blank">下载 ${type.toUpperCase()}</a>`
  )).join("");
}

async function loadHistory() {
  if (!dom.history) return;
  try {
    const response = await fetch("/api/v1/reviews");
    const records = await response.json();
    if (!Array.isArray(records) || records.length === 0) {
      dom.history.innerHTML = `<span class="history-empty">暂无历史记录。</span>`;
      return;
    }
    dom.history.innerHTML = records.slice(0, 6).map((item) => `
      <div class="history-item" onclick="openHistory('${escapeHtml(item.review_id)}')">
        <b>${escapeHtml(item.file_name || item.review_id)}</b>
        <span>${escapeHtml(item.overall_risk_level || "未评估")} · 风险分 ${escapeHtml(item.risk_score ?? "-")}</span>
      </div>
    `).join("");
  } catch (error) {
    dom.history.innerHTML = `<span class="history-empty">历史记录读取失败。</span>`;
  }
}

async function openHistory(reviewId) {
  try {
    const response = await fetch(`/api/v1/reviews/${reviewId}`);
    const report = await response.json();
    if (!response.ok) throw new Error(report.detail || "读取失败");
    renderResult({
      review_id: reviewId,
      status: "已完成",
      final_report: report,
      risk_findings: report["风险点"] || [],
      revision_suggestions: report["修改建议"] || [],
      report_path: `data/reports/${reviewId}.json`,
    });
    dom.status.textContent = "已载入历史审查记录。";
  } catch (error) {
    dom.status.textContent = `历史记录读取失败：${error.message}`;
  }
}

dom.form.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!dom.file.files.length) return;

  const body = new FormData();
  body.append("合同文件", dom.file.files[0]);
  dom.button.disabled = true;
  dom.status.textContent = "正在解析合同并执行 Multi-Agent 审查，AI 增强可能需要几十秒。";
  dom.badge.textContent = "审查中";
  dom.result.innerHTML = `<div class="empty-state"><strong>审查进行中</strong><span>正在进行文档解析、风险识别与建议生成。</span></div>`;

  try {
    const response = await fetch("/api/v1/reviews", {
      method: "POST",
      body,
      headers: buildReviewHeaders(),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || "审查失败");
    dom.status.textContent = "审查完成。";
    renderResult(data);
  } catch (error) {
    dom.status.textContent = `审查失败：${error.message}`;
    dom.badge.textContent = "失败";
    dom.result.innerHTML = `<div class="empty-state"><strong>请求失败</strong><span>${escapeHtml(error.message)}</span></div>`;
  } finally {
    dom.button.disabled = false;
  }
});

dom.provider.addEventListener("change", applyProviderDefaults);

dom.bindForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const providerLabel = dom.provider.options[dom.provider.selectedIndex]?.textContent || dom.provider.value;
  const config = {
    provider: dom.provider.value,
    providerLabel,
    apiKey: dom.apiKey.value.trim(),
    model: dom.apiModel.value.trim(),
    baseUrl: dom.apiBaseUrl.value.trim(),
    savedAt: new Date().toISOString(),
  };
  if (!config.apiKey || !config.model || !config.baseUrl) return;
  const submitButton = dom.bindForm.querySelector("button[type='submit']");
  submitButton.disabled = true;
  dom.bindStatus.textContent = "正在验证 API Key 和模型连通性...";
  try {
    const result = await validateApiConfig(config);
    config.validatedAt = new Date().toISOString();
    config.latencyMs = result.latency_ms;
    localStorage.setItem(API_CONFIG_KEY, JSON.stringify(config));
    dom.bindStatus.textContent = `验证成功，响应耗时 ${result.latency_ms} ms。`;
    enterWorkspace(config);
  } catch (error) {
    dom.bindStatus.textContent = `验证失败：${error.message}`;
  } finally {
    submitButton.disabled = false;
  }
});

dom.rebind.addEventListener("click", () => {
  showGate(getApiConfig());
});

const savedConfig = getApiConfig();
if (savedConfig?.apiKey && savedConfig?.model && savedConfig?.baseUrl) {
  enterWorkspace(savedConfig);
} else {
  showGate();
}
