<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Download, Refresh, Search } from '@element-plus/icons-vue'
import DashboardChart from '../components/dashboard/DashboardChart.vue'
import EmptyState from '../components/EmptyState.vue'
import ErrorState from '../components/ErrorState.vue'
import MetricCard from '../components/MetricCard.vue'
import PageHeader from '../components/PageHeader.vue'
import RiskLevelTag from '../components/RiskLevelTag.vue'
import { api } from '../api'

interface ReportRecord {
  review_id: string
  file_name: string
  contract_type: string
  overall_risk_level?: string | null
  risk_score?: number | null
  duration_ms?: number | null
  model_name?: string | null
  created_at: string
}

const loading = ref(false)
const error = ref('')
const records = ref<ReportRecord[]>([])
const keyword = ref('')
const riskLevel = ref('')
const contractType = ref('')
let controller: AbortController | null = null

const contractTypeNames: Record<string, string> = {
  software_development: '软件开发合同', technical_service: '技术服务合同',
  information_system: '信息系统建设合同', software_outsourcing: '软件外包合同',
  procurement: '采购合同', purchase: '采购合同', sales: '销售合同', labor: '劳动合同',
  employment: '劳动合同', lease: '租赁合同', nda: '保密协议', service: '服务合同',
  other: '其他合同', general: '通用合同',
}
const riskColors: Record<string, string> = {
  严重: '#7F1D1D', 严重风险: '#7F1D1D', 高: '#DC2626', 高风险: '#DC2626',
  中: '#D97706', 中风险: '#D97706', 低: '#16A34A', 低风险: '#16A34A', 未知: '#94A3B8',
}

async function load() {
  controller?.abort()
  const active = new AbortController()
  controller = active
  loading.value = true
  error.value = ''
  try {
    const response = await api.get('/reviews', { signal: active.signal })
    records.value = Array.isArray(response.data)
      ? response.data.filter((item: unknown) => item && typeof item === 'object').map((item: any) => ({
          ...item,
          review_id: String(item.review_id || ''),
          file_name: String(item.file_name || '未命名合同'),
          contract_type: String(item.contract_type || 'other'),
          created_at: String(item.created_at || ''),
        }))
      : []
  } catch (cause: any) {
    if (cause?.code !== 'ERR_CANCELED') {
      error.value = cause?.response?.data?.message || cause?.response?.data?.detail || '报告列表加载失败'
    }
  } finally {
    if (controller === active) loading.value = false
  }
}

const filteredRecords = computed(() => records.value.filter((item) => {
  const term = keyword.value.trim().toLocaleLowerCase()
  return (!term || item.file_name.toLocaleLowerCase().includes(term) || item.review_id.toLocaleLowerCase().includes(term))
    && (!riskLevel.value || item.overall_risk_level === riskLevel.value)
    && (!contractType.value || item.contract_type === contractType.value)
}))
const scores = computed(() => records.value.map((item) => item.risk_score).filter((value): value is number => typeof value === 'number'))
const averageScore = computed(() => scores.value.length ? (scores.value.reduce((sum, value) => sum + value, 0) / scores.value.length).toFixed(1) : '暂无')
const highRiskCount = computed(() => records.value.filter((item) => /严重|高/.test(item.overall_risk_level || '')).length)
const monthReviewCount = computed(() => {
  const now = new Date()
  return records.value.filter((item) => {
    const created = new Date(item.created_at)
    return created.getFullYear() === now.getFullYear() && created.getMonth() === now.getMonth()
  }).length
})

function distribution(key: 'overall_risk_level' | 'contract_type' | 'model_name') {
  const result: Record<string, number> = {}
  for (const item of records.value) {
    const raw = String(item[key] || '未知')
    const label = key === 'contract_type' ? (contractTypeNames[raw] || raw) : raw
    result[label] = (result[label] || 0) + 1
  }
  return Object.entries(result).map(([name, value]) => ({ name, value }))
}

const riskData = computed(() => distribution('overall_risk_level'))
const typeData = computed(() => distribution('contract_type'))
const modelData = computed(() => distribution('model_name'))
const pieOption = (data: Array<{ name: string; value: number }>, colors?: string[]) => ({
  color: colors,
  tooltip: { trigger: 'item', formatter: '{b}<br/>{c} 次（{d}%）' },
  legend: { bottom: 0, type: 'scroll', textStyle: { color: '#64748B' } },
  series: [{ type: 'pie', radius: ['43%', '69%'], center: ['50%', '43%'], label: { color: '#475569', formatter: '{b}\n{c}' }, data }],
})
const riskOption = computed(() => pieOption(riskData.value, riskData.value.map((item) => riskColors[item.name] || '#64748B')))
const typeOption = computed(() => pieOption(typeData.value, ['#2563EB', '#60A5FA', '#93C5FD', '#1D4ED8', '#64748B', '#14B8A6']))
const modelOption = computed(() => pieOption(modelData.value, ['#7C3AED', '#A78BFA', '#2563EB', '#64748B']))

async function download(row: ReportRecord, type: string) {
  try {
    const response = await api.get(`/reviews/${row.review_id}/download`, { params: { file_type: type }, responseType: 'blob' })
    const url = URL.createObjectURL(response.data)
    const anchor = document.createElement('a')
    anchor.href = url
    anchor.download = `${row.review_id}.${type}`
    document.body.appendChild(anchor)
    anchor.click()
    anchor.remove()
    URL.revokeObjectURL(url)
  } catch (cause: any) { ElMessage.error(cause?.response?.data?.message || '报告下载失败') }
}

function formatDate(value?: string) { return value ? new Date(value).toLocaleString('zh-CN', { hour12: false }) : '暂无数据' }
function formatDuration(value?: number | null) { return typeof value === 'number' ? `${(value / 1000).toFixed(1)} 秒` : '暂无' }
onMounted(load)
onBeforeUnmount(() => controller?.abort())
</script>

<template>
  <div class="report-center">
    <PageHeader title="报告中心" description="按当前账号授权范围查看审查趋势、风险分布和可追溯报告。" eyebrow="REPORTS">
      <template #actions><el-button :icon="Refresh" :loading="loading" @click="load">刷新</el-button></template>
    </PageHeader>
    <ErrorState v-if="error && !records.length" title="报告加载失败" :description="error" @retry="load" />
    <template v-else>
      <section class="report-metrics" aria-label="报告统计">
        <MetricCard label="累计审查" :value="records.length" unit="次" />
        <MetricCard label="本月审查" :value="monthReviewCount" unit="次" />
        <MetricCard label="高风险报告" :value="highRiskCount" unit="份" tone="high" />
        <MetricCard label="平均风险评分" :value="averageScore" unit="/ 100" tone="medium" />
      </section>
      <section class="report-chart-grid">
        <article class="chart-panel"><header><h2>风险等级分布</h2><p>全部可查阅报告</p></header><DashboardChart :option="riskOption" :empty="!riskData.length" /></article>
        <article class="chart-panel"><header><h2>合同类型分布</h2><p>自动分类后的合同类型</p></header><DashboardChart :option="typeOption" :empty="!typeData.length" /></article>
        <article class="chart-panel"><header><h2>审查模型分布</h2><p>规则引擎与已配置模型</p></header><DashboardChart :option="modelOption" :empty="!modelData.length" /></article>
      </section>
      <section class="panel report-filters">
        <el-input v-model="keyword" clearable :prefix-icon="Search" placeholder="搜索合同名称或审查编号" />
        <el-select v-model="riskLevel" clearable placeholder="风险等级"><el-option v-for="item in riskData" :key="item.name" :label="item.name" :value="item.name" /></el-select>
        <el-select v-model="contractType" clearable placeholder="合同类型"><el-option v-for="(label, value) in contractTypeNames" :key="value" :label="label" :value="value" /></el-select>
        <span>当前展示 {{ filteredRecords.length }} / {{ records.length }} 份报告</span>
      </section>
      <section class="panel table-panel">
        <el-table v-loading="loading" :data="filteredRecords" row-key="review_id">
          <el-table-column prop="file_name" label="合同名称" min-width="220" show-overflow-tooltip />
          <el-table-column label="合同类型" width="150"><template #default="{ row }">{{ contractTypeNames[row.contract_type] || row.contract_type }}</template></el-table-column>
          <el-table-column label="风险等级" width="110"><template #default="{ row }"><RiskLevelTag v-if="row.overall_risk_level" :level="row.overall_risk_level"/><span v-else>暂无</span></template></el-table-column>
          <el-table-column prop="risk_score" label="风险评分" width="100" />
          <el-table-column label="审查耗时" width="110"><template #default="{ row }">{{ formatDuration(row.duration_ms) }}</template></el-table-column>
          <el-table-column label="生成时间" width="190"><template #default="{ row }">{{ formatDate(row.created_at) }}</template></el-table-column>
          <el-table-column label="导出" width="270" fixed="right"><template #default="{ row }">
            <el-button link type="primary" :icon="Download" @click="download(row, 'pdf')">PDF</el-button>
            <el-button link @click="download(row, 'docx')">Word</el-button>
            <el-button link @click="download(row, 'xlsx')">Excel</el-button>
            <el-button link @click="download(row, 'markdown')">Markdown</el-button>
          </template></el-table-column>
          <template #empty><EmptyState compact title="暂无审查报告" description="完成一次合同审查后，系统会在这里展示真实生成的报告。" /></template>
        </el-table>
      </section>
    </template>
  </div>
</template>

<style scoped>
.report-center { position:relative; isolation:isolate; display:grid; gap:28px; min-width:0; }.report-center::before { content:""; position:absolute; z-index:-1; top:110px; right:7%; width:480px; height:330px; border-radius:50%; background:radial-gradient(circle,rgba(118,148,255,.16),rgba(180,164,255,.07) 52%,transparent 74%); filter:blur(30px); }
.report-metrics { display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:20px; }.report-metrics :deep(.common-metric-card) { min-height:120px; display:flex; flex-direction:column; justify-content:center; border:1px solid rgba(255,255,255,.38); border-radius:22px; background:rgba(255,255,255,.52); box-shadow:0 10px 40px rgba(25,39,74,.06); backdrop-filter:blur(20px); animation:report-enter .5s ease both; }.report-metrics :deep(.common-metric-card > strong) { order:1; color:#2b3852; font-size:34px; line-height:42px; }.report-metrics :deep(.common-metric-card > span) { order:2; margin:6px 0 0; color:#8792a5; font-size:13px; }
.report-chart-grid { display:grid; grid-template-columns:2fr 1fr; grid-template-rows:repeat(2,1fr); gap:22px; }.chart-panel { min-width:0; padding:20px 22px; border:1px solid rgba(255,255,255,.38); border-radius:24px; background:rgba(255,255,255,.5); box-shadow:0 10px 40px rgba(27,42,76,.06); backdrop-filter:blur(20px); animation:report-enter .58s ease both; transition:transform .22s ease,box-shadow .22s ease; }.chart-panel:hover { transform:translateY(-3px); box-shadow:0 16px 48px rgba(30,47,85,.1); }.chart-panel:first-child { grid-row:1 / span 2; }.chart-panel header h2 { margin:0; color:#354158; font-size:15px; }.chart-panel header p { margin:4px 0 0; color:#929bad; font-size:12px; }.chart-panel :deep(.dashboard-chart) { width:100%; height:210px; }.chart-panel:first-child :deep(.dashboard-chart) { height:372px; }.chart-panel :deep(.common-state) { min-height:145px; border:0; background:transparent; box-shadow:none; }.chart-panel:first-child :deep(.common-state) { min-height:340px; }
.report-filters { display:grid; grid-template-columns:minmax(280px,1.8fr) minmax(145px,.7fr) minmax(165px,.8fr) auto; align-items:center; gap:12px; padding:18px; border:1px solid rgba(255,255,255,.4); border-radius:22px; background:rgba(255,255,255,.48); box-shadow:0 10px 36px rgba(29,43,76,.05); backdrop-filter:blur(20px); }.report-filters :deep(.el-input__wrapper) { height:48px; padding:0 17px; border:0; border-radius:16px; background:rgba(255,255,255,.62); box-shadow:0 7px 24px rgba(42,58,96,.05); }.report-filters :deep(.el-select__wrapper) { border:0; border-radius:999px; background:rgba(255,255,255,.58); box-shadow:inset 0 0 0 1px rgba(255,255,255,.52); }.report-filters span { color:#929bad; font-size:12px; white-space:nowrap; }
.table-panel { overflow:hidden; padding:10px 12px 4px; border:1px solid rgba(255,255,255,.4); border-radius:24px; background:rgba(255,255,255,.48); box-shadow:0 10px 40px rgba(30,44,76,.055); backdrop-filter:blur(20px); }.table-panel :deep(.el-table) { --el-table-bg-color:transparent; --el-table-tr-bg-color:transparent; --el-table-header-bg-color:transparent; --el-table-row-hover-bg-color:rgba(255,255,255,.64); background:transparent; }.table-panel :deep(.el-table__inner-wrapper::before) { display:none; }.table-panel :deep(th.el-table__cell) { color:#949daf; font-size:12px; font-weight:550; }.table-panel :deep(td.el-table__cell) { height:62px; border-bottom-color:rgba(143,156,181,.1); }
.table-panel :deep(.common-empty-state) { position:relative; width:min(430px,calc(100% - 40px)); min-height:220px; margin:32px auto 42px; border:1px solid rgba(255,255,255,.32); border-radius:32px; background:linear-gradient(145deg,rgba(255,255,255,.3),rgba(237,242,255,.16)); box-shadow:0 18px 56px rgba(38,53,89,.09),inset 0 1px 0 rgba(255,255,255,.65); backdrop-filter:blur(22px) saturate(140%); transition:transform .24s ease,box-shadow .24s ease; }.table-panel :deep(.common-empty-state::before) { content:""; position:absolute; inset:22% 18%; z-index:-1; border-radius:50%; background:radial-gradient(circle,rgba(116,151,255,.2),rgba(171,154,255,.08),transparent 70%); filter:blur(18px); }.table-panel :deep(.common-empty-state:hover) { transform:translateY(-3px); box-shadow:0 24px 64px rgba(38,53,89,.13),inset 0 1px 0 rgba(255,255,255,.78); }.table-panel :deep(.common-state__icon) { width:66px; height:66px; border:1px solid rgba(255,255,255,.52); background:rgba(255,255,255,.48); box-shadow:0 10px 28px rgba(65,89,154,.12),inset 0 1px 0 rgba(255,255,255,.8); backdrop-filter:blur(16px); }.table-panel :deep(.common-empty-state h2) { color:#44506a; font-size:17px; }.table-panel :deep(.common-empty-state p) { max-width:300px; color:#929bad; line-height:1.75; }
@keyframes report-enter { from { opacity:0; transform:translateY(20px); } to { opacity:1; transform:translateY(0); } }
@media (max-width:1100px) { .report-metrics { grid-template-columns:repeat(2,1fr); }.report-chart-grid { grid-template-columns:1fr; grid-template-rows:auto; }.chart-panel:first-child { grid-row:auto; }.chart-panel:first-child :deep(.dashboard-chart) { height:300px; }.report-filters { grid-template-columns:1fr 1fr; } }
@media (max-width:640px) { .report-metrics,.report-filters { grid-template-columns:1fr; }.report-center { gap:20px; }.chart-panel,.table-panel,.report-filters { border-radius:18px; } }
@media (prefers-reduced-motion:reduce) { .report-metrics :deep(.common-metric-card),.chart-panel { animation:none; transition:none; } }
</style>
