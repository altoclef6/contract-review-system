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
import { fetchContracts } from '../services/contracts'
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()
const summary = ref<DashboardSummary>()
const loading = ref(true)
const errorMessage = ref('')
const demoMode = ref(false)
const overview = ref({ totalContracts: 0, todayAdded: 0, pendingReview: 0, reports: 0 })
let requestController: AbortController | undefined

const riskColors: Record<string, string> = {
  critical: '#991B1B', high: '#DC2626', medium: '#D97706', low: '#16A34A', unknown: '#94A3B8',
}
const riskTypeNames: Record<string, string> = {
  dispute: '争议风险',
  payment: '付款风险',
  liability: '责任风险',
  termination: '解除风险',
  confidentiality: '保密风险',
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
    const [dashboard, contracts] = await Promise.all([
      fetchDashboardSummary(requestController.signal),
      fetchContracts({ page: 1, page_size: 100, sort_by: 'updated_at', sort_order: 'desc' }, requestController.signal),
    ])
    summary.value = dashboard
    const today = new Date().toLocaleDateString('sv-SE')
    overview.value = {
      totalContracts: contracts.total,
      todayAdded: contracts.items.filter((item) => new Date(item.created_at).toLocaleDateString('sv-SE') === today).length,
      pendingReview: contracts.items.filter((item) => ['draft', 'reviewing', 'legal_review', 'manager_review'].includes(item.status)).length,
      reports: dashboard.metrics.monthly_review_count,
    }
    demoMode.value = false
  } catch (error: any) {
    if (error?.code !== 'ERR_CANCELED') {
      errorMessage.value = error?.response?.data?.message || error?.response?.data?.detail || '无法获取工作台数据，请稍后重试。'
    }
  } finally {
    if (!requestController.signal.aborted) loading.value = false
  }
}

function loadDemoDashboard() {
  const today = new Date()
  const iso = (offset: number) => new Date(today.getTime() + offset * 86_400_000).toISOString().slice(0, 10)
  summary.value = {
    generated_at: today.toISOString(), time_zone: 'Asia/Shanghai', scope: 'all',
    metrics: { monthly_review_count: 64, monthly_high_risk_contract_count: 12, pending_human_review_risk_count: 8, average_review_duration_ms: 12800 },
    review_trend_30d: Array.from({ length: 30 }, (_, index) => ({ date: iso(index - 29), count: [1,2,1,3,2,4,3][index % 7] })),
    risk_level_distribution: [{ key: 'critical', label: '严重风险', value: 2 }, { key: 'high', label: '高风险', value: 10 }, { key: 'medium', label: '中风险', value: 21 }, { key: 'low', label: '低风险', value: 31 }],
    contract_type_distribution: [{ key: 'software_development', label: '软件开发合同', value: 24 }, { key: 'lease', label: '租赁合同', value: 18 }, { key: 'nda', label: '保密协议', value: 16 }, { key: 'service', label: '服务合同', value: 13 }, { key: 'other', label: '其他合同', value: 16 }],
    top_risk_rules: [{ rule_id: 'R-PAY-01', title: '付款条件不明确', count: 18 }, { rule_id: 'R-ACC-02', title: '验收标准缺失', count: 14 }, { rule_id: 'R-IP-03', title: '知识产权不清', count: 11 }, { rule_id: 'R-LIA-04', title: '违约责任失衡', count: 9 }, { rule_id: 'R-TER-05', title: '解约责任过重', count: 7 }],
    recent_tasks: [
      { review_id: 'demo-001', contract_name: '软件开发服务合同', contract_type: 'software_development', status: 'completed', risk_level: '高风险', started_at: today.toISOString(), duration_ms: 12600 },
      { review_id: 'demo-002', contract_name: '办公场地租赁合同', contract_type: 'lease', status: 'completed', risk_level: '高风险', started_at: new Date(today.getTime() - 3_600_000).toISOString(), duration_ms: 9800 },
      { review_id: 'demo-003', contract_name: '员工保密协议', contract_type: 'nda', status: 'completed', risk_level: '中风险', started_at: new Date(today.getTime() - 7_200_000).toISOString(), duration_ms: 11200 },
    ],
    todos: [{ id: 'demo-todo-1', source: 'workflow', title: '待复核高风险条款', description: '软件开发服务合同：付款与验收条款需要人工确认。', status: 'legal_review', updated_at: today.toISOString(), action_path: '/risks' }],
    unavailable_reasons: {}, statistics_notes: ['当前为验收演示数据，所有数字均已在界面中明确标识，不写入业务数据库。'],
  }
  overview.value = { totalContracts: 87, todayAdded: 5, pendingReview: 8, reports: 64 }
  demoMode.value = true
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
  series: [{ type: 'pie', radius: ['46%', '68%'], center: ['50%', '42%'], avoidLabelOverlap: true, label: { color: '#475569', formatter: '{b}\n{c} 项' }, data: summary.value?.risk_level_distribution.map((item) => ({ name: riskTypeNames[item.key] || riskTypeNames[item.label.toLowerCase()] || item.label, value: item.value })) || [] }],
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
  <section class="dashboard-welcome">
    <div><small>{{ demoMode ? '验收演示数据' : '企业合同工作区' }}</small><h1>{{ auth.user?.full_name || '当前用户' }}，欢迎回来</h1><p>集中查看合同进度、风险分布与待办事项，今天也从最重要的风险开始。</p></div>
    <div class="dashboard-quick-actions"><router-link to="/contracts"><el-button>上传合同</el-button></router-link><router-link to="/review"><el-button type="primary">发起智能审查</el-button></router-link><router-link to="/reports"><el-button>查看报告</el-button></router-link></div>
  </section>
  <PageHeader title="企业工作台" description="基于当前授权范围查看合同审查、风险分布和真实待办。" eyebrow="Dashboard">
    <template #actions>
      <el-button :icon="Refresh" :loading="loading" @click="loadDashboard">刷新</el-button>
      <router-link to="/review"><el-button type="primary">新建审查</el-button></router-link>
    </template>
  </PageHeader>

  <el-skeleton v-if="loading && !summary" animated :rows="8" class="dashboard-skeleton" />
  <ErrorState v-else-if="errorMessage && !summary" title="工作台加载失败" :description="errorMessage" @retry="loadDashboard" />

  <template v-else-if="summary">
    <el-alert v-if="demoMode" title="当前为验收演示数据，不会写入合同、审查或报告记录。点击刷新即可恢复真实数据。" type="warning" :closable="false" show-icon />
    <section v-else-if="overview.totalContracts === 0" class="dashboard-demo-callout"><div><strong>当前还没有业务数据</strong><p>可以先上传合同，也可以载入一组明确标识的演示数据检查仪表盘效果。</p></div><el-button @click="loadDemoDashboard">载入验收演示数据</el-button></section>
    <section class="dashboard-metrics" aria-label="本月审查指标">
      <MetricCard label="合同总数" :value="overview.totalContracts" unit="份" />
      <MetricCard label="今日新增" :value="overview.todayAdded" unit="份" />
      <MetricCard label="待审查" :value="overview.pendingReview" unit="份" tone="medium" />
      <MetricCard label="高风险合同" :value="summary.metrics.monthly_high_risk_contract_count" unit="份" tone="high" />
      <MetricCard label="已生成报告" :value="overview.reports" unit="份" />
    </section>

    <section class="dashboard-chart-grid">
      <article class="dashboard-panel is-wide"><header><div><h2>最近 30 天审查趋势</h2><p>按 UTC 自然日统计已完成审查</p></div></header><DashboardChart :option="trendOption" :empty="!summary.review_trend_30d.some((item) => item.count > 0)" /></article>
      <article class="dashboard-panel"><header><div><h2>风险等级分布</h2><p>最近 30 天共识别 {{ summary.risk_level_distribution.reduce((total, item) => total + item.value, 0) }} 项风险</p></div></header><DashboardChart :option="riskOption" :empty="summary.risk_level_distribution.length === 0" /></article>
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
.dashboard-welcome { display: flex; align-items: center; justify-content: space-between; gap: 24px; margin-bottom: 18px; padding: 26px 28px; border: 1px solid #dce7f0; border-radius: 22px; background: linear-gradient(115deg, rgba(255,255,255,.96), rgba(240,246,250,.96)); box-shadow: 0 10px 28px rgba(45,72,98,.07); }
.dashboard-welcome small { color: #5d7e9e; font-size: 11px; font-weight: 800; letter-spacing: .12em; }
.dashboard-welcome h1 { margin: 5px 0 4px; font-size: 24px; }
.dashboard-welcome p { margin: 0; color: var(--text-secondary); }
.dashboard-quick-actions { display: flex; flex-wrap: wrap; justify-content: flex-end; gap: 8px; }
.dashboard-demo-callout { display: flex; align-items: center; justify-content: space-between; gap: 18px; margin: 0 0 18px; padding: 15px 18px; border: 1px solid #dce7f0; border-radius: 14px; background: #f7fafc; }
.dashboard-demo-callout strong { font-size: 13px; }
.dashboard-demo-callout p { margin: 3px 0 0; color: var(--text-secondary); font-size: 12px; }
.dashboard-skeleton { padding: 24px; border: 1px solid var(--border); border-radius: var(--radius-lg); background: var(--surface); }
.dashboard-metrics { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 20px; margin-top: 18px; margin-bottom: 24px; }
.dashboard-metrics :deep(.common-metric-card > small) { display: block; margin-top: 8px; color: var(--text-muted); font-size: 11px; }
.dashboard-metrics :deep(.common-metric-card > strong) { min-height: 32px; color: #273142; font-size: 23px; line-height: 32px; }
.dashboard-chart-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 20px; }
.dashboard-panel { min-width: 0; overflow: hidden; border: 1px solid #e6e9ef; border-radius: 10px; background: var(--surface); box-shadow: 0 1px 3px rgba(23, 32, 51, 0.04); }
.dashboard-panel > header { min-height: 62px; display: flex; align-items: center; justify-content: space-between; padding: 12px 18px; border-bottom: 1px solid var(--border); }
.dashboard-panel h2 { margin: 0; color: #273142; font-size: 15px; line-height: 22px; font-weight: 600; }
.dashboard-panel header p { margin: 2px 0 0; color: var(--text-muted); font-size: 12px; }
.dashboard-chart { width: 100%; height: 260px; }
.dashboard-panel :deep(.common-state) { min-height: 260px; border: 0; border-radius: 0; box-shadow: none; }
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
@media (max-width: 760px) { .dashboard-welcome, .dashboard-demo-callout { align-items: flex-start; flex-direction: column; } .dashboard-quick-actions { justify-content: flex-start; } .dashboard-metrics, .dashboard-chart-grid { grid-template-columns: 1fr; } .dashboard-panel { overflow-x: auto; } .dashboard-chart { min-width: 320px; } }
</style>
