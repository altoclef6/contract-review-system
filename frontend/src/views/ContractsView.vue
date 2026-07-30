<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Delete, Download, Plus, Refresh, Upload } from '@element-plus/icons-vue'
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
  draft: { label: '草稿', tone: 'neutral' }, reviewing: { label: '审查中', tone: 'info' },
  legal_review: { label: '法务复核', tone: 'warning' }, manager_review: { label: '主管审批', tone: 'warning' },
  archived: { label: '已归档', tone: 'success' }, deleted: { label: '已删除', tone: 'danger' },
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
      <el-input v-model="filters.search" clearable placeholder="搜索合同名称或相对方" @keyup.enter="search" />
      <el-select v-model="filters.category" clearable placeholder="合同类型"><el-option v-for="(label, value) in categories" :key="value" :label="label" :value="value" /></el-select>
      <el-select v-model="filters.status" clearable placeholder="合同状态"><el-option v-for="(item, value) in statuses" :key="value" :label="item.label" :value="value" /></el-select>
      <el-select v-model="filters.risk_level" clearable placeholder="风险等级"><el-option label="严重" value="严重"/><el-option label="高" value="高"/><el-option label="中" value="中"/><el-option label="低" value="低"/></el-select>
      <el-select v-model="filters.sort_order" aria-label="更新时间排序"><el-option label="最近更新" value="desc"/><el-option label="最早更新" value="asc"/></el-select>
      <el-button type="primary" @click="search">查询</el-button>
    </section>

    <ErrorState v-if="error" title="合同列表加载失败" :description="error" @retry="load" />
    <section v-else class="panel table-panel">
      <el-table v-loading="loading" :data="items" row-key="id">
        <el-table-column prop="title" label="合同名称" min-width="220" fixed="left"><template #default="{ row }"><el-button link type="primary" @click="router.push(`/contracts/${row.id}`)">{{ row.title }}</el-button></template></el-table-column>
        <el-table-column label="合同类型" width="150"><template #default="{ row }">{{ categories[row.category] || row.category }}</template></el-table-column>
        <el-table-column label="当前版本" width="90"><template #default="{ row }">{{ row.current_version ? `V${row.current_version}` : '暂无' }}</template></el-table-column>
        <el-table-column prop="counterparty" label="相对方" min-width="160"><template #default="{ row }">{{ row.counterparty || '暂无数据' }}</template></el-table-column>
        <el-table-column label="合同金额" width="150"><template #default="{ row }">{{ money(row) }}</template></el-table-column>
        <el-table-column label="所有者" width="130"><template #default="{ row }">{{ row.owner_name || row.created_by }}</template></el-table-column>
        <el-table-column label="状态" width="110"><template #default="{ row }"><StatusTag :label="statusOf(row.status).label" :tone="statusOf(row.status).tone" /></template></el-table-column>
        <el-table-column label="最新风险" width="110"><template #default="{ row }"><RiskLevelTag v-if="row.latest_risk_level" :level="row.latest_risk_level"/><span v-else class="muted">暂无数据</span></template></el-table-column>
        <el-table-column label="风险点" width="90"><template #default="{ row }">{{ row.risk_count === null || row.risk_count === undefined ? '暂无' : `${row.risk_count}项` }}</template></el-table-column>
        <el-table-column label="更新时间" width="180"><template #default="{ row }">{{ formatDate(row.updated_at) }}</template></el-table-column>
        <el-table-column label="操作" width="310" fixed="right"><template #default="{ row }">
          <el-button link type="primary" @click="router.push(`/contracts/${row.id}`)">查看详情</el-button>
          <el-button link type="primary" :loading="actionId === row.id" @click="review(row)">新建审查</el-button>
          <el-button link :icon="Download" @click="download(row)">下载</el-button>
          <el-dropdown trigger="click"><el-button link>更多</el-button><template #dropdown><el-dropdown-menu>
            <el-dropdown-item v-if="!['archived','deleted'].includes(row.status)" @click="confirmAction(row,'archive')">归档</el-dropdown-item>
            <el-dropdown-item v-if="['archived','deleted'].includes(row.status)" @click="confirmAction(row,'restore')">恢复</el-dropdown-item>
            <el-dropdown-item v-if="row.status !== 'deleted'" :icon="Delete" divided @click="confirmAction(row,'delete')">删除</el-dropdown-item>
          </el-dropdown-menu></template></el-dropdown>
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
.contract-center { display: grid; gap: var(--space-6); min-width: 0; }
.filter-panel { display: grid; grid-template-columns: minmax(220px, 1.5fr) repeat(4, minmax(130px, 1fr)) auto; gap: var(--space-3); padding: var(--space-5); }
.table-panel { overflow: hidden; }
.table-panel :deep(.el-pagination) { justify-content: flex-end; padding: var(--space-5); border-top: 1px solid var(--border); }
.muted { color: var(--text-muted); }
.form-grid { display: grid; grid-template-columns: 1fr 1fr; gap: var(--space-4); }
.upload-icon { margin-bottom: var(--space-2); color: var(--primary); font-size: 28px; }
@media (max-width: 1180px) { .filter-panel { grid-template-columns: repeat(3, minmax(0, 1fr)); } }
@media (max-width: 720px) { .filter-panel, .form-grid { grid-template-columns: 1fr; } }
</style>
