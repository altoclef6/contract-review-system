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
const categoryData = computed(() => chartData(statistics.value?.categories))
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
    <section class="risk-metrics" aria-label="风险统计">
      <MetricCard label="风险总数" :value="statistics?.total ?? 0" unit="项" />
      <MetricCard label="待人工复核" :value="statistics?.pending_review_count ?? 0" unit="项" tone="medium" />
      <MetricCard label="整改处理中" :value="statistics?.active_remediation_count ?? 0" unit="项" />
      <MetricCard label="已解决" :value="statistics?.resolved_count ?? 0" unit="项" tone="low" />
      <MetricCard label="平均风险分" :value="statistics?.average_risk_score ?? 0" unit="/ 100" tone="high" />
    </section>
    <section class="risk-chart-grid">
      <article class="chart-panel"><header><h2>风险等级分布</h2><p>当前账号可访问的全部风险</p></header><DashboardChart :option="severityOption" :empty="!severityData.length" /></article>
      <article class="chart-panel"><header><h2>处理状态分布</h2><p>复核、整改和关闭进度</p></header><DashboardChart :option="statusOption" :empty="!statusData.length" /></article>
      <article class="chart-panel"><header><h2>风险类别分布</h2><p>用于定位高频条款问题</p></header><DashboardChart :option="categoryOption" :empty="!categoryData.length" /></article>
    </section>
    <section class="panel filters">
      <el-input v-model="filters.keyword" clearable placeholder="搜索风险、合同或原文" :prefix-icon="Search" @keyup.enter="search" />
      <el-select v-model="filters.severity" clearable placeholder="风险等级"><el-option label="高风险" value="高"/><el-option label="中风险" value="中"/><el-option label="低风险" value="低"/></el-select>
      <el-select v-model="filters.status" clearable placeholder="状态"><el-option v-for="(item,key) in statusMap" :key="key" :label="item.label" :value="key"/></el-select>
      <el-input v-model="filters.category" clearable placeholder="风险类别" />
      <el-select v-model="filters.contract_type" clearable placeholder="合同类型"><el-option v-for="(label,key) in contractTypes" :key="key" :label="label" :value="key"/></el-select>
      <el-input v-model="filters.assignee_id" clearable placeholder="负责人 ID" />
      <el-date-picker v-model="filters.date_from" type="datetime" value-format="YYYY-MM-DDTHH:mm:ssZ" placeholder="发现时间起" />
      <el-date-picker v-model="filters.date_to" type="datetime" value-format="YYYY-MM-DDTHH:mm:ssZ" placeholder="发现时间止" />
      <el-button type="primary" @click="search">查询</el-button>
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
        <el-table-column label="操作" width="90" fixed="right"><template #default="{row}"><el-button link type="primary" @click.stop="router.push(`/risks/${row.risk_id}`)">详情</el-button></template></el-table-column>
      </el-table>
      <EmptyState v-if="!loading && !items.length" compact title="暂无风险记录" description="完成合同审查后，持久化风险会显示在这里。" />
      <el-pagination v-if="total" v-model:current-page="filters.page" v-model:page-size="filters.page_size" layout="total, sizes, prev, pager, next" :total="total" @change="load" />
    </section>
  </div>
</template>

<style scoped>
.page-stack { display:grid; gap:var(--space-5); }.risk-metrics { display:grid; grid-template-columns:repeat(5,minmax(0,1fr)); gap:var(--space-4); }.risk-chart-grid { display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:var(--space-4); }.chart-panel { min-width:0; padding:var(--space-5); border:1px solid var(--border); border-radius:var(--radius-lg); background:#fff; box-shadow:var(--shadow-sm); }.chart-panel header h2 { margin:0; font-size:16px; }.chart-panel header p { margin:4px 0 0; color:var(--text-muted); font-size:12px; }.chart-panel :deep(.dashboard-chart) { width:100%; height:280px; }.filters { display:grid; grid-template-columns:2fr repeat(4,minmax(130px,1fr)) minmax(150px,1fr) repeat(2,minmax(170px,1fr)) auto; gap:var(--space-3); padding:var(--space-4); }.table-card { padding:0; overflow:hidden; }.table-card :deep(.el-table__row) { cursor:pointer; }.table-card strong,.table-card small { display:block; }.table-card small { margin-top:4px; color:var(--text-muted); font-size:12px; }.el-pagination { justify-content:flex-end; padding:var(--space-4); border-top:1px solid var(--border); }
@media (max-width:1400px) { .filters { grid-template-columns:repeat(4,1fr); }.filters > :first-child { grid-column:span 2; } }
@media (max-width:1100px) { .risk-metrics { grid-template-columns:repeat(2,1fr); }.risk-chart-grid { grid-template-columns:1fr; } }
@media (max-width:800px) { .filters { grid-template-columns:1fr; }.filters > :first-child { grid-column:auto; } }
</style>
