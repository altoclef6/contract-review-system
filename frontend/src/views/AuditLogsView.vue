<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { Refresh, Search } from '@element-plus/icons-vue'
import EmptyState from '../components/EmptyState.vue'
import ErrorState from '../components/ErrorState.vue'
import PageHeader from '../components/PageHeader.vue'
import { api } from '../api'

interface AuditRecord {
  action: string
  actor_id?: string | null
  operator_name: string
  operator_role: string
  target?: string | null
  metadata?: Record<string, unknown>
  ip_address?: string | null
  success?: boolean
  created_at: string
}

const loading = ref(false)
const error = ref('')
const records = ref<AuditRecord[]>([])
const detail = ref<AuditRecord>()
const detailVisible = ref(false)
const currentPage = ref(1)
const pageSize = ref(15)
const filters = reactive({ operator: '', module: '', status: '', dates: [] as string[] })

const actionLabels: Record<string, string> = {
  'auth.login': '登录系统', 'auth.register': '创建账号', 'auth.change_password': '修改密码',
  'contracts.create': '新建合同', 'contracts.version.create': '上传合同版本',
  'review_tasks.create': '发起 AI 审查', 'reviews.create': '执行合同审查',
  'chats.ask': '咨询 AI 助手', 'models.create': '添加模型配置', 'models.activate': '切换默认模型',
  'admin.user.role': '修改员工角色', 'admin.user.disabled': '停用员工账号',
}
const roleLabels: Record<string, string> = { admin: '管理员', legal: '法务', employee: '员工', system: '系统' }

function moduleOf(action: string) {
  const prefix = action.split('.')[0]
  return ({ auth: '账号安全', contracts: '合同管理', review_tasks: '智能审查', reviews: '智能审查', chats: 'AI 助手', models: '模型配置', admin: '员工权限', workflows: '审批流程', risks: '风险台账' } as Record<string, string>)[prefix] || '系统管理'
}

const filtered = computed(() => records.value.filter((item) => {
  const operatorMatched = !filters.operator || item.operator_name.toLowerCase().includes(filters.operator.toLowerCase())
  const moduleMatched = !filters.module || moduleOf(item.action) === filters.module
  const statusMatched = !filters.status || (filters.status === 'success' ? item.success !== false : item.success === false)
  const timestamp = new Date(item.created_at).getTime()
  const dateMatched = filters.dates.length !== 2 || (timestamp >= new Date(filters.dates[0]).getTime() && timestamp <= new Date(filters.dates[1]).getTime() + 86_399_999)
  return operatorMatched && moduleMatched && statusMatched && dateMatched
}))
const pagedRecords = computed(() => filtered.value.slice((currentPage.value - 1) * pageSize.value, currentPage.value * pageSize.value))

async function load() {
  loading.value = true
  error.value = ''
  try {
    records.value = (await api.get('/admin/audit-logs', { params: { limit: 300 } })).data.data
  } catch (cause: any) {
    error.value = cause?.response?.data?.message || cause?.response?.data?.detail || '操作日志加载失败'
  } finally { loading.value = false }
}

function resetFilters() {
  Object.assign(filters, { operator: '', module: '', status: '', dates: [] })
}
function showDetail(row: AuditRecord) { detail.value = row; detailVisible.value = true }
function formatDate(value: string) { return new Date(value).toLocaleString('zh-CN', { hour12: false }) }

onMounted(load)
watch(filters, () => { currentPage.value = 1 })
</script>

<template>
  <div class="audit-page">
    <PageHeader title="操作日志" description="追踪登录、合同审查与系统配置等关键操作，便于安全审计与问题回溯。" eyebrow="AUDIT LOG">
      <template #actions><el-button :icon="Refresh" :loading="loading" @click="load">刷新日志</el-button></template>
    </PageHeader>

    <section class="panel audit-filters">
      <el-input v-model="filters.operator" clearable placeholder="搜索操作人" :prefix-icon="Search" />
      <el-date-picker v-model="filters.dates" type="daterange" value-format="YYYY-MM-DD" range-separator="至" start-placeholder="开始日期" end-placeholder="结束日期" />
      <el-select v-model="filters.module" clearable placeholder="全部模块"><el-option v-for="name in ['账号安全','合同管理','智能审查','风险台账','AI 助手','员工权限','模型配置','系统管理']" :key="name" :label="name" :value="name" /></el-select>
      <el-select v-model="filters.status" clearable placeholder="全部状态"><el-option label="成功" value="success"/><el-option label="失败" value="failed"/></el-select>
      <el-button @click="resetFilters">重置</el-button>
    </section>

    <ErrorState v-if="error" title="操作日志加载失败" :description="error" @retry="load" />
    <section v-else class="panel table-panel">
      <el-table v-loading="loading" :data="pagedRecords" row-key="created_at">
        <el-table-column prop="operator_name" label="操作人" min-width="140" />
        <el-table-column label="角色" width="100"><template #default="{ row }">{{ roleLabels[row.operator_role] || row.operator_role }}</template></el-table-column>
        <el-table-column label="操作内容" min-width="180"><template #default="{ row }">{{ actionLabels[row.action] || row.action }}</template></el-table-column>
        <el-table-column label="模块" width="120"><template #default="{ row }">{{ moduleOf(row.action) }}</template></el-table-column>
        <el-table-column label="操作时间" width="180"><template #default="{ row }">{{ formatDate(row.created_at) }}</template></el-table-column>
        <el-table-column label="结果" width="90"><template #default="{ row }"><el-tag :type="row.success === false ? 'danger' : 'success'">{{ row.success === false ? '失败' : '成功' }}</el-tag></template></el-table-column>
        <el-table-column prop="ip_address" label="IP 地址" width="140"><template #default="{ row }">{{ row.ip_address || '服务端记录' }}</template></el-table-column>
        <el-table-column label="详情" width="90" fixed="right"><template #default="{ row }"><el-button link type="primary" @click="showDetail(row)">查看</el-button></template></el-table-column>
        <template #empty><EmptyState compact title="暂无操作日志" description="完成登录、上传合同或发起审查后，关键操作会显示在这里。"><el-button type="primary" @click="load">重新加载</el-button></EmptyState></template>
      </el-table>
      <footer class="audit-pagination"><span>筛选结果 {{ filtered.length }} 条，共读取 {{ records.length }} 条安全日志</span><el-pagination v-model:current-page="currentPage" v-model:page-size="pageSize" :page-sizes="[15,30,50]" :total="filtered.length" layout="sizes, prev, pager, next" /></footer>
    </section>

    <el-dialog v-model="detailVisible" title="操作日志详情" width="560px">
      <el-descriptions v-if="detail" :column="1" border>
        <el-descriptions-item label="操作人">{{ detail.operator_name }}</el-descriptions-item>
        <el-descriptions-item label="操作内容">{{ actionLabels[detail.action] || detail.action }}</el-descriptions-item>
        <el-descriptions-item label="目标对象">{{ detail.target || '无' }}</el-descriptions-item>
        <el-descriptions-item label="IP 地址">{{ detail.ip_address || '服务端记录' }}</el-descriptions-item>
        <el-descriptions-item label="扩展信息"><pre class="audit-json">{{ JSON.stringify(detail.metadata || {}, null, 2) }}</pre></el-descriptions-item>
      </el-descriptions>
      <template #footer><el-button type="primary" @click="detailVisible = false">关闭</el-button></template>
    </el-dialog>
  </div>
</template>

<style scoped>
.audit-page { display: grid; gap: var(--space-6); }
.audit-filters { display: grid; grid-template-columns: minmax(180px,1fr) minmax(300px,1.4fr) minmax(150px,.8fr) minmax(130px,.7fr) auto; gap: var(--space-3); padding: var(--space-5); }
.table-panel { overflow: hidden; }
.audit-pagination { display: flex; align-items: center; justify-content: space-between; gap: 16px; padding: 10px 20px; border-top: 1px solid var(--border); color: var(--text-muted); font-size: 12px; }
.audit-pagination :deep(.el-pagination) { padding: 0; }
.audit-json { margin: 0; overflow-wrap: anywhere; white-space: pre-wrap; font: 12px/1.6 Consolas, monospace; }
@media (max-width: 1080px) { .audit-filters { grid-template-columns: repeat(2, minmax(0,1fr)); } }
@media (max-width: 680px) { .audit-filters { grid-template-columns: 1fr; } .audit-pagination { align-items: flex-start; flex-direction: column; } }
</style>
