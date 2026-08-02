<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Delete, Document, Download, Refresh, UploadFilled, View } from '@element-plus/icons-vue'
import { api } from '../api'
import EmptyState from '../components/EmptyState.vue'
import MetricCard from '../components/MetricCard.vue'
import PageHeader from '../components/PageHeader.vue'
import RiskLevelTag from '../components/RiskLevelTag.vue'
import { validateContractFile } from '../services/contracts'

interface TextLocation {
  定位状态: '精确定位' | '相关上下文' | '缺失条款'
  字符起点: number | null
  字符终点: number | null
  定位文本: string
}

const file = ref<File>()
const uploadRef = ref<any>()
const type = ref('general')
const loading = ref(false)
const result = ref<any>()
const activeRisk = ref<any>()
const reviewError = ref('')
const demoMode = ref(false)
const reportDialog = ref(false)
const legalDrawer = ref(false)
const legalDetail = ref<any>()
const reportGenerating = ref(false)
const highlightedClause = ref<HTMLElement>()
const elapsedSeconds = ref(0)
const analysisStepIndex = ref(0)
let elapsedTimer: number | undefined
let stepTimer: number | undefined

const analysisSteps = [
  '正在解析合同',
  '正在识别合同类型',
  '正在切分合同条款',
  '正在匹配风险规则',
  '正在检索法律依据',
  '正在生成修改建议',
  '正在生成审查结果',
]

const formattedFileSize = computed(() => {
  if (!file.value) return ''
  const megabytes = file.value.size / 1024 / 1024
  return megabytes >= 1 ? `${megabytes.toFixed(2)} MB` : `${Math.max(1, Math.round(file.value.size / 1024))} KB`
})
const severeRiskCount = computed(() => result.value?.risk_findings?.filter(
  (risk: any) => risk.风险等级 === '高' || risk.风险等级 === '严重',
).length || 0)
const overallRiskClass = computed(() => {
  const level = result.value?.final_report?.总体风险等级
  if (level === '高' || level === '严重') return 'is-high'
  if (level === '中') return 'is-medium'
  return 'is-low'
})

const activeLocation = computed<TextLocation | undefined>(() => activeRisk.value?.原文定位)
const activeSuggestion = computed(() => result.value?.revision_suggestions?.find(
  (item: any) => item.对应风险编号 === activeRisk.value?.风险编号,
))
const locationStart = computed(() => activeLocation.value?.字符起点 ?? -1)
const locationEnd = computed(() => activeLocation.value?.字符终点 ?? -1)
const textBefore = computed(() => {
  if (locationStart.value < 0) return result.value?.contract_text || ''
  return result.value.contract_text.slice(0, locationStart.value)
})
const textHighlighted = computed(() => {
  if (locationStart.value < 0) return ''
  return result.value.contract_text.slice(locationStart.value, locationEnd.value)
})
const textAfter = computed(() => {
  if (locationStart.value < 0) return ''
  return result.value.contract_text.slice(locationEnd.value)
})

async function run() {
  if (!file.value) return ElMessage.warning('请选择合同文件')
  loading.value = true
  reviewError.value = ''
  demoMode.value = false
  result.value = undefined
  activeRisk.value = undefined
  elapsedSeconds.value = 0
  analysisStepIndex.value = 0
  const startedAt = performance.now()
  window.clearInterval(elapsedTimer)
  elapsedTimer = window.setInterval(() => {
    elapsedSeconds.value = Math.floor((performance.now() - startedAt) / 1000)
  }, 1000)
  window.clearInterval(stepTimer)
  stepTimer = window.setInterval(() => {
    analysisStepIndex.value = Math.min(analysisStepIndex.value + 1, analysisSteps.length - 1)
  }, 2200)
  const form = new FormData()
  form.append('合同文件', file.value)
  form.append('合同类型', type.value)
  try {
    result.value = (await api.post('/reviews', form, { timeout: 90000 })).data
    activeRisk.value = result.value.risk_findings.find(
      (risk: any) => risk.原文定位?.字符起点 !== null,
    ) || result.value.risk_findings[0]
    ElMessage.success('审查完成')
    await focusRisk(activeRisk.value)
    await new Promise((resolve) => window.setTimeout(resolve, 420))
  } catch (error: any) {
    if (error.code === 'ECONNABORTED') {
      reviewError.value = '外部模型响应超时。你可以重新分析，或加载专业演示结果继续验收流程。'
    } else if (!error.response) {
      reviewError.value = '审查服务连接中断。请确认后端服务正在运行，或加载演示结果继续展示。'
    } else {
      reviewError.value = error.response?.data?.detail || error.response?.data?.message || 'AI 分析失败，请重试或加载演示结果。'
    }
    ElMessage.error('审查未完成，页面已保留重试与演示兜底入口')
  } finally {
    window.clearInterval(elapsedTimer)
    window.clearInterval(stepTimer)
    loading.value = false
  }
}

async function loadDemoResult() {
  const contractText = `软件开发服务合同\n甲方委托乙方开发合同管理系统。项目总价为人民币 300,000 元，付款时间由双方另行协商。\n乙方完成系统后提交甲方验收，具体功能范围、测试方法和验收期限后续确定。\n项目开发过程中形成的程序、文档及其他成果，其知识产权归属由双方另行协商。\n如乙方延期交付，每延迟一日支付合同总额 1% 的违约金；甲方逾期付款不承担违约责任。\n双方应对履约中知悉的商业秘密承担保密义务。争议协商不成的，提交甲方所在地人民法院处理。`
  const risks = [
    { 风险编号: 'R001', 风险类别: '付款条件', 风险等级: '高', 短标题: '付款条件不明确', 风险标题: '付款节点与到期条件缺乏可执行约定', 相关条款: '付款时间由双方另行协商。', 问题说明: '条款未约定首付款、里程碑付款比例、发票条件及最终付款期限，容易引发回款与履约争议。', 可能后果: '双方可能因付款到期日和交付义务先后顺序产生争议，增加现金流与诉讼风险。', 修改方向: '按照签约、阶段交付、终验三个节点明确比例、到期日及付款前置条件。' },
    { 风险编号: 'R002', 风险类别: '验收', 风险等级: '高', 短标题: '验收标准缺失', 风险标题: '验收范围、方法与期限约定不完整', 相关条款: '具体功能范围、测试方法和验收期限后续确定。', 问题说明: '未形成可量化的交付清单与验收规则，也未约定逾期未反馈的处理机制。', 可能后果: '项目完成标准无法客观判断，可能造成反复修改、结算延迟或拒绝验收。', 修改方向: '在附件中固化功能清单、性能指标、测试环境、整改次数和验收确认期限。' },
    { 风险编号: 'R003', 风险类别: '知识产权', 风险等级: '中', 短标题: '成果权属不清', 风险标题: '知识产权归属与既有成果许可边界不明确', 相关条款: '其知识产权归属由双方另行协商。', 问题说明: '未区分定制成果、乙方既有技术、开源组件及第三方素材，后续商业使用存在不确定性。', 可能后果: '甲方可能无法完整使用或处分交付成果，乙方也可能承担超出预期的权利转让义务。', 修改方向: '区分背景知识产权与项目成果，明确转让或许可范围、时间、地域及交付源代码条件。' },
    { 风险编号: 'R004', 风险类别: '违约责任', 风险等级: '高', 短标题: '责任明显不对等', 风险标题: '违约责任仅约束乙方且比例可能过高', 相关条款: '每延迟一日支付合同总额 1% 的违约金；甲方逾期付款不承担违约责任。', 问题说明: '责任配置不对等，且每日 1% 未设置累计上限，与可预见损失可能明显失衡。', 可能后果: '违约金可能被司法调整，同时加剧谈判阻力并形成单方责任风险。', 修改方向: '设置双方对等的逾期责任，并将累计违约金上限控制在合同总额的合理比例。' },
  ]
  for (const risk of risks) {
    const start = contractText.indexOf(risk.相关条款)
    Object.assign(risk, {
      legalBasis: [], legal_basis: [], 审查依据: '未匹配到已核验法律依据',
      原文定位: { 定位状态: '精确定位', 字符起点: start, 字符终点: start + risk.相关条款.length, 定位文本: risk.相关条款 },
    })
  }
  try {
    const matches = (await api.get('/legal-knowledge/articles', { params: { keyword: '违约金' } })).data.data.items
    const article = matches.find((item: any) => item.article_no === '第五百八十五条') || matches[0]
    if (article) {
      const basis = {
        legalArticleId: article.id,
        lawName: article.law_name,
        articleNo: article.article_no,
        sourceUrl: article.source_url,
        contentSummary: article.content.slice(0, 220),
        sourceName: article.source_name,
        version: article.law_version,
      }
      Object.assign(risks[3], {
        legalBasis: [basis], legal_basis: [basis],
        审查依据: `《${article.law_name}》${article.article_no}`,
      })
    }
  } catch {
    // 演示兜底仍保持“未匹配”状态，不补造任何法律引用。
  }
  result.value = {
    review_id: 'demo_acceptance_software_contract', file_name: file.value?.name || '软件开发服务合同.docx', contract_text: contractText,
    status: '已完成', risk_findings: risks,
    revision_suggestions: [
      { 对应风险编号: 'R001', 修改建议: '细化付款条件并绑定可验证的里程碑。', 建议条款: '合同价款分三期支付：签约后 5 个工作日内支付 30%；阶段版本经书面确认后支付 40%；最终验收合格并收到合法发票后 10 个工作日内支付 30%。' },
      { 对应风险编号: 'R002', 修改建议: '将验收标准、期限和视为验收机制写入附件。', 建议条款: '甲方应在收到交付成果后 10 个工作日内依据附件验收标准完成测试并书面反馈；逾期未提出具体异议的，视为该阶段验收通过。' },
      { 对应风险编号: 'R003', 修改建议: '区分项目成果与背景知识产权。', 建议条款: '甲方付清全部价款后取得定制开发成果的知识产权；乙方既有工具和通用组件权利仍归乙方，但应授予甲方永久、不可撤销的项目使用许可。' },
      { 对应风险编号: 'R004', 修改建议: '设置对等责任及累计上限。', 建议条款: '任何一方逾期履行的，每日按逾期部分金额的 0.05% 承担违约金，累计不超过合同总额的 10%；不足以弥补直接损失的，守约方可就差额主张赔偿。' },
    ],
    final_report: { 总体风险等级: '高风险', 风险评分: { 风险分: 78, 安全分: 22 }, 审查摘要: '本合同共识别 4 项重点风险，其中 3 项高风险、1 项中风险。建议在付款、验收、知识产权和违约责任条款修订后再签署。' },
  }
  activeRisk.value = risks[0]
  demoMode.value = true
  reviewError.value = ''
  ElMessage.success('已加载专业演示结果，可继续查看风险与审查报告')
  void focusRisk(activeRisk.value)
}

async function showReport() {
  reportGenerating.value = true
  await new Promise((resolve) => window.setTimeout(resolve, 650))
  reportGenerating.value = false
  reportDialog.value = true
  ElMessage.success('审查报告已生成')
}

async function openLegalArticle(basis: any) {
  try {
    legalDetail.value = (await api.get(`/legal-knowledge/articles/${basis.legalArticleId}`)).data.data
    legalDrawer.value = true
  } catch (cause: any) {
    ElMessage.error(cause?.response?.data?.detail || '法律条文当前不可访问')
  }
}

async function downloadReport(fileType: string) {
  if (demoMode.value) return ElMessage.info('演示兜底结果仅支持页面预览；连接真实后端后可下载正式报告')
  try {
    const response = await api.get(`/reviews/${result.value.review_id}/download`, { params: { file_type: fileType }, responseType: 'blob' })
    const url = URL.createObjectURL(response.data)
    const anchor = document.createElement('a')
    anchor.href = url; anchor.download = `${result.value.review_id}.${fileType}`; anchor.click(); URL.revokeObjectURL(url)
  } catch (cause: any) { ElMessage.error(cause?.response?.data?.message || '报告下载失败') }
}

async function focusRisk(risk: any) {
  activeRisk.value = risk
  await nextTick()
  highlightedClause.value?.scrollIntoView({ behavior: 'smooth', block: 'center' })
}

const onChange = (upload: any) => {
  const selected = upload.raw as File
  const validationError = validateContractFile(selected)
  if (validationError) {
    uploadRef.value?.clearFiles()
    file.value = undefined
    ElMessage.warning(validationError)
    return
  }
  file.value = selected
  ElMessage.success('文件校验通过，可以开始审查')
}

function triggerUpload() {
  uploadRef.value?.clearFiles()
  window.requestAnimationFrame(() => {
    uploadRef.value?.$el?.querySelector('input[type="file"]')?.click()
  })
}

function removeFile() {
  uploadRef.value?.clearFiles()
  file.value = undefined
}

onBeforeUnmount(() => { window.clearInterval(elapsedTimer); window.clearInterval(stepTimer) })
</script>

<template>
  <div class="review-page">
    <PageHeader title="智能审查工作台" description="上传合同后执行文档解析、确定性规则与 AI 辅助审查，并定位风险原文。" eyebrow="合同风险审查" />

    <main class="review-content">
      <section class="review-setup" aria-label="合同上传与审查配置">
        <div class="setup-card upload-card">
          <div class="module-heading">
            <div><h2>上传合同</h2><p>上传待审查的合同原始文件</p></div>
          </div>
          <el-upload
            ref="uploadRef"
            class="contract-uploader"
            drag
            :auto-upload="false"
            :limit="1"
            :show-file-list="false"
            accept=".pdf,.doc,.docx,.txt"
            :on-change="onChange"
          >
            <div v-if="!file" class="upload-placeholder">
              <span class="upload-icon-wrap"><el-icon><UploadFilled /></el-icon></span>
              <div><strong>拖放合同文件到此处，或点击选择</strong><small>支持 DOCX、文本型 PDF、TXT，单文件不超过 50 MB</small></div>
            </div>
            <div v-else class="selected-file" @click.stop>
              <span class="file-icon"><el-icon><Document /></el-icon></span>
              <div class="file-meta"><strong :title="file.name">{{ file.name }}</strong><span>{{ formattedFileSize }} · 等待开始审查</span></div>
              <span class="upload-success"><i></i>文件已就绪</span>
              <div class="file-actions">
                <el-button text :icon="Refresh" @click.stop="triggerUpload">重新上传</el-button>
                <el-button text class="delete-file" :icon="Delete" @click.stop="removeFile">删除</el-button>
              </div>
            </div>
          </el-upload>
        </div>

        <div class="setup-card review-options">
          <div class="module-heading"><div><h2>审查配置</h2><p>选择合同类型与审查能力</p></div></div>
          <label for="contract-type">合同类型</label>
          <el-select id="contract-type" v-model="type">
            <el-option label="通用合同" value="general" /><el-option label="采购合同" value="purchase" />
            <el-option label="销售合同" value="sales" /><el-option label="劳动合同" value="employment" />
            <el-option label="租赁合同" value="lease" /><el-option label="保密协议" value="nda" />
            <el-option label="服务合同" value="service" />
          </el-select>
          <div class="capability-tags" aria-label="审查能力">
            <span>要素提取</span><span>合规校验</span><span>风险评分</span><span>条款优化</span>
          </div>
          <el-button class="start-review" type="primary" :loading="loading" :disabled="loading" @click="run">开始审查</el-button>
          <p class="duration-hint">通常 30～90 秒，超时可加载演示结果</p>
        </div>
      </section>

      <section v-if="reviewError" class="review-fallback" role="alert">
        <div><strong>本次 AI 审查未完成</strong><p>{{ reviewError }}</p></div>
        <div><el-button :icon="Refresh" @click="run">重新分析</el-button><el-button type="primary" @click="loadDemoResult">加载演示结果</el-button></div>
      </section>
      <el-alert v-if="demoMode" title="当前展示的是专业演示兜底结果，不会覆盖真实审查记录。" type="warning" :closable="false" show-icon />

      <section class="result-area" aria-label="审查结果">
        <div v-if="result" class="result-summary">
          <MetricCard label="综合风险" :value="`${result.final_report?.总体风险等级}风险`" :tone="overallRiskClass === 'is-high' ? 'high' : overallRiskClass === 'is-medium' ? 'medium' : 'low'" />
          <MetricCard label="风险评分" :value="result.final_report?.风险评分?.风险分" unit="/ 100" tone="medium" />
          <MetricCard label="风险点" :value="result.risk_findings.length" unit="项" />
          <MetricCard label="严重风险" :value="severeRiskCount" unit="项" tone="high" />
        </div>

        <EmptyState v-if="!result" title="尚未生成审查结果" description="上传合同并开始审查后，系统将在此展示风险条款、风险说明和修改建议。" />

        <section v-else class="results">
          <div class="result-toolbar">
            <div><h2>审查结果</h2><p>选择风险项可在合同全文中定位相关原文</p></div>
            <div class="result-actions"><router-link to="/contracts"><el-button>返回合同列表</el-button></router-link><router-link v-if="!demoMode" :to="`/reader/${result.review_id}`"><el-button :icon="View">审查复核工作区</el-button></router-link><el-button type="primary" :icon="Document" :loading="reportGenerating" @click="showReport">生成并查看报告</el-button></div>
          </div>

          <div class="review-result-workbench">
      <aside class="risk-pane">
        <header><div><h2>风险点</h2><span>移入风险可定位原文</span></div><b>{{ result.risk_findings.length }}</b></header>
        <div class="risk-pane-list">
          <button
            v-for="risk in result.risk_findings"
            :key="risk.风险编号"
            :class="['linked-risk', { active: activeRisk?.风险编号 === risk.风险编号 }]"
            @mouseenter="focusRisk(risk)"
            @focus="focusRisk(risk)"
            @click="focusRisk(risk)"
          >
            <div class="linked-risk-title">
              <RiskLevelTag :level="risk.风险等级" />
              <strong>{{ risk.短标题 || risk.风险类别 }}</strong>
              <small>{{ risk.风险编号 }}</small>
            </div>
            <p>{{ risk.风险标题 }}</p>
            <span>{{ risk.问题说明 }}</span>
            <div class="location-state" :class="risk.原文定位?.定位状态 === '缺失条款' ? 'missing' : ''">
              {{ risk.原文定位?.定位状态 === '缺失条款' ? '缺失条款，建议补充' : `${risk.原文定位?.定位状态} · 移入查看` }}
            </div>
            <div v-if="activeRisk?.风险编号 === risk.风险编号" class="active-risk-advice">
              <b>修改方向</b><span>{{ risk.修改方向 }}</span>
            </div>
          </button>
        </div>
      </aside>

      <article class="contract-pane">
        <header>
          <div><h2>合同全文</h2><span>{{ result.file_name }}</span></div>
          <el-tag v-if="activeLocation" :type="activeLocation.定位状态 === '缺失条款' ? 'info' : 'success'">{{ activeLocation.定位状态 }}</el-tag>
        </header>
        <div class="contract-document">
          <pre><span>{{ textBefore }}</span><mark v-if="textHighlighted" ref="highlightedClause">{{ textHighlighted }}</mark><span>{{ textAfter }}</span></pre>
        </div>
      </article>
          </div>

          <section v-if="activeRisk" class="risk-detail-card">
            <header><div><RiskLevelTag :level="activeRisk.风险等级" /><h3>{{ activeRisk.风险标题 }}</h3></div><small>{{ activeRisk.风险编号 }} · {{ activeRisk.风险类别 }}</small></header>
            <div class="risk-detail-grid">
              <article><span>条款原文</span><p>{{ activeRisk.相关条款 || activeLocation?.定位文本 || '合同中未发现对应条款' }}</p></article>
              <article><span>风险说明</span><p>{{ activeRisk.问题说明 }}</p></article>
              <article><span>可能后果</span><p>{{ activeRisk.可能后果 || '可能造成履约边界不清、争议处理成本上升或责任承担不确定。' }}</p></article>
              <article><span>法务建议</span><p>{{ activeSuggestion?.修改建议 || activeRisk.修改方向 }}</p></article>
              <article class="recommended-clause"><span>推荐修改文本</span><p>{{ activeSuggestion?.建议条款 || activeRisk.修改方向 }}</p></article>
            </div>
            <section class="legal-basis-block">
              <div><span>已核验法律依据</span><small>引用内容以知识库当前有效记录为准</small></div>
              <div v-if="(activeRisk.legalBasis || activeRisk.legal_basis || []).length" class="legal-basis-list">
                <button v-for="basis in (activeRisk.legalBasis || activeRisk.legal_basis)" :key="basis.legalArticleId" type="button" @click="openLegalArticle(basis)">
                  <strong>《{{ basis.lawName }}》{{ basis.articleNo }}</strong>
                  <span>{{ basis.contentSummary || '点击查看已核验条文详情' }}</span>
                  <small>{{ basis.sourceName || '官方来源' }} · 版本 {{ basis.version || '当前有效版本' }}</small>
                </button>
              </div>
              <el-alert v-else title="未匹配到已核验法律依据" description="系统不会根据模型猜测生成法律名称、条号或条文内容，建议由法务人工补充核验。" type="warning" :closable="false" show-icon />
            </section>
          </section>
        </section>
      </section>
    </main>
  </div>

  <el-dialog v-model="reportDialog" title="合同智能审查报告" width="780px" append-to-body>
    <div v-if="result" class="report-preview">
      <header><div><small>审查编号</small><strong>{{ result.review_id }}</strong></div><RiskLevelTag :level="result.final_report?.总体风险等级?.replace('风险', '') || '中'" /></header>
      <el-descriptions :column="2" border><el-descriptions-item label="合同文件">{{ result.file_name }}</el-descriptions-item><el-descriptions-item label="风险评分">{{ result.final_report?.风险评分?.风险分 ?? '暂无' }} / 100</el-descriptions-item><el-descriptions-item label="风险总数">{{ result.risk_findings.length }} 项</el-descriptions-item><el-descriptions-item label="高风险">{{ severeRiskCount }} 项</el-descriptions-item></el-descriptions>
      <section><h3>审查摘要</h3><p>{{ result.final_report?.审查摘要 }}</p></section>
      <section><h3>重点风险与修改建议</h3><ol><li v-for="risk in result.risk_findings" :key="risk.风险编号"><strong>{{ risk.风险标题 }}</strong><span>{{ activeSuggestion?.对应风险编号 === risk.风险编号 ? activeSuggestion?.修改建议 : result.revision_suggestions?.find((item:any) => item.对应风险编号 === risk.风险编号)?.修改建议 || risk.修改方向 }}</span><small>{{ (risk.legalBasis || risk.legal_basis || []).length ? (risk.legalBasis || risk.legal_basis).map((item:any) => `《${item.lawName}》${item.articleNo}`).join('；') : '未匹配到已核验法律依据' }}</small></li></ol></section>
      <el-alert title="AI 审查结果用于辅助决策，重要合同应由专业法务结合交易背景复核。" type="info" :closable="false" show-icon />
    </div>
    <template #footer><el-button @click="reportDialog = false">关闭</el-button><el-button :icon="Download" @click="downloadReport('docx')">下载 Word</el-button><el-button type="primary" :icon="Download" @click="downloadReport('pdf')">下载 PDF</el-button></template>
  </el-dialog>

  <el-drawer v-model="legalDrawer" title="已核验法律条文" size="560px" append-to-body>
    <template v-if="legalDetail">
      <div class="legal-detail-tags"><el-tag type="success">已核验</el-tag><el-tag>{{ legalDetail.law_version }}</el-tag><el-tag>{{ legalDetail.effect_status === 'effective' ? '有效' : legalDetail.effect_status }}</el-tag></div>
      <h2>《{{ legalDetail.law_name }}》{{ legalDetail.article_no }}</h2>
      <h3 v-if="legalDetail.title">{{ legalDetail.title }}</h3>
      <p class="legal-detail-content">{{ legalDetail.content }}</p>
      <el-descriptions :column="1" border>
        <el-descriptions-item label="法律主题">{{ legalDetail.legal_topics.join('、') || '未设置' }}</el-descriptions-item>
        <el-descriptions-item label="来源名称">{{ legalDetail.source_name }}</el-descriptions-item>
        <el-descriptions-item label="更新时间">{{ legalDetail.updated_at }}</el-descriptions-item>
        <el-descriptions-item label="官方来源"><a v-if="legalDetail.source_url" :href="legalDetail.source_url" target="_blank" rel="noopener noreferrer">打开官方来源</a><span v-else>未提供</span></el-descriptions-item>
      </el-descriptions>
    </template>
  </el-drawer>

  <Teleport to="body">
    <Transition name="ritual-fade">
      <section v-if="loading" class="review-ritual" aria-live="polite" aria-busy="true">
        <div class="ritual-content">
          <span class="ritual-brand"><el-icon><Document /></el-icon></span>
          <span class="ritual-code">CONTRACT REVIEW</span>
          <h2>合同审查进行中</h2>
          <p>正在安全执行文档解析、规则检查和 AI 辅助审查</p>
          <ol class="ritual-steps">
            <li v-for="(step, index) in analysisSteps" :key="step" :class="{ done: index < analysisStepIndex, active: index === analysisStepIndex }"><i></i><span>{{ step }}</span></li>
          </ol>
          <div class="ritual-progress"><span></span></div>
          <div class="ritual-timing"><strong>处理中</strong><span>已等待 {{ elapsedSeconds }} 秒，请勿关闭当前页面</span></div>
          <small>步骤用于说明审查流程，最终状态以服务端返回结果为准。</small>
        </div>
      </section>
    </Transition>
  </Teleport>
</template>

<style scoped>
.review-page {
  --review-primary: #2563eb;
  --review-primary-hover: #1d4ed8;
  --review-text: #172033;
  --review-muted: #64748b;
  --review-border: #e5eaf2;
  --review-bg: #f5f7fb;
  --review-danger: #dc2626;
  --review-warning: #f59e0b;
  --review-success: #16a34a;
  --review-radius: 12px;
  --review-shadow: 0 4px 16px rgba(23, 32, 51, 0.05);
  max-width: 1440px;
  min-width: 0;
  min-height: calc(100vh - 150px);
  margin: 0 auto;
  color: var(--review-text);
  background: transparent;
  box-shadow: none;
  font-family: Inter, "PingFang SC", "Microsoft YaHei", sans-serif;
}

.review-page-head {
  min-height: 76px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 24px;
  padding: 0 4px;
  border-bottom: 1px solid var(--review-border);
}

.review-page-head h1,
.module-heading h2,
.result-toolbar h2,
.empty-result h2 { margin: 0; color: var(--review-text); }
.review-page-head h1 { font-size: 26px; line-height: 34px; font-weight: 700; letter-spacing: -0.02em; }
.review-page-head p { margin: 4px 0 0; color: var(--review-muted); font-size: 13px; line-height: 20px; }

.ai-service-status {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 190px;
  padding: 8px 12px;
  border: 1px solid var(--review-border);
  border-radius: 10px;
  background: #fff;
}
.ai-status-icon { display: grid; place-items: center; width: 34px; height: 34px; border-radius: 50%; color: var(--review-primary); background: #eff6ff; font-size: 18px; }
.ai-service-status > span:nth-child(2) { display: flex; flex: 1; flex-direction: column; }
.ai-service-status b { color: var(--review-text); font-size: 13px; line-height: 18px; }
.ai-service-status small { color: var(--review-muted); font-size: 11px; line-height: 16px; }
.ai-service-status > i { width: 8px; height: 8px; border-radius: 50%; background: var(--review-success); box-shadow: 0 0 0 3px #dcfce7; }

.review-content { padding: 24px 0 32px; }
.review-setup { display: grid; grid-template-columns: minmax(0, 1fr) 320px; gap: 24px; align-items: stretch; }
.setup-card,
.result-summary,
.empty-result,
.results { background: #fff; border: 1px solid var(--review-border); border-radius: var(--review-radius); box-shadow: var(--review-shadow); }
.setup-card { min-width: 0; padding: 24px; }
.module-heading { display: flex; align-items: flex-start; justify-content: space-between; margin-bottom: 16px; }
.module-heading h2,
.result-toolbar h2 { font-size: 18px; line-height: 26px; font-weight: 700; }
.module-heading p,
.result-toolbar p { margin: 2px 0 0; color: var(--review-muted); font-size: 12px; line-height: 18px; }

.contract-uploader { display: block; min-width: 0; }
.contract-uploader :deep(.el-upload) { display: block; width: 100%; }
.contract-uploader :deep(.el-upload-dragger) {
  width: 100%; height: 150px; padding: 0; overflow: hidden;
  display: flex; align-items: center; justify-content: center;
  border: 1px dashed #bfdbfe; border-radius: 10px; background: #f8fbff;
  transition: border-color 0.2s ease, background 0.2s ease, box-shadow 0.2s ease;
}
.contract-uploader :deep(.el-upload-dragger:hover),
.contract-uploader :deep(.el-upload-dragger.is-dragover) { border-color: var(--review-primary); background: #eff6ff; box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.08); }
.upload-placeholder { display: flex; align-items: center; justify-content: center; gap: 16px; padding: 24px; text-align: left; }
.upload-icon-wrap { display: grid; flex: 0 0 auto; place-items: center; width: 52px; height: 52px; border-radius: 50%; color: var(--review-primary); background: #dbeafe; font-size: 25px; }
.upload-placeholder > div { display: flex; flex-direction: column; gap: 6px; }
.upload-placeholder strong { color: var(--review-text); font-size: 14px; line-height: 22px; }
.upload-placeholder small { color: var(--review-muted); font-size: 12px; line-height: 18px; }

.selected-file { width: 100%; min-width: 0; display: flex; align-items: center; gap: 14px; padding: 24px; text-align: left; cursor: default; }
.file-icon { display: grid; flex: 0 0 auto; place-items: center; width: 48px; height: 48px; border-radius: 10px; color: var(--review-primary); background: #eff6ff; font-size: 24px; }
.file-meta { min-width: 0; flex: 1; display: flex; flex-direction: column; gap: 5px; }
.file-meta strong { overflow: hidden; color: var(--review-text); font-size: 14px; line-height: 20px; text-overflow: ellipsis; white-space: nowrap; }
.file-meta span { color: var(--review-muted); font-size: 12px; line-height: 18px; }
.upload-success { display: inline-flex; align-items: center; gap: 6px; color: var(--review-success); font-size: 12px; white-space: nowrap; }
.upload-success i { width: 7px; height: 7px; border-radius: 50%; background: currentColor; }
.file-actions { display: flex; align-items: center; gap: 4px; }
.file-actions :deep(.el-button) { margin: 0; color: var(--review-primary); }
.file-actions :deep(.delete-file) { color: var(--review-danger); }

.review-options { display: flex; flex-direction: column; }
.review-options label { margin-bottom: 8px; color: var(--review-text); font-size: 13px; line-height: 20px; font-weight: 600; }
.review-options :deep(.el-select) { width: 100%; }
.review-options :deep(.el-select__wrapper) { min-height: 44px; border-radius: 8px; box-shadow: 0 0 0 1px var(--review-border) inset; }
.review-options :deep(.el-select__wrapper.is-focused) { box-shadow: 0 0 0 1px var(--review-primary) inset; }
.capability-tags { display: flex; flex-wrap: wrap; gap: 8px; margin: 16px 0 20px; }
.capability-tags span { padding: 5px 9px; border: 1px solid #dbeafe; border-radius: 6px; color: #1e40af; background: #eff6ff; font-size: 12px; line-height: 18px; }
.start-review { width: 100%; height: 46px; margin-top: auto; border: 0; border-radius: 8px; background: var(--review-primary); font-size: 14px; font-weight: 600; box-shadow: none; }
.start-review:hover,
.start-review:focus { background: var(--review-primary-hover); }
.start-review:active { transform: translateY(1px); background: #1e40af; }
.start-review.is-disabled { background: #93b4f3; }
.duration-hint { margin: 8px 0 0; color: var(--review-muted); font-size: 12px; line-height: 18px; text-align: center; }

.result-area { margin-top: 24px; }
.result-summary { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 16px; padding: 16px; }
.metric-card { position: relative; min-width: 0; padding: 18px 20px; overflow: hidden; border: 1px solid var(--review-border); border-radius: 10px; background: #fafcff; }
.metric-card::before { content: ""; position: absolute; inset: 0 auto 0 0; width: 3px; background: var(--review-primary); }
.metric-card > span { display: block; margin-bottom: 8px; color: var(--review-muted); font-size: 12px; line-height: 18px; }
.metric-card strong { display: flex; align-items: baseline; gap: 4px; color: var(--review-text); font-size: 28px; line-height: 34px; font-weight: 700; }
.metric-card strong small { color: var(--review-muted); font-size: 14px; line-height: 20px; font-weight: 500; }
.severe-card::before { background: var(--review-danger); }
.risk-level-card strong { font-size: 18px; }
.risk-level-card strong em { padding: 4px 9px; border-radius: 6px; font-size: 16px; line-height: 24px; font-style: normal; }
.risk-level-card.is-high::before { background: var(--review-danger); }
.risk-level-card.is-high strong em { color: var(--review-danger); background: #fef2f2; }
.risk-level-card.is-medium::before { background: var(--review-warning); }
.risk-level-card.is-medium strong em { color: #b45309; background: #fffbeb; }
.risk-level-card.is-low::before { background: var(--review-success); }
.risk-level-card.is-low strong em { color: var(--review-success); background: #f0fdf4; }
.score-card::before { background: var(--review-warning); }

.empty-result { min-height: 280px; display: flex; flex-direction: column; align-items: center; justify-content: center; margin-top: 16px; padding: 40px 24px; text-align: center; }
.empty-result-icon { display: grid; place-items: center; width: 56px; height: 56px; margin-bottom: 16px; border-radius: 50%; color: var(--review-primary); background: #eff6ff; font-size: 25px; }
.empty-result h2 { font-size: 18px; line-height: 26px; font-weight: 700; }
.empty-result p { max-width: 520px; margin: 8px 0 0; color: var(--review-muted); font-size: 14px; line-height: 22px; }

.results { margin-top: 16px; overflow: hidden; }
.result-toolbar { display: flex; align-items: center; justify-content: space-between; gap: 16px; padding: 20px 24px; border-bottom: 1px solid var(--review-border); }
.result-toolbar :deep(.el-button) { height: 38px; border-color: var(--review-border); border-radius: 8px; color: var(--review-primary); }
.review-result-workbench { height: min(680px, calc(100vh - 160px)); min-height: 560px; display: grid; grid-template-columns: minmax(320px, 38%) minmax(0, 1fr); margin-top: 0; overflow: hidden; }
.risk-pane { min-width: 0; border-right: 1px solid var(--review-border); background: #fbfcfe; }
.risk-pane > header,
.contract-pane > header { min-height: 66px; display: flex; align-items: center; justify-content: space-between; gap: 16px; padding: 14px 20px; border-bottom: 1px solid var(--review-border); background: #fff; }
.risk-pane header h2,
.contract-pane header h2 { margin: 0; color: var(--review-text); font-size: 16px; line-height: 24px; }
.risk-pane header span,
.contract-pane header span { display: block; margin-top: 2px; overflow: hidden; color: var(--review-muted); font-size: 12px; line-height: 18px; text-overflow: ellipsis; white-space: nowrap; }
.risk-pane header b { display: grid; place-items: center; min-width: 30px; height: 30px; padding: 0 8px; border-radius: 15px; color: var(--review-primary); background: #eff6ff; font-size: 13px; }
.risk-pane-list { max-height: 640px; padding: 12px; overflow-y: auto; }
.linked-risk { width: 100%; margin: 0 0 10px; padding: 16px; border: 1px solid var(--review-border); border-radius: 10px; color: var(--review-text); background: #fff; text-align: left; cursor: pointer; transition: border-color 0.2s ease, box-shadow 0.2s ease, background 0.2s ease; }
.linked-risk:hover,
.linked-risk:focus-visible,
.linked-risk.active { outline: 0; border-color: #93c5fd; background: #f8fbff; box-shadow: 0 2px 10px rgba(37, 99, 235, 0.08); }
.linked-risk-title { display: flex; align-items: center; gap: 8px; }
.linked-risk-title strong { min-width: 0; flex: 1; overflow: hidden; font-size: 14px; text-overflow: ellipsis; white-space: nowrap; }
.linked-risk-title small { color: var(--review-muted); font-size: 11px; }
.linked-risk > p { margin: 10px 0 5px; color: var(--review-text); font-size: 14px; line-height: 21px; font-weight: 600; }
.linked-risk > span { display: -webkit-box; overflow: hidden; color: var(--review-muted); font-size: 12px; line-height: 19px; -webkit-box-orient: vertical; -webkit-line-clamp: 2; }
.location-state { margin-top: 10px; color: var(--review-primary); font-size: 12px; line-height: 18px; }
.location-state.missing { color: var(--review-warning); }
.active-risk-advice { display: grid; gap: 4px; margin-top: 12px; padding: 10px 12px; border-left: 3px solid var(--review-primary); border-radius: 0 6px 6px 0; background: #eff6ff; }
.active-risk-advice b { color: var(--review-text); font-size: 12px; }
.active-risk-advice span { color: var(--review-muted); font-size: 12px; line-height: 19px; }
.contract-pane { min-width: 0; background: #fff; }
.contract-pane > header > div { min-width: 0; }
.contract-document { max-height: 640px; padding: 24px; overflow: auto; background: #f8fafc; }
.contract-document pre { min-height: 520px; margin: 0; padding: 28px 32px; border: 1px solid var(--review-border); border-radius: 8px; color: var(--review-text); background: #fff; font-family: "PingFang SC", "Microsoft YaHei", sans-serif; font-size: 14px; line-height: 2; white-space: pre-wrap; word-break: break-word; box-shadow: 0 2px 8px rgba(23, 32, 51, 0.04); }
.contract-document mark { padding: 2px 0; color: inherit; background: #fef3c7; box-shadow: 0 0 0 2px #fef3c7; }

.review-ritual {
  --review-primary: #2563eb;
  --review-text: #172033;
  --review-muted: #64748b;
  --review-border: #e5eaf2;
  --review-radius: 12px;
  position: fixed; z-index: 3000; inset: 0; display: grid; place-items: center; padding: 32px; overflow: hidden; background: #f5f7fb !important;
}
.ritual-content {
  position: relative !important;
  z-index: 1;
  inset: auto !important;
  left: auto !important;
  top: auto !important;
  width: min(760px, 100%);
  padding: 0;
  transform: none !important;
  border: 0;
  color: var(--review-text);
  background: transparent;
  box-shadow: none;
  text-align: center;
}
.ritual-code { display: inline-flex; align-items: center; gap: 10px; color: var(--review-primary); font: 700 11px/18px Inter, sans-serif; letter-spacing: 0.18em; }
.ritual-code::before,
.ritual-code::after { content: ""; width: 34px; height: 1px; background: #93c5fd; }
.ritual-content h2 { margin: 22px 0 8px; color: var(--review-text); font-size: clamp(28px, 4vw, 42px); line-height: 1.25; font-weight: 600; letter-spacing: 0.22em; }
.ritual-content > p { margin: 0; color: var(--review-muted); font-size: 14px; line-height: 22px; letter-spacing: 0.16em; }
.ritual-timing { display: flex; align-items: center; flex-direction: column; justify-content: center; gap: 8px; margin: 34px auto 28px; padding: 0; background: transparent; text-align: center; }
.ritual-timing strong { display: grid; place-items: center; min-width: 104px; height: 38px; padding: 0 18px; border: 1px solid #bfdbfe; border-radius: 19px; color: var(--review-primary); background: #eff6ff; font-size: 14px; font-weight: 700; letter-spacing: 0.12em; }
.ritual-timing span { color: var(--review-muted); font-size: 12px; line-height: 20px; text-align: center; }
.ritual-agents { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 0; border-top: 1px solid var(--review-border); border-bottom: 1px solid var(--review-border); }
.ritual-agents > div { min-width: 0; display: flex; align-items: center; justify-content: center; gap: 8px; padding: 16px 10px; color: #94a3b8; background: transparent; font-size: 12px; }
.ritual-agents > div + div { border-left: 1px solid var(--review-border); }
.ritual-agents > div.active { color: var(--review-text); background: rgba(219, 234, 254, 0.52); }
.ritual-agents i { display: grid; flex: 0 0 auto; place-items: center; width: 24px; height: 24px; border-radius: 50%; color: #94a3b8; background: #eef2f7; font-size: 9px; font-style: normal; }
.ritual-agents > div.active i { color: #fff; background: var(--review-primary); }
.ritual-progress { position: relative; height: 3px; margin-top: 28px; overflow: hidden; background: #dbe3ef; }
.ritual-progress::before,
.ritual-progress::after { content: ""; position: absolute; top: -3px; width: 1px; height: 9px; background: #94a3b8; }
.ritual-progress::before { left: 0; }
.ritual-progress::after { right: 0; }
.ritual-progress span { position: absolute; top: 0; left: 0; display: block; width: 32%; height: 100%; background: var(--review-primary); animation: review-loading-scan 1.45s cubic-bezier(0.4, 0, 0.2, 1) infinite; }
.ritual-progress.complete span { width: 100%; animation: none; }
.ritual-fade-enter-active,
.ritual-fade-leave-active { transition: opacity 0.2s ease; }
.ritual-fade-enter-from,
.ritual-fade-leave-to { opacity: 0; }

@keyframes review-loading-scan {
  from { transform: translateX(-105%); }
  to { transform: translateX(315%); }
}

@media (prefers-reduced-motion: reduce) {
  .ritual-progress span { animation: none; }
  .ritual-progress span { left: 34%; }
  .ritual-progress.complete span { left: 0; }
}

@media (max-width: 1024px) {
  .review-setup { grid-template-columns: minmax(0, 1fr) 300px; gap: 20px; }
  .result-summary { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .review-result-workbench { grid-template-columns: minmax(280px, 42%) minmax(0, 1fr); }
}

@media (max-width: 820px) {
  .review-page-head { min-height: auto; padding: 12px 0 16px; }
  .ai-service-status { min-width: auto; }
  .ai-service-status small { display: none; }
  .review-setup { grid-template-columns: 1fr; }
  .review-result-workbench { height: auto; min-height: 0; grid-template-columns: 1fr; }
  .risk-pane { border-right: 0; border-bottom: 1px solid var(--review-border); }
  .risk-pane-list { max-height: 420px; }
}

@media (max-width: 600px) {
  .review-page-head { align-items: flex-start; }
  .review-page-head h1 { font-size: 22px; line-height: 30px; }
  .ai-service-status { padding: 7px; }
  .ai-service-status > span:nth-child(2) { display: none; }
  .setup-card { padding: 16px; }
  .upload-placeholder { flex-direction: column; text-align: center; }
  .selected-file { flex-wrap: wrap; padding: 16px; }
  .file-meta { flex-basis: calc(100% - 66px); }
  .upload-success { margin-left: 62px; }
  .file-actions { margin-left: auto; }
  .result-summary { grid-template-columns: 1fr; }
  .result-toolbar { align-items: flex-start; padding: 16px; }
  .contract-document { padding: 12px; }
  .contract-document pre { padding: 20px; }
  .ritual-content { padding: 20px; }
  .ritual-content h2 { letter-spacing: 0.12em; }
  .ritual-agents { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .ritual-agents > div:nth-child(3) { border-left: 0; border-top: 1px solid var(--review-border); }
  .ritual-agents > div:nth-child(4) { border-top: 1px solid var(--review-border); }
}
</style>

<style scoped>
.review-page {
  max-width: none;
  min-height: calc(100vh - 160px);
  background: transparent;
  box-shadow: none;
  clip-path: none;
}

.review-content { padding: 0 0 24px; }

.review-fallback { display: flex; align-items: center; justify-content: space-between; gap: 18px; margin: 18px 0 0; padding: 16px 18px; border: 1px solid #f2c8c8; border-radius: 14px; background: #fff7f7; }
.review-fallback strong { color: #a72e2e; font-size: 14px; }
.review-fallback p { margin: 4px 0 0; color: var(--review-muted); font-size: 12px; line-height: 1.6; }
.review-fallback > div:last-child, .result-actions { display: flex; flex-wrap: wrap; gap: 8px; }
.review-content > :deep(.el-alert) { margin-top: 16px; }

.result-summary {
  gap: 16px;
  padding: 0;
  border: 0;
  background: transparent;
  box-shadow: none;
}

.risk-detail-card { padding: 22px 24px 26px; border-top: 1px solid var(--review-border); background: #fff; }
.risk-detail-card > header { display: flex; align-items: center; justify-content: space-between; gap: 14px; margin-bottom: 16px; }
.risk-detail-card > header div { display: flex; align-items: center; gap: 10px; }
.risk-detail-card h3 { margin: 0; font-size: 17px; }
.risk-detail-card > header small { color: var(--review-muted); }
.risk-detail-grid { display: grid; grid-template-columns: repeat(2, minmax(0,1fr)); gap: 12px; }
.risk-detail-grid article { padding: 14px 16px; border: 1px solid var(--review-border); border-radius: 12px; background: #fafcff; }
.risk-detail-grid article > span { color: #53708d; font-size: 11px; font-weight: 700; letter-spacing: .04em; }
.risk-detail-grid article p { margin: 7px 0 0; color: var(--review-text); font-size: 13px; line-height: 1.75; }
.risk-detail-grid .recommended-clause { grid-column: 1 / -1; border-color: #cfe0ee; background: #f2f7fb; }

.report-preview { display: grid; gap: 18px; }
.report-preview > header { display: flex; align-items: center; justify-content: space-between; gap: 16px; }
.report-preview > header div { display: flex; flex-direction: column; }
.report-preview > header small { color: var(--review-muted); }
.report-preview > section { padding: 16px 18px; border: 1px solid var(--review-border); border-radius: 12px; }
.report-preview h3 { margin: 0 0 8px; font-size: 15px; }
.report-preview p { margin: 0; color: var(--review-muted); line-height: 1.75; }
.report-preview ol { display: grid; gap: 10px; margin: 0; padding-left: 20px; }
.report-preview li { padding-left: 3px; }
.report-preview li strong, .report-preview li span { display: block; }
.report-preview li span { margin-top: 3px; color: var(--review-muted); font-size: 12px; line-height: 1.6; }

.review-ritual { background: rgba(245, 247, 251, 0.96) !important; }

.ritual-content {
  width: min(560px, 100%);
  padding: 36px 40px;
  border: 1px solid var(--review-border);
  border-radius: 16px;
  background: #fff;
  box-shadow: 0 18px 50px rgba(23, 32, 51, 0.12);
}

.ritual-brand {
  width: 52px;
  height: 52px;
  display: grid;
  place-items: center;
  margin: 0 auto 16px;
  border-radius: 14px;
  color: #fff;
  background: var(--review-primary);
  font-size: 24px;
}

.ritual-code::before,
.ritual-code::after { display: none; }

.ritual-content h2 {
  margin: 12px 0 8px;
  font-size: 28px;
  letter-spacing: 0.04em;
}

.ritual-content > p { letter-spacing: 0; }

.ritual-steps { display: grid; grid-template-columns: repeat(5, minmax(0,1fr)); gap: 8px; margin: 24px 0 0; padding: 0; list-style: none; }
.ritual-steps li { display: grid; justify-items: center; gap: 7px; color: #9aaabd; font-size: 10px; }
.ritual-steps i { width: 10px; height: 10px; border: 2px solid #c9d5e1; border-radius: 50%; background: #fff; }
.ritual-steps li.done, .ritual-steps li.active { color: #315f92; }
.ritual-steps li.done i { border-color: #5e8ab5; background: #5e8ab5; }
.ritual-steps li.active i { border-color: #315f92; box-shadow: 0 0 0 5px rgba(49,95,146,.1); }

.ritual-progress {
  width: 100%;
  height: 4px;
  margin: 28px 0 18px;
  border-radius: 2px;
}

.ritual-timing {
  flex-direction: row;
  gap: 12px;
  margin: 0;
}

.ritual-timing strong {
  min-width: 72px;
  height: 30px;
  padding: 0 12px;
  border-radius: 15px;
  letter-spacing: 0;
}

.ritual-content > small {
  display: block;
  margin-top: 18px;
  color: var(--review-muted);
  font-size: 11px;
}

.legal-basis-block { margin-top: 18px; padding-top: 18px; border-top: 1px solid var(--review-border); }
.legal-basis-block > div:first-child { display: flex; justify-content: space-between; gap: 12px; margin-bottom: 12px; }
.legal-basis-block > div:first-child span { font-weight: 700; color: var(--review-text); }
.legal-basis-block > div:first-child small { color: var(--review-muted); }
.legal-basis-list { display: grid; gap: 10px; }
.legal-basis-list button { display: grid; gap: 6px; width: 100%; padding: 14px 16px; border: 1px solid #dce8e3; border-radius: 12px; background: #f8fcfa; color: #29483f; text-align: left; cursor: pointer; }
.legal-basis-list button:hover { border-color: #5a8a7d; background: #f0f8f5; }
.legal-basis-list span { line-height: 1.6; color: #526a63; }
.legal-basis-list small { color: #789088; }
.legal-detail-tags { display: flex; gap: 8px; margin-bottom: 16px; }
.legal-detail-content { padding: 18px; border-radius: 12px; background: #f7faf9; white-space: pre-wrap; line-height: 1.9; color: #2f4841; }
.report-preview ol li small { display: block; margin-top: 6px; color: #6b827b; }

@media (max-width: 600px) {
  .ritual-content { padding: 28px 20px; }
  .ritual-timing { align-items: center; flex-direction: column; }
  .review-fallback { align-items: flex-start; flex-direction: column; }
  .risk-detail-grid { grid-template-columns: 1fr; }
  .risk-detail-grid .recommended-clause { grid-column: auto; }
  .result-actions { justify-content: flex-start; }
  .ritual-steps { grid-template-columns: 1fr; }
  .ritual-steps li { grid-template-columns: auto 1fr; justify-items: start; text-align: left; }
}
</style>
