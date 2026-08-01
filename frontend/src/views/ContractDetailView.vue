<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Download, Upload } from '@element-plus/icons-vue'
import PageHeader from '../components/PageHeader.vue'
import EmptyState from '../components/EmptyState.vue'
import ErrorState from '../components/ErrorState.vue'
import LoadingState from '../components/LoadingState.vue'
import RiskLevelTag from '../components/RiskLevelTag.vue'
import StatusTag from '../components/StatusTag.vue'
import {
  archiveContract,
  downloadContractVersion,
  downloadReviewReport,
  fetchContractOverview,
  restoreContract,
  startContractReview,
  uploadContractVersion,
  type ContractDetail,
  type ContractVersion,
} from '../services/contracts'

const route = useRoute()
const router = useRouter()
const contractId = computed(() => String(route.params.contractId))
const detail = ref<ContractDetail | null>(null)
const loading = ref(false)
const error = ref('')
const acting = ref(false)
const uploadVisible = ref(false)
const uploadFile = ref<File | null>(null)
const changeNote = ref('')
let controller: AbortController | null = null

const categories: Record<string, string> = {
  software_development: '软件开发合同', technical_service: '技术服务合同',
  information_system: '信息系统建设合同', software_outsourcing: '软件外包合同',
  procurement: '采购合同', sales: '销售合同', labor: '劳动合同', lease: '租赁合同',
  nda: '保密协议', service: '服务合同', other: '其他',
}
const statusLabels: Record<string, string> = { draft: '草稿', reviewing: '审查中', legal_review: '法务复核', manager_review: '主管审批', archived: '已归档', deleted: '已删除' }
const actionLabels: Record<string, string> = {
  'contracts.create': '创建合同', 'contracts.update': '更新合同',
  'contracts.archive': '归档合同', 'contracts.restore': '恢复合同',
  'contracts.delete': '删除合同', 'contracts.version.create': '创建版本',
  'contracts.version.upload': '上传新版本', 'contracts.version.download': '下载原文件',
  'contracts.review.start': '发起审查',
}

const contract = computed(() => detail.value?.contract)
const currentVersion = computed(() => contract.value?.versions.at(-1))
const recentReviews = computed(() => detail.value?.recent_reviews || [])
const reports = computed(() => detail.value?.reports || [])
const auditLogs = computed(() => detail.value?.audit_logs || [])

async function load() {
  controller?.abort()
  controller = new AbortController()
  loading.value = true
  error.value = ''
  try { detail.value = await fetchContractOverview(contractId.value, controller.signal) }
  catch (cause: any) {
    if (cause?.code !== 'ERR_CANCELED') error.value = cause?.response?.data?.message || cause?.response?.data?.detail || '合同详情加载失败'
  } finally { loading.value = false }
}

async function submitUpload() {
  if (!uploadFile.value) return ElMessage.warning('请选择合同文件')
  acting.value = true
  try {
    await uploadContractVersion(contractId.value, uploadFile.value, changeNote.value.trim() || undefined)
    uploadVisible.value = false
    uploadFile.value = null
    changeNote.value = ''
    ElMessage.success('新版本已上传，历史版本保持不变')
    await load()
  } catch (cause: any) { ElMessage.error(cause?.response?.data?.message || cause?.response?.data?.detail || '上传失败') }
  finally { acting.value = false }
}

async function review(version = currentVersion.value) {
  if (!version?.file_size) return ElMessage.warning('该版本没有可审查的原文件')
  acting.value = true
  try {
    const result = await startContractReview(contractId.value, version.id)
    const reviewId = result.result_summary?.review_id
    ElMessage.success(reviewId ? '审查已完成' : '审查任务已创建')
    await router.push(reviewId ? `/reader/${reviewId}` : `/review-tasks?task_id=${result.task_id}`)
  } catch (cause: any) { ElMessage.error(cause?.response?.data?.message || cause?.response?.data?.detail || '审查失败') }
  finally { acting.value = false }
}

async function download(version = currentVersion.value) {
  if (!version?.file_size) return ElMessage.warning('该版本没有可下载的原文件')
  try { await downloadContractVersion(contractId.value, version) }
  catch { ElMessage.error('原文件下载失败') }
}

async function toggleArchive() {
  if (!contract.value) return
  const restoring = ['archived', 'deleted'].includes(contract.value.status)
  await ElMessageBox.confirm(`确认${restoring ? '恢复' : '归档'}合同“${contract.value.title}”吗？`, '操作确认', { type: 'warning' })
  acting.value = true
  try {
    if (restoring) await restoreContract(contractId.value)
    else await archiveContract(contractId.value)
    ElMessage.success(restoring ? '合同已恢复' : '合同已归档')
    await load()
  } finally { acting.value = false }
}

function formatDate(value?: string | null) { return value ? new Date(value).toLocaleString('zh-CN', { hour12: false }) : '暂无数据' }
function formatSize(value?: number | null) {
  if (value === null || value === undefined) return '暂无数据'
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`
  return `${(value / 1024 / 1024).toFixed(2)} MB`
}
function money() {
  const value = contract.value?.amount
  return value === null || value === undefined ? '暂无数据' : `${contract.value?.currency || 'CNY'} ${Number(value).toLocaleString('zh-CN', { minimumFractionDigits: 2 })}`
}
function parseLabel(value: string) { return ({ pending: '待解析', ready: '已解析', failed: '解析失败', unavailable: '未解析' } as Record<string, string>)[value] || value }
function versionType(value: string) { return ({ original: '原始版本', modified: '修改版本', re_review: '复审版本', final: '最终版本' } as Record<string, string>)[value] || value }

onMounted(load)
onBeforeUnmount(() => controller?.abort())
</script>

<template>
  <div class="contract-detail">
    <PageHeader :title="contract?.title || '合同详情'" description="查看合同档案、不可变版本历史、审查记录与操作留痕。" eyebrow="CONTRACT PROFILE">
      <template #actions>
        <el-button @click="router.push('/contracts')">返回列表</el-button>
        <el-button :icon="Upload" @click="uploadVisible=true">上传新版本</el-button>
        <el-button :icon="Download" @click="download()">下载</el-button>
        <el-button type="primary" :loading="acting" @click="review()">新建审查</el-button>
        <el-button :loading="acting" @click="toggleArchive">{{ ['archived','deleted'].includes(contract?.status || '') ? '恢复' : '归档' }}</el-button>
      </template>
    </PageHeader>

    <LoadingState v-if="loading && !detail" title="正在加载合同档案" />
    <ErrorState v-else-if="error" title="合同详情加载失败" :description="error" @retry="load" />
    <template v-else-if="contract">
      <section class="summary-grid">
        <div class="panel summary-card"><span>当前版本</span><strong>{{ contract.current_version ? `V${contract.current_version}` : '暂无' }}</strong><small>{{ currentVersion?.file_name || '尚未上传文件' }}</small></div>
        <div class="panel summary-card"><span>最新风险</span><RiskLevelTag v-if="contract.latest_risk_level" :level="contract.latest_risk_level"/><strong v-else>暂无数据</strong><small>{{ contract.risk_count === null || contract.risk_count === undefined ? '尚无风险统计' : `${contract.risk_count} 个风险点` }}</small></div>
        <div class="panel summary-card"><span>合同状态</span><StatusTag :label="statusLabels[contract.status] || contract.status" :tone="contract.status === 'archived' ? 'success' : contract.status === 'deleted' ? 'danger' : 'info'"/><small>更新于 {{ formatDate(contract.updated_at) }}</small></div>
        <div class="panel summary-card"><span>历史审查</span><strong>{{ recentReviews.length }}</strong><small>当前关联审查记录</small></div>
      </section>

      <el-tabs class="panel detail-tabs">
        <el-tab-pane label="基本信息">
          <el-descriptions :column="2" border>
            <el-descriptions-item label="合同名称">{{ contract.title }}</el-descriptions-item><el-descriptions-item label="合同类型">{{ categories[contract.category] || contract.category }}</el-descriptions-item>
            <el-descriptions-item label="相对方">{{ contract.counterparty || '暂无数据' }}</el-descriptions-item><el-descriptions-item label="合同金额">{{ money() }}</el-descriptions-item>
            <el-descriptions-item label="所有者">{{ contract.owner_name || contract.created_by }}</el-descriptions-item><el-descriptions-item label="创建时间">{{ formatDate(contract.created_at) }}</el-descriptions-item>
            <el-descriptions-item label="说明" :span="2">{{ contract.description || '暂无数据' }}</el-descriptions-item>
          </el-descriptions>
        </el-tab-pane>
        <el-tab-pane :label="`版本历史（${contract.versions.length}）`">
          <el-table :data="[...contract.versions].reverse()" row-key="id">
            <el-table-column label="版本号" width="90"><template #default="{ row }">V{{ row.version_no }}</template></el-table-column>
            <el-table-column prop="file_name" label="原文件名" min-width="220"/>
            <el-table-column label="类型" width="110"><template #default="{ row }">{{ versionType(row.version_type) }}</template></el-table-column>
            <el-table-column label="大小" width="110"><template #default="{ row }">{{ formatSize(row.file_size) }}</template></el-table-column>
            <el-table-column prop="created_by" label="上传人" min-width="150"/>
            <el-table-column label="上传时间" width="180"><template #default="{ row }">{{ formatDate(row.created_at) }}</template></el-table-column>
            <el-table-column label="解析状态" width="100"><template #default="{ row }">{{ parseLabel(row.parse_status) }}</template></el-table-column>
            <el-table-column label="审查状态" width="100"><template #default="{ row }">{{ row.review_status === 'completed' ? '已完成' : '未审查' }}</template></el-table-column>
            <el-table-column label="风险等级" width="110"><template #default="{ row }"><RiskLevelTag v-if="row.risk_level" :level="row.risk_level"/><span v-else>暂无</span></template></el-table-column>
            <el-table-column label="操作" width="190"><template #default="{ row }"><el-button link type="primary" @click="download(row)">下载</el-button><el-button link type="primary" :loading="acting" @click="review(row)">审查</el-button></template></el-table-column>
            <template #empty><EmptyState compact title="尚无版本" description="上传首个合同文件后，版本将显示在这里。" /></template>
          </el-table>
        </el-tab-pane>
        <el-tab-pane :label="`最近审查（${recentReviews.length}）`">
          <el-table :data="recentReviews"><el-table-column prop="review_id" label="审查编号" min-width="200"/><el-table-column label="风险等级" width="110"><template #default="{ row }"><RiskLevelTag v-if="row.risk_level" :level="row.risk_level"/><span v-else>暂无</span></template></el-table-column><el-table-column label="风险点" width="100"><template #default="{ row }">{{ row.risk_count ?? '暂无' }}</template></el-table-column><el-table-column label="审查时间" width="190"><template #default="{ row }">{{ formatDate(row.created_at) }}</template></el-table-column><el-table-column label="操作" width="150"><template #default="{ row }"><el-button link type="primary" @click="router.push(`/reader/${row.review_id}`)">查看结果</el-button></template></el-table-column><template #empty><EmptyState compact title="暂无审查记录" description="对合同版本发起审查后，记录会显示在这里。" /></template></el-table>
        </el-tab-pane>
        <el-tab-pane :label="`历史报告（${reports.length}）`">
          <el-table :data="reports"><el-table-column prop="review_id" label="报告编号"/><el-table-column label="生成时间"><template #default="{ row }">{{ formatDate(row.created_at) }}</template></el-table-column><el-table-column label="操作" width="180"><template #default="{ row }"><el-button link type="primary" @click="router.push(`/reader/${row.review_id}`)">查看</el-button><el-button link @click="downloadReviewReport(row.review_id)">导出PDF</el-button></template></el-table-column><template #empty><EmptyState compact title="暂无历史报告" description="完成合同审查后可查看和导出报告。" /></template></el-table>
        </el-tab-pane>
        <el-tab-pane :label="`操作日志（${auditLogs.length}）`">
          <el-table :data="auditLogs"><el-table-column label="操作" min-width="180"><template #default="{ row }">{{ actionLabels[row.action] || row.action }}</template></el-table-column><el-table-column prop="actor_id" label="操作人" min-width="180"/><el-table-column label="时间" width="190"><template #default="{ row }">{{ formatDate(row.created_at) }}</template></el-table-column><template #empty><EmptyState compact title="暂无操作日志" description="可审计操作发生后将显示在这里。" /></template></el-table>
        </el-tab-pane>
      </el-tabs>
    </template>

    <el-dialog v-model="uploadVisible" title="上传合同新版本" width="560px" destroy-on-close>
      <el-alert title="新版本不会覆盖历史文件，本阶段不提供版本文本差异。" type="info" :closable="false" show-icon />
      <el-form label-position="top" class="upload-form"><el-form-item label="合同文件" required><el-upload drag :auto-upload="false" :limit="1" :on-change="(item:any) => uploadFile = item.raw" :on-remove="() => uploadFile = null" accept=".pdf,.doc,.docx,.png,.jpg,.jpeg,.tif,.tiff,.bmp"><el-icon class="upload-icon"><Upload /></el-icon><div>拖拽文件到此处，或点击选择</div><template #tip>支持 PDF、Word、扫描图片，最大 50MB</template></el-upload></el-form-item><el-form-item label="版本说明"><el-input v-model="changeNote" type="textarea" :rows="3" maxlength="1000" show-word-limit /></el-form-item></el-form>
      <template #footer><el-button @click="uploadVisible=false">取消</el-button><el-button type="primary" :loading="acting" @click="submitUpload">上传新版本</el-button></template>
    </el-dialog>
  </div>
</template>

<style scoped>
.contract-detail { position:relative; isolation:isolate; display:grid; gap:28px; min-width:0; }.contract-detail::before { content:""; position:absolute; z-index:-1; top:70px; left:10%; width:500px; height:350px; border-radius:50%; background:radial-gradient(circle,rgba(112,150,255,.16),rgba(178,163,255,.07) 50%,transparent 73%); filter:blur(30px); pointer-events:none; }
.summary-grid { display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:20px; }.summary-card { display:flex; min-height:138px; flex-direction:column; align-items:flex-start; justify-content:center; gap:8px; padding:22px; border:1px solid rgba(255,255,255,.4); border-radius:22px; background:linear-gradient(145deg,rgba(255,255,255,.6),rgba(242,246,255,.4)); box-shadow:0 10px 40px rgba(26,41,76,.06),inset 0 1px 0 rgba(255,255,255,.72); backdrop-filter:blur(20px) saturate(130%); animation:detail-enter .5s ease both; transition:transform .22s ease,box-shadow .22s ease; }.summary-card:hover { transform:translateY(-3px); box-shadow:0 16px 48px rgba(35,52,90,.1),inset 0 1px 0 rgba(255,255,255,.8); }.summary-card > span:first-child { order:2; margin-top:2px; color:#8994a8; font-size:13px; }.summary-card strong { order:1; color:#2b3852; font-size:32px; line-height:38px; letter-spacing:-.025em; }.summary-card > .risk-level-tag,.summary-card > .status-tag { order:1; }.summary-card small { order:3; color:#9aa4b5; font-size:12px; }
.detail-tabs { padding:16px 22px 24px; overflow:hidden; border:1px solid rgba(255,255,255,.4); border-radius:24px; background:rgba(255,255,255,.5); box-shadow:0 12px 44px rgba(29,43,76,.06); backdrop-filter:blur(22px) saturate(130%); animation:detail-enter .6s ease both; }.detail-tabs :deep(.el-tabs__nav-wrap::after) { height:1px; background:rgba(133,148,176,.13); }.detail-tabs :deep(.el-tabs__item) { color:#8b95a8; }.detail-tabs :deep(.el-tabs__item.is-active) { color:#4d69ad; }.detail-tabs :deep(.el-tabs__active-bar) { height:2px; border-radius:2px; background:#6987d8; }.detail-tabs :deep(.el-table) { --el-table-bg-color:transparent; --el-table-tr-bg-color:transparent; --el-table-header-bg-color:transparent; --el-table-row-hover-bg-color:rgba(255,255,255,.64); background:transparent; }.detail-tabs :deep(.el-table__inner-wrapper::before) { display:none; }.detail-tabs :deep(th.el-table__cell) { color:#929cad; font-size:12px; font-weight:550; }.detail-tabs :deep(td.el-table__cell) { height:60px; border-bottom-color:rgba(143,156,181,.1); }.detail-tabs :deep(.el-descriptions__body),.detail-tabs :deep(.el-descriptions__table) { background:transparent; }.detail-tabs :deep(.el-descriptions__label.el-descriptions__cell) { color:#8490a5; background:rgba(245,247,252,.4); }.detail-tabs :deep(.el-descriptions__content.el-descriptions__cell) { background:rgba(255,255,255,.3); }
.upload-form { margin-top: var(--space-5); }
.upload-icon { margin-bottom: var(--space-2); color: var(--primary); font-size: 28px; }
@keyframes detail-enter { from { opacity:0; transform:translateY(20px); } to { opacity:1; transform:translateY(0); } }
@media (max-width: 1100px) { .summary-grid { grid-template-columns: repeat(2, 1fr); } }
@media (max-width:680px) { .contract-detail { gap:20px; }.summary-grid { grid-template-columns:1fr; }.detail-tabs { border-radius:18px; padding-inline:14px; } }
@media (prefers-reduced-motion:reduce) { .summary-card,.detail-tabs { animation:none; transition:none; } }
</style>
