<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { Refresh } from '@element-plus/icons-vue'
import DashboardChart from '../components/dashboard/DashboardChart.vue'
import EmptyState from '../components/EmptyState.vue'
import ErrorState from '../components/ErrorState.vue'
import MetricCard from '../components/MetricCard.vue'
import PageHeader from '../components/PageHeader.vue'
import RiskLevelTag from '../components/RiskLevelTag.vue'
import StatusTag from '../components/StatusTag.vue'
import { fetchDashboardSummary, type DashboardSummary } from '../services/dashboard'

const summary = ref<DashboardSummary>()
const loading = ref(true)
const errorMessage = ref('')
let requestController: AbortController | undefined

const riskColors: Record<string, string> = {
  critical: '#991B1B', high: '#DC2626', medium: '#D97706', low: '#16A34A', unknown: '#94A3B8',
}
const contractTypeNames: Record<string, string> = {
  general: '通用合同', purchase: '采购合同', sales: '销售合同', employment: '劳动合同',
  labor: '劳动合同', lease: '租赁合同', nda: '保密协议', service: '服务合同',
  software_development: '软件开发合同', technical_service: '技术服务合同',
  information_system: '信息系统建设合同', software_outsourcing: '软件外包合同', other: '其他合同',
}

async function loadDashboard() {
  requestController?.abort()
  requestController = new AbortController()
  loading.value = true
  errorMessage.value = ''
  try {
    summary.value = await fetchDashboardSummary(requestController.signal)
  } catch (error: any) {
    if (error?.code !== 'ERR_CANCELED') {
      errorMessage.value = error?.response?.data?.message || error?.response?.data?.detail || '无法获取工作台数据，请稍后重试。'
    }
  } finally {
    if (!requestController.signal.aborted) loading.value = false
  }
}

onMounted(loadDashboard)
onBeforeUnmount(() => requestController?.abort())

const trendOption = computed(() => ({
  color: ['#2563EB'],
  tooltip: { trigger: 'axis' },
  grid: { top: 24, right: 20, bottom: 34, left: 44 },
  xAxis: { type: 'category', boundaryGap: false, data: summary.value?.review_trend_30d.map((item) => item.date.slice(5)) || [], axisLine: { lineStyle: { color: '#D7DEEA' } }, axisLabel: { color: '#64748B', interval: 4 } },
  yAxis: { type: 'value', minInterval: 1, axisLabel: { color: '#64748B' }, splitLine: { lineStyle: { color: '#EEF2F7' } } },
  series: [{ type: 'line', smooth: 0.22, symbolSize: 6, data: summary.value?.review_trend_30d.map((item) => item.count) || [], areaStyle: { color: 'rgba(37, 99, 235, 0.08)' }, lineStyle: { width: 2 } }],
}))

const riskOption = computed(() => ({
  color: summary.value?.risk_level_distribution.map((item) => riskColors[item.key]) || [],
  tooltip: { trigger: 'item' },
  legend: { bottom: 0, textStyle: { color: '#64748B' } },
  series: [{ type: 'pie', radius: ['48%', '70%'], center: ['50%', '44%'], avoidLabelOverlap: true, label: { color: '#475569', formatter: '{b}\n{c}' }, data: summary.value?.risk_level_distribution.map((item) => ({ name: item.label, value: item.value })) || [] }],
}))

const typeOption = computed(() => ({
  color: ['#2563EB', '#60A5FA', '#93C5FD', '#1D4ED8', '#64748B'],
  tooltip: { trigger: 'item' },
  legend: { bottom: 0, type: 'scroll', textStyle: { color: '#64748B' } },
  series: [{ type: 'pie', radius: ['42%', '68%'], center: ['50%', '43%'], label: { color: '#475569', formatter: '{b}\n{c}' }, data: summary.value?.contract_type_distribution.map((item) => ({ name: item.label, value: item.value })) || [] }],
}))

const rulesOption = computed(() => {
  const items = [...(summary.value?.top_risk_rules || [])].reverse()
  return {
    color: ['#2563EB'],
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    grid: { top: 16, right: 24, bottom: 24, left: 132 },
    xAxis: { type: 'value', minInterval: 1, axisLabel: { color: '#64748B' }, splitLine: { lineStyle: { color: '#EEF2F7' } } },
    yAxis: { type: 'category', data: items.map((item) => item.title.length > 9 ? `${item.title.slice(0, 9)}…` : item.title), axisLabel: { color: '#475569' }, axisLine: { show: false }, axisTick: { show: false } },
    series: [{ type: 'bar', barWidth: 16, data: items.map((item) => item.count), itemStyle: { borderRadius: [0, 4, 4, 0] } }],
  }
})

function metricValue(value: number | null | undefined) {
  return value === null || value === undefined ? '暂无数据' : value
}
function duration(value: number | null | undefined) {
  if (value === null || value === undefined) return '暂无数据'
  return value < 1000 ? `${Math.round(value)} ms` : `${(value / 1000).toFixed(1)} 秒`
}
function formatDate(value: string | null) {
  if (!value) return '暂无数据'
  return new Intl.DateTimeFormat('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hour12: false }).format(new Date(value))
}
</script>

<template>
  <PageHeader title="企业工作台" description="基于当前授权范围查看合同审查、风险分布和真实待办。" eyebrow="Dashboard">
    <template #actions>
      <el-button :icon="Refresh" :loading="loading" @click="loadDashboard">刷新</el-button>
      <router-link to="/review"><el-button type="primary">发起智能审查</el-button></router-link>
    </template>
  </PageHeader>

  <el-skeleton v-if="loading && !summary" animated :rows="8" class="dashboard-skeleton" />
  <ErrorState v-else-if="errorMessage && !summary" title="工作台加载失败" :description="errorMessage" @retry="loadDashboard" />

  <template v-else-if="summary">
    <section class="dashboard-metrics" aria-label="本月审查指标">
      <MetricCard label="本月审查合同数" :value="summary.metrics.monthly_review_count" unit="份" />
      <MetricCard label="高风险合同数" :value="summary.metrics.monthly_high_risk_contract_count" unit="份" tone="high" />
      <MetricCard label="待人工复核风险数" :value="metricValue(summary.metrics.pending_human_review_risk_count)" tone="medium">
        <small v-if="summary.metrics.pending_human_review_risk_count === null">风险复核状态尚未持久化</small>
      </MetricCard>
      <MetricCard label="平均审查耗时" :value="duration(summary.metrics.average_review_duration_ms)" />
    </section>

    <section class="dashboard-chart-grid">
      <article class="dashboard-panel is-wide"><header><div><h2>最近 30 天审查趋势</h2><p>按 UTC 自然日统计已完成审查</p></div></header><DashboardChart :option="trendOption" :empty="!summary.review_trend_30d.some((item) => item.count > 0)" /></article>
      <article class="dashboard-panel"><header><div><h2>风险等级分布</h2><p>最近 30 天已完成审查</p></div></header><DashboardChart :option="riskOption" :empty="summary.risk_level_distribution.length === 0" /></article>
      <article class="dashboard-panel"><header><div><h2>合同类型分布</h2><p>最近 30 天已完成审查</p></div></header><DashboardChart :option="typeOption" :empty="summary.contract_type_distribution.length === 0" /></article>
      <article class="dashboard-panel is-wide"><header><div><h2>高频风险规则 Top 5</h2><p>仅统计具有完整规则快照的最近 30 天审查</p></div></header><DashboardChart :option="rulesOption" :empty="!summary.top_risk_rules?.length" :empty-title="summary.top_risk_rules === null ? '暂无完整规则排名' : '暂无规则命中'" :empty-description="summary.unavailable_reasons.top_risk_rules || '当前统计范围内没有确定性规则命中。'" /></article>
    </section>

    <section class="dashboard-list-grid">
      <article class="dashboard-panel recent-task-panel">
        <header><div><h2>最近审查任务</h2><p>当前授权范围内最近完成的 8 条记录</p></div></header>
        <el-table v-if="summary.recent_tasks.length" :data="summary.recent_tasks">
          <el-table-column prop="contract_name" label="合同名称" min-width="180" show-overflow-tooltip />
          <el-table-column label="类型" width="130"><template #default="scope">{{ contractTypeNames[scope.row.contract_type] || scope.row.contract_type }}</template></el-table-column>
          <el-table-column label="任务状态" width="105"><template #default><StatusTag label="已完成" tone="success" /></template></el-table-column>
          <el-table-column label="风险等级" width="105"><template #default="scope"><RiskLevelTag v-if="scope.row.risk_level" :level="scope.row.risk_level.replace('风险', '')" /><span v-else>暂无数据</span></template></el-table-column>
          <el-table-column label="开始时间" width="150"><template #default="scope">{{ formatDate(scope.row.started_at) }}</template></el-table-column>
          <el-table-column label="耗时" width="100"><template #default="scope">{{ duration(scope.row.duration_ms) }}</template></el-table-column>
          <el-table-column label="操作" width="100" fixed="right"><template #default="scope"><router-link v-if="scope.row.contract_name.toLowerCase().endsWith('.pdf')" :to="`/reader/${scope.row.review_id}`"><el-button text type="primary">查看</el-button></router-link><el-button v-else text disabled title="当前在线阅读器仅支持 PDF">暂无入口</el-button></template></el-table-column>
        </el-table>
        <EmptyState v-else compact title="暂无审查任务" description="上传合同并完成审查后，最近任务会显示在这里。" />
      </article>

      <article class="dashboard-panel todo-panel">
        <header><div><h2>待我处理</h2><p>只展示现有工作流中可确认的真实待办</p></div></header>
        <div v-if="summary.todos.length" class="todo-list">
          <router-link v-for="item in summary.todos" :key="item.id" :to="item.action_path" class="todo-item">
            <span class="todo-item__mark"></span><div><strong>{{ item.title }}</strong><p>{{ item.description }}</p><small>{{ formatDate(item.updated_at) }}</small></div><span>处理</span>
          </router-link>
        </div>
        <EmptyState v-else compact title="当前没有待办" description="风险复核和失败任务尚未持久化时，不会生成虚假待办。" />
      </article>
    </section>

    <details class="statistics-notes"><summary>统计口径与暂不可用数据</summary><ul><li v-for="note in summary.statistics_notes" :key="note">{{ note }}</li><li v-for="(reason, key) in summary.unavailable_reasons" :key="key">{{ reason }}</li></ul></details>
  </template>
</template>

<style scoped>
.dashboard-skeleton { padding: 24px; border: 1px solid var(--border); border-radius: var(--radius-lg); background: var(--surface); }
.dashboard-metrics { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 16px; margin-bottom: 20px; }
.dashboard-metrics :deep(.common-metric-card > small) { display: block; margin-top: 8px; color: var(--text-muted); font-size: 11px; }
.dashboard-metrics :deep(.common-metric-card > strong) { min-height: 34px; font-size: 26px; }
.dashboard-chart-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 20px; }
.dashboard-panel { min-width: 0; overflow: hidden; border: 1px solid var(--border); border-radius: var(--radius-lg); background: var(--surface); box-shadow: var(--shadow-card); }
.dashboard-panel > header { min-height: 68px; display: flex; align-items: center; justify-content: space-between; padding: 14px 20px; border-bottom: 1px solid var(--border); }
.dashboard-panel h2 { margin: 0; font-size: 16px; line-height: 24px; }
.dashboard-panel header p { margin: 2px 0 0; color: var(--text-muted); font-size: 12px; }
.dashboard-chart { width: 100%; height: 300px; }
.dashboard-panel :deep(.common-state) { min-height: 300px; border: 0; border-radius: 0; box-shadow: none; }
.dashboard-list-grid { display: grid; grid-template-columns: minmax(0, 1.7fr) minmax(320px, 0.8fr); gap: 20px; margin-top: 20px; }
.recent-task-panel { overflow-x: auto; }
.todo-list { padding: 10px; }
.todo-item { display: grid; grid-template-columns: 4px minmax(0, 1fr) auto; gap: 12px; align-items: center; padding: 12px; border-radius: var(--radius-md); }
.todo-item:hover { background: var(--surface-soft); }
.todo-item__mark { align-self: stretch; border-radius: 2px; background: var(--risk-medium); }
.todo-item strong { font-size: 13px; }
.todo-item p { margin: 3px 0; color: var(--text-secondary); font-size: 12px; line-height: 18px; }
.todo-item small { color: var(--text-muted); font-size: 11px; }
.todo-item > span:last-child { color: var(--primary); font-size: 12px; font-weight: 700; }
.statistics-notes { margin-top: 16px; padding: 12px 16px; border: 1px solid var(--border); border-radius: var(--radius-md); color: var(--text-secondary); background: var(--surface-soft); font-size: 12px; }
.statistics-notes summary { cursor: pointer; font-weight: 700; }
.statistics-notes ul { margin: 10px 0 0; padding-left: 20px; }
.statistics-notes li + li { margin-top: 4px; }
@media (max-width: 1180px) { .dashboard-metrics { grid-template-columns: repeat(2, minmax(0, 1fr)); } .dashboard-list-grid { grid-template-columns: 1fr; } }
@media (max-width: 760px) { .dashboard-metrics, .dashboard-chart-grid { grid-template-columns: 1fr; } .dashboard-panel { overflow-x: auto; } .dashboard-chart { min-width: 320px; } }
</style>
