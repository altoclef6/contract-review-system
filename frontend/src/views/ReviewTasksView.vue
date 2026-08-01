<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { api } from '../api'
import EmptyState from '../components/EmptyState.vue'

type Task = {
  task_id: string
  contract_id?: string
  contract_version_id?: string
  requested_by: string
  status: string
  current_stage: string
  progress?: number | null
  started_at?: string
  finished_at?: string
  retry_count: number
  safe_error_message?: string
  result_summary: Record<string, any>
}

const router = useRouter()
const loading = ref(false)
const tasks = ref<Task[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const statusFilter = ref('')
let timer: number | undefined

const hasRunningTasks = computed(() =>
  tasks.value.some((item) => !['COMPLETED', 'FAILED', 'CANCELLED'].includes(item.status)),
)
const stageLabels: Record<string, string> = {
  PENDING: '待处理', VALIDATING: '正在校验文件', PARSING: '正在解析合同',
  EXTRACTING: '正在识别合同类型与条款', RULE_REVIEW: '正在匹配风险规则',
  KNOWLEDGE_RETRIEVAL: '正在检索法律依据', LLM_REVIEW: '正在生成修改建议',
  VALIDATING_RESULT: '正在校验审查结果', PERSISTING_RISKS: '正在保存风险',
  GENERATING_REPORT: '正在生成审查报告', COMPLETED: '已完成', FAILED: '失败', CANCELLED: '已取消',
}

async function load() {
  loading.value = true
  try {
    const response = await api.get('/review-tasks', {
      params: { page: page.value, page_size: pageSize.value, status: statusFilter.value || undefined },
    })
    tasks.value = response.data.data.items
    total.value = response.data.data.total
    schedulePolling()
  } catch (error: any) {
    ElMessage.error(error.response?.data?.message || '审查任务加载失败')
  } finally {
    loading.value = false
  }
}

function schedulePolling() {
  if (timer) window.clearInterval(timer)
  if (hasRunningTasks.value) timer = window.setInterval(load, 5000)
}

function stopPolling() {
  if (timer) window.clearInterval(timer)
  timer = undefined
}

async function cancelTask(task: Task) {
  await ElMessageBox.confirm('确定取消该审查任务吗？', '取消确认', { type: 'warning' })
  await api.post(`/review-tasks/${task.task_id}/cancel`)
  ElMessage.success('审查任务已取消')
  load()
}

async function retryTask(task: Task) {
  await api.post(`/review-tasks/${task.task_id}/retry`)
  ElMessage.success('已创建重试任务')
  load()
}

function viewResult(task: Task) {
  const reviewId = task.result_summary?.review_id
  if (reviewId) router.push(`/reader/${reviewId}`)
}

function elapsed(task: Task) {
  const start = task.started_at ? new Date(task.started_at).getTime() : 0
  const end = task.finished_at ? new Date(task.finished_at).getTime() : Date.now()
  if (!start) return '-'
  return `${Math.max(0, Math.round((end - start) / 1000))}s`
}

onMounted(load)
onBeforeUnmount(stopPolling)
</script>

<template>
  <section>
    <div class="page-head">
      <div>
        <h1>审查任务</h1>
        <p>展示真实异步执行阶段，支持取消、重试和结果恢复。</p>
      </div>
      <el-button :loading="loading" @click="load">刷新</el-button>
    </div>

    <div class="panel table-panel">
      <div class="toolbar">
        <el-select v-model="statusFilter" clearable placeholder="任务状态" @change="load">
          <el-option label="等待中" value="PENDING" />
          <el-option label="AI 审查中" value="LLM_REVIEW" />
          <el-option label="已完成" value="COMPLETED" />
          <el-option label="已失败" value="FAILED" />
          <el-option label="已取消" value="CANCELLED" />
        </el-select>
      </div>
      <el-table v-loading="loading" :data="tasks">
        <el-table-column prop="task_id" label="任务编号" min-width="220" show-overflow-tooltip />
        <el-table-column prop="contract_id" label="合同" min-width="160" show-overflow-tooltip />
        <el-table-column prop="contract_version_id" label="版本" min-width="160" show-overflow-tooltip />
        <el-table-column prop="requested_by" label="创建人" min-width="150" />
        <el-table-column label="状态" width="140"><template #default="{ row }">{{ stageLabels[row.status] || row.status }}</template></el-table-column>
        <el-table-column label="当前阶段" min-width="230"><template #default="{ row }"><div class="task-progress"><span>{{ stageLabels[row.current_stage] || row.current_stage }}</span><el-progress :percentage="row.progress ?? 0" :status="row.status === 'FAILED' ? 'exception' : row.status === 'COMPLETED' ? 'success' : undefined" /></div></template></el-table-column>
        <el-table-column label="耗时" width="100">
          <template #default="{ row }">{{ elapsed(row) }}</template>
        </el-table-column>
        <el-table-column prop="retry_count" label="重试" width="90" />
        <el-table-column label="风险数" width="90">
          <template #default="{ row }">{{ row.result_summary?.risk_count ?? '-' }}</template>
        </el-table-column>
        <el-table-column prop="safe_error_message" label="错误摘要" min-width="180" show-overflow-tooltip />
        <el-table-column fixed="right" label="操作" width="210">
          <template #default="{ row }">
            <el-button text size="small" :disabled="!row.result_summary?.review_id" @click="viewResult(row)">结果</el-button>
            <el-button text size="small" :disabled="['COMPLETED','FAILED','CANCELLED'].includes(row.status)" @click="cancelTask(row)">取消</el-button>
            <el-button text size="small" :disabled="row.status !== 'FAILED'" @click="retryTask(row)">重试</el-button>
          </template>
        </el-table-column>
        <template #empty><EmptyState compact title="暂无审查任务" description="上传合同并发起审查后，可在这里查看真实执行进度。"><el-button type="primary" @click="router.push('/review')">开始智能审查</el-button></EmptyState></template>
      </el-table>
      <el-pagination
        v-model:current-page="page"
        v-model:page-size="pageSize"
        layout="total, sizes, prev, pager, next"
        :total="total"
        @current-change="load"
        @size-change="load"
      />
    </div>
  </section>
</template>

<style scoped>
.task-progress { display: grid; gap: 5px; min-width: 190px; }
.task-progress span { color: var(--text-secondary); font-size: 12px; }
</style>
