<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { Refresh, Search } from '@element-plus/icons-vue'
import DashboardChart from '../components/dashboard/DashboardChart.vue'
import EmptyState from '../components/EmptyState.vue'
import ErrorState from '../components/ErrorState.vue'
import MetricCard from '../components/MetricCard.vue'
import PageHeader from '../components/PageHeader.vue'
import RiskLevelTag from '../components/RiskLevelTag.vue'
import StatusTag from '../components/StatusTag.vue'
import { fetchRisks, fetchRiskStatistics, type RiskQuery, type RiskRecord, type RiskStatistics, type RiskStatus } from '../services/risks'

const router = useRouter()
const items = ref<RiskRecord[]>([])
const total = ref(0)
const loading = ref(false)
const error = ref('')
const statistics = ref<RiskStatistics>()
let controller: AbortController | null = null
const filters = reactive<RiskQuery>({ page: 1, page_size: 10, keyword: '', severity: '', category: '', status: '', assignee_id: '', contract_type: '', date_from: '', date_to: '' })
const statusMap: Record<RiskStatus, { label: string; tone: 'neutral' | 'info' | 'success' | 'warning' | 'danger' }> = {
  pending_review: { label: '待复核', tone: 'warning' }, confirmed: { label: '已确认', tone: 'danger' }, rejected: { label: '已驳回', tone: 'neutral' },
  remediating: { label: '整改中', tone: 'info' }, remediated: { label: '已整改', tone: 'success' }, closed: { label: '已关闭', tone: 'neutral' },
}
const contractTypes: Record<string, string> = { software_development: '软件开发合同', technical_service: '技术服务合同', information_system: '信息系统建设合同', software_outsourcing: '软件外包合同', general: '通用合同', other: '其他' }
const categoryNames: Record<string, string> = { dispute: '争议风险', payment: '付款风险', liability: '责任风险', termination: '解除风险', confidentiality: '保密风险' }
const params = computed(() => Object.fromEntries(Object.entries(filters).filter(([, value]) => value !== '')) as unknown as RiskQuery)

async function load() {
  controller?.abort(); const active = new AbortController(); controller = active; loading.value = true; error.value = ''
  try {
    const [data, summary] = await Promise.all([fetchRisks(params.value, active.signal), fetchRiskStatistics(active.signal)])
    items.value = data.items; total.value = data.total; statistics.value = summary
  }
  catch (cause: any) { if (cause?.code !== 'ERR_CANCELED') error.value = cause?.response?.data?.detail || '风险台账加载失败' }
  finally { if (controller === active) loading.value = false }
}
function search() { filters.page = 1; void load() }
function formatDate(value: string) { return new Date(value).toLocaleString('zh-CN', { hour12: false }) }
function statusLabel(value: RiskStatus) { return statusMap[value]?.label || value }
function statusTone(value: RiskStatus) { return statusMap[value]?.tone || 'neutral' }
function chartData(values?: Record<string, number>, labels?: Record<string, string>) {
  return Object.entries(values || {}).map(([key, value]) => ({ name: labels?.[key] || key, value }))
}
const severityData = computed(() => chartData(statistics.value?.severities))
const statusData = computed(() => chartData(statistics.value?.statuses, Object.fromEntries(Object.entries(statusMap).map(([key, value]) => [key, value.label]))))
const categoryData = computed(() => chartData(statistics.value?.categories, categoryNames))
const pieOption = (data: Array<{ name: string; value: number }>, colors: string[]) => ({
  color: colors, tooltip: { trigger: 'item', formatter: '{b}<br/>{c} 项（{d}%）' },
  legend: { bottom: 0, type: 'scroll', textStyle: { color: '#64748B' } },
  series: [{ type: 'pie', radius: ['43%', '69%'], center: ['50%', '43%'], label: { color: '#475569', formatter: '{b}\n{c}' }, data }],
})
const severityOption = computed(() => pieOption(severityData.value, ['#7F1D1D', '#DC2626', '#D97706', '#16A34A', '#94A3B8']))
const statusOption = computed(() => pieOption(statusData.value, ['#D97706', '#DC2626', '#64748B', '#2563EB', '#16A34A', '#475569']))
const categoryOption = computed(() => pieOption(categoryData.value, ['#2563EB', '#60A5FA', '#14B8A6', '#7C3AED', '#D97706', '#64748B']))
onMounted(load)
onBeforeUnmount(() => controller?.abort())
</script>

<template>
  <div class="risk-ledger page-stack">
    <PageHeader title="风险台账" description="统一跟踪风险复核、整改和关闭过程，所有数据来自已持久化的审查结果。" eyebrow="RISK LEDGER">
      <template #actions><el-button :icon="Refresh" :loading="loading" @click="load">刷新</el-button></template>
    </PageHeader>
    <section class="panel filters risk-filter-shell">
      <div class="spotlight-search">
        <el-input v-model="filters.keyword" clearable placeholder="搜索风险、合同或原文" :prefix-icon="Search" @keyup.enter="search" />
        <el-button type="primary" @click="search">查询</el-button>
      </div>
      <div class="filter-pills" aria-label="风险筛选条件">
        <el-select v-model="filters.severity" clearable placeholder="风险等级"><el-option label="高风险" value="高"/><el-option label="中风险" value="中"/><el-option label="低风险" value="低"/></el-select>
        <el-select v-model="filters.contract_type" clearable placeholder="合同类型"><el-option v-for="(label,key) in contractTypes" :key="key" :label="label" :value="key"/></el-select>
        <el-select v-model="filters.status" clearable placeholder="状态"><el-option v-for="(item,key) in statusMap" :key="key" :label="item.label" :value="key"/></el-select>
        <el-input v-model="filters.category" clearable placeholder="风险类别" />
        <el-input v-model="filters.assignee_id" clearable placeholder="负责人 ID" />
        <el-date-picker v-model="filters.date_from" type="datetime" value-format="YYYY-MM-DDTHH:mm:ssZ" placeholder="发现时间起" />
        <el-date-picker v-model="filters.date_to" type="datetime" value-format="YYYY-MM-DDTHH:mm:ssZ" placeholder="发现时间止" />
      </div>
    </section>
    <section class="risk-metrics" aria-label="风险统计">
      <MetricCard label="风险总数" :value="statistics?.total ?? 0" unit="项" />
      <MetricCard label="待人工复核" :value="statistics?.pending_review_count ?? 0" unit="项" tone="medium" />
      <MetricCard label="整改处理中" :value="statistics?.active_remediation_count ?? 0" unit="项" />
      <MetricCard label="已解决" :value="statistics?.resolved_count ?? 0" unit="项" tone="low" />
      <MetricCard label="平均风险分" :value="statistics?.average_risk_score ?? 0" unit="/ 100" tone="high" />
    </section>
    <section class="risk-chart-grid">
      <article class="chart-panel chart-panel--primary"><header><h2>风险等级分布</h2><p>当前账号可访问的全部风险</p></header><DashboardChart :option="severityOption" :empty="!severityData.length" /></article>
      <article class="chart-panel"><header><h2>处理状态</h2><p>复核、整改和关闭进度</p></header><DashboardChart :option="statusOption" :empty="!statusData.length" /></article>
      <article class="chart-panel"><header><h2>风险类型</h2><p>用于定位高频条款问题</p></header><DashboardChart :option="categoryOption" :empty="!categoryData.length" /></article>
    </section>
    <ErrorState v-if="error" title="风险台账加载失败" :description="error" @retry="load" />
    <section v-else class="panel table-card">
      <el-table v-loading="loading" :data="items" row-key="risk_id" @row-click="(row: RiskRecord) => router.push(`/risks/${row.risk_id}`)">
        <el-table-column label="风险标题" min-width="220"><template #default="{row}"><strong>{{ row.title }}</strong><small>{{ row.category }}</small></template></el-table-column>
        <el-table-column label="合同 / 版本" min-width="190"><template #default="{row}">{{ row.contract_title || '独立审查' }}<small>{{ row.contract_version ? `V${row.contract_version}` : '暂无版本' }}</small></template></el-table-column>
        <el-table-column label="等级" width="90"><template #default="{row}"><RiskLevelTag :level="row.severity"/></template></el-table-column>
        <el-table-column prop="rule_id" label="规则" min-width="120"><template #default="{row}">{{ row.rule_id || '语义分析' }}</template></el-table-column>
        <el-table-column label="状态" width="100"><template #default="{row}"><StatusTag :label="statusLabel(row.status)" :tone="statusTone(row.status)"/></template></el-table-column>
        <el-table-column label="负责人" min-width="120"><template #default="{row}">{{ row.assignee_name || '未分配' }}</template></el-table-column>
        <el-table-column label="发现时间" min-width="165"><template #default="{row}">{{ formatDate(row.created_at) }}</template></el-table-column>
        <el-table-column label="更新时间" min-width="165"><template #default="{row}">{{ formatDate(row.updated_at) }}</template></el-table-column>
        <el-table-column label="操作" width="110" fixed="right"><template #default="{row}"><el-button link type="primary" @click.stop="router.push(`/risks/${row.risk_id}`)">查看详情</el-button></template></el-table-column>
      </el-table>
      <EmptyState v-if="!loading && !items.length" compact title="暂无风险记录" description="完成合同审查后，持久化风险会显示在这里。" />
      <el-pagination v-if="total" v-model:current-page="filters.page" v-model:page-size="filters.page_size" layout="total, sizes, prev, pager, next" :total="total" @change="load" />
    </section>
  </div>
</template>

<style scoped>
.risk-ledger { position:relative; isolation:isolate; }.risk-ledger::before { content:""; position:absolute; z-index:-1; top:90px; left:8%; width:520px; height:360px; border-radius:50%; background:radial-gradient(circle,rgba(119,153,255,.18),rgba(177,160,255,.08) 48%,transparent 72%); filter:blur(28px); pointer-events:none; }.page-stack { display:grid; gap:28px; }
.risk-filter-shell { padding:18px; border:1px solid rgba(255,255,255,.42); border-radius:24px; background:rgba(255,255,255,.48); box-shadow:0 10px 40px rgba(38,51,84,.06); backdrop-filter:blur(20px) saturate(135%); animation:glass-enter .5s ease both; }.spotlight-search { display:grid; grid-template-columns:minmax(0,1fr) auto; gap:12px; }.spotlight-search :deep(.el-input__wrapper) { height:48px; padding:0 18px; border-radius:16px; background:rgba(255,255,255,.66); box-shadow:0 8px 28px rgba(45,62,100,.06); }.spotlight-search :deep(.el-button) { height:48px; padding-inline:24px; border:0; border-radius:16px; background:linear-gradient(135deg,#4777db,#6d70d8); box-shadow:0 8px 22px rgba(75,104,190,.18); }.filter-pills { display:flex; flex-wrap:wrap; gap:10px; margin-top:14px; }.filter-pills > * { width:auto; min-width:128px; flex:0 1 168px; }.filter-pills :deep(.el-select__wrapper),.filter-pills :deep(.el-input__wrapper) { min-height:38px; border-radius:999px; border:0; background:rgba(255,255,255,.55); box-shadow:inset 0 0 0 1px rgba(255,255,255,.5); }.filter-pills :deep(.el-date-editor) { min-width:170px; }
.risk-metrics { display:grid; grid-template-columns:repeat(5,minmax(0,1fr)); gap:20px; }.risk-metrics :deep(.common-metric-card) { min-height:126px; display:flex; flex-direction:column; justify-content:center; padding:20px 22px; border:1px solid rgba(255,255,255,.38); border-radius:22px; background:linear-gradient(145deg,rgba(255,255,255,.62),rgba(245,247,255,.42)); box-shadow:0 10px 40px rgba(25,39,74,.06),inset 0 1px 0 rgba(255,255,255,.72); backdrop-filter:blur(20px); animation:glass-enter .55s ease both; transition:transform .22s ease,box-shadow .22s ease; }.risk-metrics :deep(.common-metric-card:hover) { transform:translateY(-3px); box-shadow:0 16px 46px rgba(35,52,90,.1),inset 0 1px 0 rgba(255,255,255,.8); }.risk-metrics :deep(.common-metric-card > strong) { order:1; color:#26344f; font-size:36px; line-height:44px; font-weight:650; letter-spacing:-.035em; }.risk-metrics :deep(.common-metric-card > span) { order:2; margin:7px 0 0; color:#7d899f; font-size:13px; }.risk-metrics :deep(.common-metric-card > strong small) { font-size:12px; color:#9aa5b8; }
.risk-chart-grid { display:grid; grid-template-columns:minmax(0,2fr) minmax(280px,1fr); grid-template-rows:repeat(2,minmax(0,1fr)); gap:22px; }.chart-panel { min-width:0; padding:20px 22px; border:1px solid rgba(255,255,255,.38); border-radius:24px; background:rgba(255,255,255,.52); box-shadow:0 10px 40px rgba(27,42,76,.06); backdrop-filter:blur(20px) saturate(130%); animation:glass-enter .6s ease both; transition:transform .22s ease,box-shadow .22s ease; }.chart-panel:hover { transform:translateY(-3px); box-shadow:0 16px 48px rgba(30,47,85,.1); }.chart-panel--primary { grid-row:1 / span 2; }.chart-panel header h2 { margin:0; color:#354158; font-size:15px; font-weight:650; }.chart-panel header p { margin:4px 0 0; color:#929bad; font-size:12px; }.chart-panel :deep(.dashboard-chart) { width:100%; height:220px; }.chart-panel--primary :deep(.dashboard-chart) { height:382px; }.chart-panel :deep(.common-state) { min-height:148px; padding:20px; border:0; background:transparent; box-shadow:none; }.chart-panel--primary :deep(.common-state) { min-height:350px; }
.table-card { padding:10px 12px 4px; overflow:hidden; border:1px solid rgba(255,255,255,.4); border-radius:24px; background:rgba(255,255,255,.48); box-shadow:0 10px 40px rgba(30,44,76,.055); backdrop-filter:blur(20px); animation:glass-enter .65s ease both; }.table-card :deep(.el-table) { --el-table-bg-color:transparent; --el-table-tr-bg-color:transparent; --el-table-header-bg-color:transparent; --el-table-row-hover-bg-color:rgba(255,255,255,.62); background:transparent; }.table-card :deep(.el-table__inner-wrapper::before) { display:none; }.table-card :deep(th.el-table__cell) { height:44px; border-bottom-color:rgba(143,156,181,.12); color:#939cad; font-size:12px; font-weight:550; }.table-card :deep(td.el-table__cell) { height:62px; border-bottom-color:rgba(143,156,181,.1); }.table-card :deep(.el-table__row) { cursor:pointer; transition:background .18s ease; }.table-card strong,.table-card small { display:block; }.table-card small { margin-top:4px; color:var(--text-muted); font-size:12px; }.el-pagination { justify-content:flex-end; padding:16px; border-top:0; }
@keyframes glass-enter { from { opacity:0; transform:translateY(20px); } to { opacity:1; transform:translateY(0); } }
@media (max-width:1180px) { .risk-metrics { grid-template-columns:repeat(2,1fr); }.risk-chart-grid { grid-template-columns:1fr; grid-template-rows:auto; }.chart-panel--primary { grid-row:auto; }.chart-panel--primary :deep(.dashboard-chart) { height:300px; } }
@media (max-width:720px) { .page-stack { gap:20px; }.risk-metrics { grid-template-columns:1fr; }.spotlight-search { grid-template-columns:1fr; }.filter-pills > * { flex:1 1 100%; }.risk-filter-shell,.chart-panel,.table-card { border-radius:18px; } }
@media (prefers-reduced-motion:reduce) { .risk-filter-shell,.risk-metrics :deep(.common-metric-card),.chart-panel,.table-card { animation:none; transition:none; } }
</style>
