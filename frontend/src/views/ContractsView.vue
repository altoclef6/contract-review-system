<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Delete, Download, MoreFilled, Plus, Refresh, Search, Upload } from '@element-plus/icons-vue'
import PageHeader from '../components/PageHeader.vue'
import EmptyState from '../components/EmptyState.vue'
import ErrorState from '../components/ErrorState.vue'
import RiskLevelTag from '../components/RiskLevelTag.vue'
import StatusTag from '../components/StatusTag.vue'
import {
  archiveContract,
  createContract,
  deleteContract,
  downloadContractVersion,
  fetchContracts,
  restoreContract,
  startContractReview,
  uploadContractVersion,
  type ContractRecord,
} from '../services/contracts'

const router = useRouter()
const loading = ref(false)
const error = ref('')
const items = ref<ContractRecord[]>([])
const total = ref(0)
const dialogVisible = ref(false)
const uploadAfterCreate = ref(false)
const submitting = ref(false)
const actionId = ref('')
const selectedFile = ref<File | null>(null)
let controller: AbortController | null = null

const filters = reactive({
  page: 1,
  page_size: 10,
  search: '',
  category: '',
  status: '',
  risk_level: '',
  sort_order: 'desc',
})
const form = reactive({ title: '', category: 'software_development', counterparty: '', amount: '', currency: 'CNY', description: '' })

const categories: Record<string, string> = {
  software_development: '软件开发合同', technical_service: '技术服务合同',
  information_system: '信息系统建设合同', software_outsourcing: '软件外包合同',
  procurement: '采购合同', sales: '销售合同', labor: '劳动合同', lease: '租赁合同',
  nda: '保密协议', service: '服务合同', other: '其他',
}
const statuses: Record<string, { label: string; tone: 'neutral' | 'info' | 'success' | 'warning' | 'danger' }> = {
  draft: { label: '草稿', tone: 'neutral' }, reviewing: { label: '审核中', tone: 'info' },
  legal_review: { label: '法务复核', tone: 'warning' }, manager_review: { label: '主管审批', tone: 'warning' },
  completed: { label: '已完成', tone: 'success' }, archived: { label: '已归档', tone: 'success' }, deleted: { label: '已删除', tone: 'danger' },
}

const queryParams = computed(() => ({
  ...filters,
  search: filters.search || undefined,
  category: filters.category || undefined,
  status: filters.status || undefined,
  risk_level: filters.risk_level || undefined,
  sort_by: 'updated_at',
  include_deleted: filters.status === 'deleted',
}))

async function load() {
  controller?.abort()
  controller = new AbortController()
  loading.value = true
  error.value = ''
  try {
    const data = await fetchContracts(queryParams.value, controller.signal)
    items.value = data.items
    total.value = data.total
  } catch (cause: any) {
    if (cause?.code !== 'ERR_CANCELED') error.value = cause?.response?.data?.message || cause?.response?.data?.detail || '合同列表加载失败'
  } finally {
    loading.value = false
  }
}

function search() { filters.page = 1; void load() }
function openCreate(withUpload: boolean) {
  Object.assign(form, { title: '', category: 'software_development', counterparty: '', amount: '', currency: 'CNY', description: '' })
  selectedFile.value = null
  uploadAfterCreate.value = withUpload
  dialogVisible.value = true
}

async function submitCreate() {
  if (!form.title.trim()) return ElMessage.warning('请输入合同名称')
  if (uploadAfterCreate.value && !selectedFile.value) return ElMessage.warning('请选择合同文件')
  submitting.value = true
  try {
    const contract = await createContract({
      title: form.title.trim(), category: form.category, tags: [],
      counterparty: form.counterparty.trim() || null,
      amount: form.amount === '' ? null : form.amount,
      currency: form.currency || null,
      description: form.description.trim() || null,
    })
    if (selectedFile.value) await uploadContractVersion(contract.id, selectedFile.value, '初始上传')
    dialogVisible.value = false
    ElMessage.success(selectedFile.value ? '合同及原文件已创建' : '合同草稿已创建')
    await load()
  } catch (cause: any) {
    ElMessage.error(cause?.response?.data?.message || cause?.response?.data?.detail || '创建失败')
  } finally { submitting.value = false }
}

async function confirmAction(row: ContractRecord, action: 'archive' | 'restore' | 'delete') {
  const labels = { archive: '归档', restore: '恢复', delete: '删除' }
  await ElMessageBox.confirm(`确认${labels[action]}合同“${row.title}”吗？`, `${labels[action]}确认`, { type: action === 'delete' ? 'warning' : 'info' })
  actionId.value = row.id
  try {
    if (action === 'archive') await archiveContract(row.id)
    if (action === 'restore') await restoreContract(row.id)
    if (action === 'delete') await deleteContract(row.id)
    ElMessage.success(`合同已${labels[action]}`)
    await load()
  } catch (cause: any) {
    ElMessage.error(cause?.response?.data?.message || cause?.response?.data?.detail || `${labels[action]}失败`)
  } finally { actionId.value = '' }
}

async function review(row: ContractRecord) {
  const version = row.versions.at(-1)
  if (!version?.file_size) return ElMessage.warning('请先上传可审查的合同版本')
  actionId.value = row.id
  try {
    const result = await startContractReview(row.id, version.id)
    const reviewId = result.result_summary?.review_id
    ElMessage.success(reviewId ? '审查已完成' : '审查任务已创建')
    await router.push(reviewId ? `/reader/${reviewId}` : `/review-tasks?task_id=${result.task_id}`)
  } catch (cause: any) {
    ElMessage.error(cause?.response?.data?.message || cause?.response?.data?.detail || '审查失败')
  } finally { actionId.value = '' }
}

async function download(row: ContractRecord) {
  const version = row.versions.at(-1)
  if (!version?.file_size) return ElMessage.warning('当前合同没有可下载的原文件')
  actionId.value = row.id
  try { await downloadContractVersion(row.id, version) }
  catch { ElMessage.error('原文件下载失败') }
  finally { actionId.value = '' }
}

function money(row: ContractRecord) {
  if (row.amount === null || row.amount === undefined || row.amount === '') return '暂无数据'
  return `${row.currency || 'CNY'} ${Number(row.amount).toLocaleString('zh-CN', { minimumFractionDigits: 2 })}`
}
function formatDate(value: string) { return new Date(value).toLocaleString('zh-CN', { hour12: false }) }
function statusOf(value: string) { return statuses[value] || { label: value, tone: 'neutral' as const } }

onMounted(load)
onBeforeUnmount(() => controller?.abort())
</script>

<template>
  <div class="contract-center">
    <PageHeader title="合同中心" description="统一管理合同档案、版本、审查与归档状态。" eyebrow="CONTRACT CENTER">
      <template #actions>
        <el-button :icon="Refresh" :loading="loading" @click="load">刷新</el-button>
        <el-button :icon="Plus" @click="openCreate(false)">新建</el-button>
        <el-button type="primary" :icon="Upload" @click="openCreate(true)">上传合同</el-button>
      </template>
    </PageHeader>

    <section class="panel filter-panel">
      <div class="contract-search">
        <el-input v-model="filters.search" clearable :prefix-icon="Search" placeholder="搜索合同名称或相对方" @keyup.enter="search" />
        <el-button type="primary" @click="search">查询</el-button>
      </div>
      <div class="contract-filter-pills">
        <el-select v-model="filters.category" clearable placeholder="合同类型"><el-option v-for="(label, value) in categories" :key="value" :label="label" :value="value" /></el-select>
        <el-select v-model="filters.status" clearable placeholder="合同状态"><el-option v-for="(item, value) in statuses" :key="value" :label="item.label" :value="value" /></el-select>
        <el-select v-model="filters.risk_level" clearable placeholder="风险等级"><el-option label="严重" value="严重"/><el-option label="高" value="高"/><el-option label="中" value="中"/><el-option label="低" value="低"/></el-select>
        <el-select v-model="filters.sort_order" aria-label="更新时间排序"><el-option label="最近更新" value="desc"/><el-option label="最早更新" value="asc"/></el-select>
      </div>
    </section>

    <ErrorState v-if="error" title="合同列表加载失败" :description="error" @retry="load" />
    <section v-else class="panel table-panel">
      <el-table v-loading="loading" :data="items" row-key="id">
        <el-table-column prop="title" label="合同名称" min-width="220" fixed="left"><template #default="{ row }"><div class="contract-name"><strong>{{ row.title }}</strong><small>{{ row.owner_name || row.created_by }}</small></div></template></el-table-column>
        <el-table-column label="合同类型" min-width="145"><template #default="{ row }"><span class="type-label">{{ categories[row.category] || row.category }}</span></template></el-table-column>
        <el-table-column label="版本信息" min-width="150"><template #default="{ row }"><div class="version-info"><strong>{{ row.current_version ? `V${row.current_version}` : '暂无版本' }}</strong><small>{{ row.versions.at(-1)?.file_name || '尚未上传文件' }}</small></div></template></el-table-column>
        <el-table-column prop="counterparty" label="相对方" min-width="155"><template #default="{ row }">{{ row.counterparty || '暂无数据' }}</template></el-table-column>
        <el-table-column label="合同金额" min-width="145"><template #default="{ row }"><span class="contract-amount">{{ money(row) }}</span></template></el-table-column>
        <el-table-column label="状态" width="110"><template #default="{ row }"><StatusTag :label="statusOf(row.status).label" :tone="statusOf(row.status).tone" /></template></el-table-column>
        <el-table-column label="风险情况" min-width="185"><template #default="{ row }">
          <div v-if="row.latest_risk_level || row.risk_count !== null && row.risk_count !== undefined" class="risk-summary">
            <RiskLevelTag v-if="row.latest_risk_level" :level="row.latest_risk_level"/>
            <span>{{ row.risk_count === null || row.risk_count === undefined ? '暂无风险统计' : `${row.risk_count} 项风险点` }}</span>
          </div>
          <span v-else class="muted">暂无风险数据</span>
        </template></el-table-column>
        <el-table-column label="操作" width="155" fixed="right"><template #default="{ row }">
          <div class="row-actions">
            <el-button link type="primary" @click="router.push(`/contracts/${row.id}`)">查看详情</el-button>
            <el-dropdown trigger="click" popper-class="contract-action-menu">
              <el-button class="more-action" circle :icon="MoreFilled" :loading="actionId === row.id" aria-label="更多操作" />
              <template #dropdown><el-dropdown-menu>
                <el-dropdown-item @click="review(row)">新建审查</el-dropdown-item>
                <el-dropdown-item :icon="Download" @click="download(row)">下载原文件</el-dropdown-item>
                <el-dropdown-item v-if="!['archived','deleted'].includes(row.status)" divided @click="confirmAction(row,'archive')">归档合同</el-dropdown-item>
                <el-dropdown-item v-if="['archived','deleted'].includes(row.status)" divided @click="confirmAction(row,'restore')">恢复合同</el-dropdown-item>
                <el-dropdown-item v-if="row.status !== 'deleted'" :icon="Delete" @click="confirmAction(row,'delete')">删除合同</el-dropdown-item>
              </el-dropdown-menu></template>
            </el-dropdown>
          </div>
        </template></el-table-column>
        <template #empty><EmptyState compact title="暂无合同" description="当前筛选条件下没有可展示的合同。" /></template>
      </el-table>
      <el-pagination v-model:current-page="filters.page" v-model:page-size="filters.page_size" :total="total" :page-sizes="[10,20,50]" layout="total, sizes, prev, pager, next" @change="load" />
    </section>

    <el-dialog v-model="dialogVisible" :title="uploadAfterCreate ? '上传合同' : '新建合同'" width="600px" destroy-on-close>
      <el-form label-position="top">
        <div class="form-grid"><el-form-item label="合同名称" required><el-input v-model="form.title" maxlength="160" /></el-form-item><el-form-item label="合同类型"><el-select v-model="form.category"><el-option v-for="(label, value) in categories" :key="value" :label="label" :value="value" /></el-select></el-form-item></div>
        <div class="form-grid"><el-form-item label="相对方"><el-input v-model="form.counterparty" maxlength="160" /></el-form-item><el-form-item label="合同金额"><el-input v-model="form.amount" type="number"><template #prepend>{{ form.currency }}</template></el-input></el-form-item></div>
        <el-form-item label="说明"><el-input v-model="form.description" type="textarea" :rows="3" maxlength="1000" show-word-limit /></el-form-item>
        <el-form-item v-if="uploadAfterCreate" label="合同文件" required><el-upload drag :auto-upload="false" :limit="1" :on-change="(item:any) => selectedFile = item.raw" :on-remove="() => selectedFile = null" accept=".pdf,.doc,.docx,.png,.jpg,.jpeg,.tif,.tiff,.bmp"><el-icon class="upload-icon"><Upload /></el-icon><div>拖拽文件到此处，或点击选择</div><template #tip>支持 PDF、Word、扫描图片，最大 50MB</template></el-upload></el-form-item>
      </el-form>
      <template #footer><el-button @click="dialogVisible=false">取消</el-button><el-button type="primary" :loading="submitting" @click="submitCreate">{{ uploadAfterCreate ? '创建并上传' : '创建草稿' }}</el-button></template>
    </el-dialog>
  </div>
</template>

<style scoped>
.contract-center { position:relative; isolation:isolate; display:grid; gap:28px; min-width:0; }.contract-center::before { content:""; position:absolute; z-index:-1; top:80px; right:5%; width:520px; height:360px; border-radius:50%; background:radial-gradient(circle,rgba(113,148,255,.17),rgba(181,164,255,.075) 50%,transparent 73%); filter:blur(30px); pointer-events:none; }
.filter-panel { padding:18px; border:1px solid rgba(255,255,255,.4); border-radius:24px; background:rgba(255,255,255,.48); box-shadow:0 10px 40px rgba(31,46,79,.06); backdrop-filter:blur(20px) saturate(135%); animation:contract-enter .48s ease both; }.contract-search { display:grid; grid-template-columns:minmax(0,1fr) auto; gap:12px; }.contract-search :deep(.el-input__wrapper) { height:48px; padding:0 18px; border:0; border-radius:16px; background:rgba(255,255,255,.65); box-shadow:0 8px 28px rgba(45,62,100,.055); }.contract-search :deep(.el-button) { height:48px; padding-inline:25px; border:0; border-radius:16px; background:linear-gradient(135deg,#4777db,#6d70d8); box-shadow:0 8px 22px rgba(75,104,190,.18); }.contract-filter-pills { display:flex; flex-wrap:wrap; gap:10px; margin-top:14px; }.contract-filter-pills > * { width:auto; min-width:138px; flex:0 1 180px; }.contract-filter-pills :deep(.el-select__wrapper) { min-height:38px; border:0; border-radius:999px; background:rgba(255,255,255,.55); box-shadow:inset 0 0 0 1px rgba(255,255,255,.52); }
.table-panel { overflow:hidden; padding:10px 12px 4px; border:1px solid rgba(255,255,255,.4); border-radius:24px; background:rgba(255,255,255,.48); box-shadow:0 10px 40px rgba(30,44,76,.055); backdrop-filter:blur(20px); animation:contract-enter .58s ease both; }.table-panel :deep(.el-table) { --el-table-bg-color:transparent; --el-table-tr-bg-color:transparent; --el-table-header-bg-color:transparent; --el-table-row-hover-bg-color:rgba(255,255,255,.65); background:transparent; }.table-panel :deep(.el-table__inner-wrapper::before) { display:none; }.table-panel :deep(th.el-table__cell) { height:46px; padding:8px 0; border-bottom-color:rgba(143,156,181,.12); color:#929cad; font-size:12px; font-weight:550; }.table-panel :deep(td.el-table__cell) { height:68px; padding:10px 0; border-bottom-color:rgba(143,156,181,.1); vertical-align:middle; }.table-panel :deep(.el-table__cell .cell) { display:flex; align-items:center; min-height:44px; padding:0 14px; line-height:1.45; }.table-panel :deep(.el-table__row) { transition:background .18s ease; }.table-panel :deep(.el-pagination) { justify-content:flex-end; padding:18px 16px 14px; border-top:0; }
.contract-name,.version-info { min-width:0; display:flex; flex-direction:column; justify-content:center; }.contract-name strong { overflow:hidden; color:#344158; font-size:14px; font-weight:650; text-overflow:ellipsis; white-space:nowrap; }.contract-name small,.version-info small { max-width:180px; margin-top:4px; overflow:hidden; color:#9aa4b5; font-size:11px; text-overflow:ellipsis; white-space:nowrap; }.version-info strong { color:#53637f; font-size:13px; font-weight:650; }.type-label { color:#59667d; }.contract-amount { color:#46546c; font-variant-numeric:tabular-nums; }.risk-summary { display:flex; align-items:center; gap:9px; white-space:nowrap; }.risk-summary > span { color:#7f8a9e; font-size:12px; }.row-actions { width:100%; display:flex; align-items:center; justify-content:flex-end; gap:8px; }.more-action { width:32px; min-height:32px; height:32px; padding:0; border:1px solid rgba(128,145,176,.16); color:#71809a; background:rgba(255,255,255,.48); box-shadow:none; }.more-action:hover { border-color:rgba(104,130,190,.24); color:#526ea9; background:rgba(255,255,255,.78); }
.table-panel :deep(.common-empty-state) { width:min(420px,calc(100% - 32px)); min-height:190px; margin:28px auto 38px; border:1px solid rgba(255,255,255,.32); border-radius:30px; background:rgba(255,255,255,.24); box-shadow:0 18px 54px rgba(38,53,89,.08); backdrop-filter:blur(20px); transition:transform .22s ease,box-shadow .22s ease; }.table-panel :deep(.common-empty-state:hover) { transform:translateY(-3px); box-shadow:0 24px 62px rgba(38,53,89,.12); }.table-panel :deep(.common-state__icon) { width:62px; height:62px; border:1px solid rgba(255,255,255,.5); background:rgba(255,255,255,.48); box-shadow:0 10px 28px rgba(65,89,154,.11); }
.muted { color: var(--text-muted); }
.form-grid { display: grid; grid-template-columns: 1fr 1fr; gap: var(--space-4); }
.upload-icon { margin-bottom: var(--space-2); color: var(--primary); font-size: 28px; }
@keyframes contract-enter { from { opacity:0; transform:translateY(20px); } to { opacity:1; transform:translateY(0); } }
@media (max-width:720px) { .contract-center { gap:20px; }.contract-search { grid-template-columns:1fr; }.contract-filter-pills > * { flex:1 1 100%; }.filter-panel,.table-panel { border-radius:18px; }.form-grid { grid-template-columns:1fr; } }
@media (prefers-reduced-motion:reduce) { .filter-panel,.table-panel { animation:none; transition:none; } }
</style>
