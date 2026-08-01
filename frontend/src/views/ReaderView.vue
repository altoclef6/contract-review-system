<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { ElMessageBox } from 'element-plus'
import { ArrowLeft, ArrowRight, CopyDocument, Download, Minus, Plus, RefreshRight, Search } from '@element-plus/icons-vue'
import EmptyState from '../components/EmptyState.vue'
import ErrorState from '../components/ErrorState.vue'
import LoadingState from '../components/LoadingState.vue'
import RiskLevelTag from '../components/RiskLevelTag.vue'
import StatusTag from '../components/StatusTag.vue'
import { startContractReview } from '../services/contracts'
import { useAuthStore } from '../stores/auth'
import { addRiskComment, saveRiskRevision, transitionRisk, updateRiskHumanReview, type RiskRecord } from '../services/risks'
import {
  downloadReaderReport,
  fetchReaderWorkspace,
  locatePdfText,
  type ReaderRisk,
  type ReaderWorkspace,
} from '../services/reader'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const reviewId = computed(() => String(route.params.reviewId))
const workspace = ref<ReaderWorkspace | null>(null)
const loading = ref(false)
const error = ref('')
const selectedRiskId = ref('')
const severityFilter = ref('all')
const searchQuery = ref('')
const fontScale = ref(1)
const rerunning = ref(false)
const riskSaving = ref(false)
const pdfLocation = ref<{ page: number; box: number[] } | null>(null)
let controller: AbortController | null = null
let locationController: AbortController | null = null

const categoryLabels: Record<string, string> = {
  software_development: '软件开发合同', technical_service: '技术服务合同', information_system: '信息系统建设合同',
  software_outsourcing: '软件外包合同', procurement: '采购合同', sales: '销售合同', service: '服务合同', general: '通用合同', other: '其他',
}
const sourceTypeLabels: Record<string, string> = { law: '法律', regulation: '行政法规', judicial_interpretation: '司法解释', enterprise_policy: '企业制度', contract_template: '合同模板', review_guideline: '审查指南' }
const statusLabels: Record<string, string> = { effective: '现行有效', amended: '已修订', expired: '已失效', repealed: '已废止' }
const riskStatusLabels: Record<string, string> = { pending_review: 'AI 发现·待确认', confirmed: '已确认', rejected: '已驳回', ignored: '已忽略', false_positive: '误报', modified: '已修改', remediating: '整改中', remediated: '已整改', closed: '已关闭' }

const risks = computed(() => workspace.value?.risks || [])
const filteredRisks = computed(() => risks.value.filter((risk) => {
  if (severityFilter.value === 'all') return true
  if (severityFilter.value === 'high') return ['高', '严重', 'high', 'critical'].includes(risk.severity)
  return [severityFilter.value, ({ medium: '中', low: '低' } as Record<string, string>)[severityFilter.value]].includes(risk.severity)
}))
const selectedRisk = computed(() => risks.value.find((item) => item.risk_id === selectedRiskId.value) || null)
const selectedIndex = computed(() => filteredRisks.value.findIndex((item) => item.risk_id === selectedRiskId.value))
const isReviewer = computed(() => ['admin', 'legal'].includes(auth.user?.role || ''))
const reviewActions = computed(() => {
  if (!selectedRisk.value?.persisted) return []
  const status = selectedRisk.value?.status
  if (status === 'pending_review' && isReviewer.value) return [
    { key: 'confirm', label: '确认' },
    { key: 'ignore', label: '忽略' },
    { key: 'false-positive', label: '标记误报' },
  ]
  if (status === 'confirmed') return [{ key: 'start-remediation', label: '开始整改' }]
  if (status === 'remediating') return [{ key: 'mark-remediated', label: '标记已整改' }]
  return []
})

interface TextSegment { text: string; current: boolean; search: boolean }
interface TextParagraph { id: string; start: number; end: number; segments: TextSegment[] }

const paragraphs = computed<TextParagraph[]>(() => {
  const text = workspace.value?.contract_text || ''
  if (!text) return []
  const result: TextParagraph[] = []
  let start = 0
  const lines = text.split('\n')
  for (let index = 0; index < lines.length; index += 1) {
    const line = lines[index]
    const end = start + line.length
    const boundaries = new Set<number>([start, end])
    const currentStart = selectedRisk.value?.location.start_offset
    const currentEnd = selectedRisk.value?.location.end_offset
    if (currentStart !== null && currentStart !== undefined && currentEnd !== null && currentEnd !== undefined && currentStart < end && currentEnd > start) {
      boundaries.add(Math.max(start, currentStart)); boundaries.add(Math.min(end, currentEnd))
    }
    const query = searchQuery.value.trim()
    if (query) {
      let local = line.indexOf(query)
      while (local >= 0) { boundaries.add(start + local); boundaries.add(start + local + query.length); local = line.indexOf(query, local + Math.max(1, query.length)) }
    }
    const points = [...boundaries].sort((a, b) => a - b)
    const segments = points.slice(0, -1).map((left, segmentIndex) => {
      const right = points[segmentIndex + 1]
      const current = currentStart !== null && currentStart !== undefined && currentEnd !== null && currentEnd !== undefined && left < currentEnd && right > currentStart
      return { text: text.slice(left, right), current, search: Boolean(query && text.slice(left, right).includes(query)) }
    })
    result.push({ id: `paragraph-${index}`, start, end, segments })
    start = end + 1
  }
  return result
})

async function load() {
  controller?.abort()
  controller = new AbortController()
  loading.value = true
  error.value = ''
  try {
    workspace.value = await fetchReaderWorkspace(reviewId.value, controller.signal)
    selectedRiskId.value = workspace.value.risks[0]?.risk_id || ''
  } catch (cause: any) {
    if (cause?.code !== 'ERR_CANCELED') error.value = cause?.response?.data?.message || cause?.response?.data?.detail || '审查工作区加载失败'
  } finally { loading.value = false }
}

async function selectRisk(risk: ReaderRisk) {
  selectedRiskId.value = risk.risk_id
  pdfLocation.value = null
  await nextTick()
  jumpToOffset(risk.location.start_offset)
  if (!workspace.value?.summary.source_is_pdf || risk.clause_text.length < 2 || risk.clause_text.startsWith('未在合同文本中')) return
  locationController?.abort()
  locationController = new AbortController()
  try {
    const locations = await locatePdfText(reviewId.value, risk.clause_text, locationController.signal)
    const first = locations[0]
    if (first) pdfLocation.value = { page: first.page, box: [first.x0, first.y0, first.x1, first.y1] }
  } catch (cause: any) {
    if (cause?.code !== 'ERR_CANCELED') pdfLocation.value = null
  }
}

function jumpToOffset(offset?: number | null) {
  if (offset === null || offset === undefined) return ElMessage.info('该风险暂无可用文本位置')
  const paragraph = paragraphs.value.find((item) => item.start <= offset && offset <= item.end)
  document.getElementById(paragraph?.id || '')?.scrollIntoView({ behavior: 'smooth', block: 'center' })
}

function move(direction: number) {
  if (!filteredRisks.value.length) return
  const current = selectedIndex.value < 0 ? 0 : selectedIndex.value
  const next = Math.min(Math.max(current + direction, 0), filteredRisks.value.length - 1)
  void selectRisk(filteredRisks.value[next])
}

function chapterClick(start: number, end: number) {
  const firstRisk = filteredRisks.value.find((risk) => risk.location.start_offset !== null && risk.location.start_offset !== undefined && risk.location.start_offset >= start && risk.location.start_offset < end)
  if (firstRisk) void selectRisk(firstRisk)
  else jumpToOffset(start)
}

async function copySuggestion() {
  const value = selectedRisk.value?.suggested_revision || selectedRisk.value?.recommendation
  if (!value) return ElMessage.info('当前风险没有可复制的修改建议')
  await navigator.clipboard.writeText(value)
  ElMessage.success('修改建议已复制')
}

function asRiskRecord(item: ReaderRisk): RiskRecord {
  return item as unknown as RiskRecord
}

function replaceSelected(updated: RiskRecord) {
  if (!workspace.value) return
  const index = workspace.value.risks.findIndex((item) => item.risk_id === updated.risk_id)
  if (index < 0) return
  workspace.value.risks[index] = {
    ...workspace.value.risks[index], status: updated.status, revision: updated.revision,
    severity: updated.severity,
    assignee_id: updated.assignee_id, reviewer_id: updated.reviewer_id,
    review_comment: updated.review_comment, revised_clause: updated.revised_clause,
  }
}

async function runRiskAction(action: string, label: string) {
  if (!selectedRisk.value) return
  try {
    const prompt = await ElMessageBox.prompt(`请输入“${label}”的复核说明（可留空）`, label, { inputType: 'textarea' })
    riskSaving.value = true
    const updated = await transitionRisk(asRiskRecord(selectedRisk.value), action as any, prompt.value)
    replaceSelected(updated); ElMessage.success(`${label}成功`)
  } catch (cause: any) {
    if (cause !== 'cancel' && cause !== 'close') ElMessage.error(cause?.response?.data?.detail || `${label}失败`)
  } finally { riskSaving.value = false }
}

async function saveManualRevision() {
  if (!selectedRisk.value) return
  try {
    const prompt = await ElMessageBox.prompt('输入人工确认后的修改条款', '保存人工修改', { inputType: 'textarea', inputValue: selectedRisk.value.revised_clause || selectedRisk.value.suggested_revision || '' })
    if (!prompt.value.trim()) return ElMessage.warning('人工修改条款不能为空')
    riskSaving.value = true
    replaceSelected(await saveRiskRevision(asRiskRecord(selectedRisk.value), prompt.value))
    ElMessage.success('人工修改条款已保存')
  } catch (cause: any) { if (cause !== 'cancel' && cause !== 'close') ElMessage.error(cause?.response?.data?.detail || '保存失败') }
  finally { riskSaving.value = false }
}

async function editHumanReview() {
  if (!selectedRisk.value) return
  try {
    const levelPrompt = await ElMessageBox.prompt(
      '输入统一风险等级：HIGH、MEDIUM 或 LOW',
      '修改风险等级',
      { inputValue: String(selectedRisk.value.severity || '').toUpperCase(), inputPattern: /^(HIGH|MEDIUM|LOW)$/, inputErrorMessage: '请输入 HIGH、MEDIUM 或 LOW' },
    )
    const opinionPrompt = await ElMessageBox.prompt('输入人工审查意见', '修改审查意见', { inputType: 'textarea', inputValue: selectedRisk.value.review_comment || selectedRisk.value.explanation || '' })
    if (!opinionPrompt.value.trim()) return
    riskSaving.value = true
    replaceSelected(await updateRiskHumanReview(asRiskRecord(selectedRisk.value), levelPrompt.value as 'HIGH' | 'MEDIUM' | 'LOW', opinionPrompt.value))
    ElMessage.success('人工风险等级和审查意见已保存')
  } catch (cause: any) { if (cause !== 'cancel' && cause !== 'close') ElMessage.error(cause?.response?.data?.detail || '保存人工审查结论失败') }
  finally { riskSaving.value = false }
}

async function addComment() {
  if (!selectedRisk.value) return
  try {
    const prompt = await ElMessageBox.prompt('输入复核或整改评论', '添加评论', { inputType: 'textarea' })
    if (!prompt.value.trim()) return
    riskSaving.value = true
    replaceSelected(await addRiskComment(asRiskRecord(selectedRisk.value), prompt.value))
    ElMessage.success('评论已添加，可在风险详情查看')
  } catch (cause: any) { if (cause !== 'cancel' && cause !== 'close') ElMessage.error(cause?.response?.data?.detail || '评论失败') }
  finally { riskSaving.value = false }
}

async function rerun() {
  const summary = workspace.value?.summary
  if (!summary?.contract_id || !summary.contract_version_id) {
    await router.push('/review')
    return
  }
  rerunning.value = true
  try {
    const result = await startContractReview(summary.contract_id, summary.contract_version_id)
    if (result.status === 'COMPLETED' && result.result_summary?.review_id) {
      ElMessage.success('重新审查已完成')
      await router.replace(`/reader/${result.result_summary.review_id}`)
    } else {
      ElMessage.success('已创建重新审查任务')
      await router.replace(`/review-tasks?task_id=${result.task_id}`)
    }
  } catch (cause: any) { ElMessage.error(cause?.response?.data?.message || cause?.response?.data?.detail || '重新审查失败') }
  finally { rerunning.value = false }
}

function formatDate(value?: string | null) { return value ? new Date(value).toLocaleString('zh-CN', { hour12: false }) : '暂无数据' }
function locationText(risk: ReaderRisk) {
  if (pdfLocation.value) return `PDF 第 ${pdfLocation.value.page} 页 · 坐标 ${pdfLocation.value.box.map((value) => Math.round(value)).join(', ')}`
  if (risk.location.page_number) return `PDF 第 ${risk.location.page_number} 页`
  if (risk.location.start_offset !== null && risk.location.start_offset !== undefined) return `字符 ${risk.location.start_offset}–${risk.location.end_offset} · 当前仅支持文本位置`
  return '暂无可用原文位置'
}

watch(reviewId, load)
watch(severityFilter, () => { if (!filteredRisks.value.some((item) => item.risk_id === selectedRiskId.value)) selectedRiskId.value = filteredRisks.value[0]?.risk_id || '' })
onMounted(load)
onBeforeUnmount(() => { controller?.abort(); locationController?.abort() })
</script>

<template>
  <div class="review-workspace">
    <LoadingState v-if="loading && !workspace" title="正在加载审查工作区" description="系统正在读取合同原文和已验证风险结果。" />
    <ErrorState v-else-if="error" title="审查工作区加载失败" :description="error" @retry="load" />
    <template v-else-if="workspace">
      <section class="panel review-summary">
        <div class="summary-title"><span>REVIEW WORKSPACE</span><h1>{{ workspace.summary.contract_name }}</h1><p>{{ categoryLabels[workspace.summary.contract_type] || workspace.summary.contract_type }} · {{ workspace.summary.contract_version ? `V${workspace.summary.contract_version}` : '独立审查' }}</p></div>
        <dl><div><dt>审查状态</dt><dd><StatusTag label="已完成" tone="success" /></dd></div><div><dt>审查时间</dt><dd>{{ formatDate(workspace.summary.reviewed_at) }}</dd></div><div><dt>操作人</dt><dd>{{ workspace.summary.operator_name || '暂无数据' }}</dd></div><div><dt>总体风险</dt><dd><RiskLevelTag v-if="workspace.summary.overall_risk_level" :level="workspace.summary.overall_risk_level.replace('风险','')"/><span v-else>暂无数据</span></dd></div><div><dt>风险评分</dt><dd class="metric">{{ workspace.summary.risk_score ?? '暂无' }}<small v-if="workspace.summary.risk_score !== null"> / 100</small></dd></div><div><dt>风险数量</dt><dd class="metric">{{ workspace.summary.risk_count }}<small> 项</small></dd></div></dl>
        <div class="summary-actions"><el-button :icon="Download" :disabled="!workspace.summary.report_available" @click="downloadReaderReport(reviewId)">导出报告</el-button><el-button type="primary" :icon="RefreshRight" :loading="rerunning" @click="rerun">重新审查</el-button></div>
      </section>

      <section class="workspace-grid">
        <aside class="panel chapter-pane">
          <header><h2>合同章节</h2><el-select v-model="severityFilter" size="small"><el-option label="全部风险" value="all"/><el-option label="高风险" value="high"/><el-option label="中风险" value="medium"/><el-option label="低风险" value="low"/></el-select></header>
          <nav v-if="workspace.chapters.length" aria-label="合同章节"><button v-for="chapter in workspace.chapters" :key="chapter.chapter_id" @click="chapterClick(chapter.start_offset, chapter.end_offset)"><span><i v-if="chapter.high_risk_count" class="high-dot"></i>{{ chapter.title }}</span><small>{{ chapter.risk_count }} 项</small></button></nav>
          <EmptyState v-else compact title="暂无章节" description="合同原文为空或未识别到章节。" />
          <div class="risk-nav"><h3>风险定位</h3><button v-for="risk in filteredRisks" :key="risk.risk_id" :class="{ active: risk.risk_id === selectedRiskId }" @click="selectRisk(risk)"><RiskLevelTag :level="risk.severity"/><span>{{ risk.title }}</span></button><EmptyState v-if="!filteredRisks.length" compact title="暂无风险" description="当前筛选条件下没有风险项。" /></div>
        </aside>

        <main class="panel document-pane">
          <header><div class="search-box"><el-input v-model="searchQuery" clearable placeholder="搜索合同原文" :prefix-icon="Search" /></div><div class="reader-tools"><el-button-group><el-button :icon="Minus" aria-label="缩小字号" @click="fontScale=Math.max(.85,fontScale-.1)"/><el-button disabled>{{ Math.round(fontScale*100) }}%</el-button><el-button :icon="Plus" aria-label="放大字号" @click="fontScale=Math.min(1.4,fontScale+.1)"/></el-button-group><el-button :icon="ArrowLeft" :disabled="selectedIndex<=0" @click="move(-1)">上一条</el-button><el-button :icon="ArrowRight" :disabled="selectedIndex<0 || selectedIndex>=filteredRisks.length-1" @click="move(1)">下一条</el-button></div></header>
          <div v-if="paragraphs.length" class="document-text" :style="{ fontSize: `${fontScale}rem` }"><p v-for="paragraph in paragraphs" :id="paragraph.id" :key="paragraph.id"><template v-for="(segment,index) in paragraph.segments" :key="index"><mark v-if="segment.current" class="current-risk">{{ segment.text }}</mark><mark v-else-if="segment.search" class="search-hit">{{ segment.text }}</mark><template v-else>{{ segment.text }}</template></template>&nbsp;</p></div>
          <EmptyState v-else title="合同原文为空" description="当前审查记录没有可读取的解析文本，请重新上传可解析文件。" />
          <footer v-if="selectedRisk"><span>{{ locationText(selectedRisk) }}</span><span v-if="selectedRisk.location.is_ambiguous">存在重复文本，已按保存偏移或首个匹配定位</span></footer>
        </main>

        <aside class="panel risk-pane">
          <template v-if="selectedRisk">
            <header><RiskLevelTag :level="selectedRisk.severity"/><span>{{ selectedRisk.category }}</span></header><h2>{{ selectedRisk.title }}</h2>
            <section><h3>命中原文</h3><blockquote>{{ selectedRisk.clause_text || '该风险属于缺失条款检查，没有命中原文。' }}</blockquote><el-button link type="primary" @click="jumpToOffset(selectedRisk.location.start_offset)">跳转原文</el-button></section>
            <section><h3>风险说明</h3><p>{{ selectedRisk.explanation || '暂无风险说明' }}</p></section>
            <section class="metadata"><h3>检测信息</h3><dl><div><dt>规则来源</dt><dd>{{ selectedRisk.source }}</dd></div><div><dt>规则编号</dt><dd>{{ selectedRisk.rule_id || '暂无' }}</dd></div><div><dt>检测方式</dt><dd>{{ selectedRisk.detection_method }}</dd></div><div><dt>AI参与</dt><dd>{{ selectedRisk.ai_involved ? '是' : '否' }}</dd></div><div v-if="selectedRisk.confidence !== null && selectedRisk.confidence !== undefined"><dt>置信度</dt><dd>{{ `${Math.round(selectedRisk.confidence*100)}%` }}</dd></div><div><dt>原文位置</dt><dd>{{ locationText(selectedRisk) }}</dd></div></dl></section>
            <section><h3>知识依据</h3><div v-if="selectedRisk.knowledge_basis.length" class="basis-list"><article v-for="basis in selectedRisk.knowledge_basis" :key="basis.document_id"><strong>{{ basis.name }}</strong><dl><div><dt>条号</dt><dd>{{ basis.article_number || '未标注' }}</dd></div><div><dt>来源类型</dt><dd>{{ sourceTypeLabels[basis.source_type] || basis.source_type }}</dd></div><div><dt>效力状态</dt><dd>{{ statusLabels[basis.status] || basis.status }}</dd></div><div><dt>更新时间</dt><dd>{{ basis.updated_at ? formatDate(basis.updated_at) : '暂无维护时间' }}</dd></div></dl></article></div><p v-else class="muted">暂无已验证知识依据</p></section>
            <section><div class="section-heading"><h3>修改建议</h3><el-button link :icon="CopyDocument" @click="copySuggestion">复制建议</el-button></div><p>{{ selectedRisk.recommendation || '暂无修改建议' }}</p><blockquote v-if="selectedRisk.suggested_revision" class="revision">{{ selectedRisk.suggested_revision }}</blockquote></section>
            <section class="review-actions"><div class="section-heading"><h3>人工复核</h3><StatusTag :label="riskStatusLabels[selectedRisk.status] || selectedRisk.status || '待复核'" tone="info" /></div><p v-if="selectedRisk.review_comment"><strong>审查意见：</strong>{{ selectedRisk.review_comment }}</p><p v-if="selectedRisk.revised_clause"><strong>人工修改：</strong>{{ selectedRisk.revised_clause }}</p><p v-if="!selectedRisk.persisted" class="muted">该记录来自升级前的历史报告，尚无持久化风险记录；请重新审查后进行复核。</p><div v-else><el-button v-for="action in reviewActions" :key="action.key" type="primary" :loading="riskSaving" @click="runRiskAction(action.key, action.label)">{{ action.label }}</el-button><el-button :loading="riskSaving" @click="editHumanReview">修改等级/意见</el-button><el-button :loading="riskSaving" @click="saveManualRevision">保存人工修改</el-button><el-button :loading="riskSaving" @click="addComment">添加备注</el-button><el-button link type="primary" @click="router.push(`/risks/${selectedRisk.risk_id}`)">完整风险详情</el-button></div></section>
          </template>
          <EmptyState v-else title="暂无风险结果" description="当前审查没有风险项，或筛选条件下没有可展示内容。" />
        </aside>
      </section>
    </template>
  </div>
</template>

<style scoped>
.review-workspace { display: grid; gap: var(--space-4); min-width: 0; }
.review-summary { position: relative; display: grid; grid-template-columns: minmax(220px, 1.1fr) minmax(600px, 2fr) auto; align-items: center; gap: var(--space-6); padding: var(--space-5) var(--space-6); }
.summary-title span { color: var(--primary); font-size: 11px; font-weight: 700; letter-spacing: .12em; }.summary-title h1 { margin: 4px 0; font-size: 21px; }.summary-title p { margin: 0; color: var(--text-secondary); font-size: 13px; }
.review-summary > dl { display: grid; grid-template-columns: repeat(6,minmax(80px,1fr)); margin: 0; }.review-summary > dl div { min-width: 0; padding: 0 var(--space-3); border-left: 1px solid var(--border); }.review-summary dt { color: var(--text-muted); font-size: 12px; }.review-summary dd { margin: 6px 0 0; color: var(--text-primary); font-size: 13px; white-space: nowrap; }.review-summary dd.metric { font-size: 20px; font-weight: 700; }.review-summary dd small { color: var(--text-secondary); font-size: 12px; font-weight: 400; }.summary-actions { display: flex; gap: var(--space-2); }
.workspace-grid { display: grid; grid-template-columns: 260px minmax(440px,1fr) 360px; gap: var(--space-4); min-width: 0; height: calc(100vh - 264px); min-height: 620px; }
.chapter-pane,.risk-pane,.document-pane { min-height: 0; overflow: hidden; }.chapter-pane,.risk-pane { overflow-y: auto; }.chapter-pane { padding: var(--space-4); }.chapter-pane > header,.document-pane > header,.risk-pane > header,.section-heading { display: flex; align-items: center; justify-content: space-between; gap: var(--space-3); }.chapter-pane h2,.risk-pane h2 { margin: 0; font-size: 17px; }.chapter-pane nav { display: grid; gap: 4px; margin-top: var(--space-4); }.chapter-pane nav button,.risk-nav > button { display: flex; width: 100%; align-items: center; justify-content: space-between; gap: var(--space-2); padding: 9px 10px; border: 0; border-radius: var(--radius-sm); color: var(--text-secondary); background: transparent; text-align: left; cursor: pointer; }.chapter-pane nav button:hover,.risk-nav > button:hover,.risk-nav > button.active { color: var(--primary); background: var(--primary-soft); }.chapter-pane nav span { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }.chapter-pane nav small { flex: 0 0 auto; }.high-dot { display: inline-block; width: 7px; height: 7px; margin-right: 6px; border-radius: 50%; background: var(--risk-high); }.risk-nav { display: grid; gap: 4px; margin-top: var(--space-5); padding-top: var(--space-4); border-top: 1px solid var(--border); }.risk-nav h3 { margin: 0 0 var(--space-2); font-size: 14px; }.risk-nav > button { justify-content: flex-start; }.risk-nav > button span:last-child { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.document-pane { display: grid; grid-template-rows: auto 1fr auto; }.document-pane > header { padding: var(--space-3) var(--space-4); border-bottom: 1px solid var(--border); }.search-box { width: min(320px,40%); }.reader-tools { display: flex; gap: var(--space-2); }.document-text { overflow: auto; padding: 36px clamp(28px,7vw,84px); color: #273044; background: #fbfcfe; font-family: 'Songti SC','SimSun',serif; line-height: 1.95; scroll-behavior: smooth; }.document-text p { min-height: 1.95em; margin: 0; white-space: pre-wrap; overflow-wrap: anywhere; }.document-text mark { padding: 1px 0; color: inherit; }.current-risk { background: #fecaca; box-shadow: 0 0 0 2px rgba(220,38,38,.16); }.search-hit { background: #fef08a; }.document-pane footer { display: flex; justify-content: space-between; gap: var(--space-4); padding: 9px var(--space-4); border-top: 1px solid var(--border); color: var(--text-secondary); background: var(--surface-soft); font-size: 12px; }
.risk-pane { padding: var(--space-5); }.risk-pane > header { justify-content: flex-start; }.risk-pane h2 { margin-top: var(--space-3); line-height: 1.45; }.risk-pane section { padding: var(--space-4) 0; border-top: 1px solid var(--border); }.risk-pane h3 { margin: 0 0 var(--space-2); font-size: 14px; }.risk-pane p,.risk-pane blockquote { margin: 0; color: var(--text-secondary); font-size: 13px; line-height: 1.75; }.risk-pane blockquote { padding: var(--space-3); border-left: 3px solid var(--primary); background: var(--surface-soft); }.metadata dl,.basis-list dl { display: grid; gap: 8px; margin: 0; }.metadata dl div,.basis-list dl div { display: grid; grid-template-columns: 76px 1fr; gap: var(--space-2); }.metadata dt,.basis-list dt { color: var(--text-muted); }.metadata dd,.basis-list dd { margin: 0; color: var(--text-primary); overflow-wrap: anywhere; }.basis-list { display: grid; gap: var(--space-3); }.basis-list article { padding: var(--space-3); border: 1px solid var(--border); border-radius: var(--radius-sm); background: var(--surface-soft); }.basis-list article strong { display: block; margin-bottom: var(--space-2); font-size: 13px; }.basis-list dl { font-size: 12px; }.muted { color: var(--text-muted) !important; }.revision { margin-top: var(--space-3) !important; border-left-color: var(--risk-low) !important; }
.review-actions>div:last-child { display:flex; flex-wrap:wrap; gap:var(--space-2); margin-top:var(--space-3); }.review-actions strong { color:var(--text-primary); }
@media (max-width: 1450px) { .review-summary { grid-template-columns: 1fr; }.review-summary > dl { grid-template-columns: repeat(6,1fr); }.summary-actions { position: absolute; right: 44px; }.workspace-grid { grid-template-columns: 230px minmax(400px,1fr) 330px; height: calc(100vh - 338px); } }
@media (max-width: 1150px) { .workspace-grid { grid-template-columns: 220px minmax(0,1fr); height: auto; }.risk-pane { grid-column: 1 / -1; max-height: none; }.document-pane { min-height: 680px; } }
@media (max-width: 760px) { .review-summary > dl { grid-template-columns: repeat(2,1fr); gap: var(--space-3); }.summary-actions { position: static; }.workspace-grid { grid-template-columns: 1fr; }.chapter-pane { max-height: 420px; }.document-pane > header { align-items: stretch; flex-direction: column; }.search-box { width: 100%; }.reader-tools { flex-wrap: wrap; }.document-text { padding: var(--space-5); }.document-pane footer { flex-direction: column; } }
</style>
