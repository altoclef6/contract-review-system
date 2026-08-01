<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { api } from '../api'

const loading = ref(false)
const tasks = ref<any[]>([])
const current = ref<any>()
const createDialog = ref(false)
const form = reactive({
  task_type: 'contract_review',
  objective: '',
  contract_id: '',
})

const statusText: Record<string, string> = {
  created: '待启动',
  planning: '规划中',
  running: '执行中',
  waiting_confirmation: '等待确认',
  completed: '已完成',
  failed: '执行失败',
  cancelled: '已取消',
}
const statusType = computed(() => {
  const status = current.value?.status
  if (status === 'completed') return 'success'
  if (status === 'waiting_confirmation') return 'warning'
  if (status === 'failed' || status === 'cancelled') return 'danger'
  return 'primary'
})

async function load() {
  loading.value = true
  try {
    tasks.value = (await api.get('/agent-tasks')).data.data
    if (current.value) {
      current.value = tasks.value.find((item) => item.id === current.value.id) || tasks.value[0]
    } else {
      current.value = tasks.value[0]
    }
  } finally {
    loading.value = false
  }
}

async function createTask() {
  if (!form.objective.trim()) {
    ElMessage.warning('请填写任务目标')
    return
  }
  const payload = {
    task_type: form.task_type,
    objective: form.objective,
    contract_id: form.contract_id || null,
    context: {},
  }
  current.value = (await api.post('/agent-tasks', payload)).data.data
  createDialog.value = false
  form.objective = ''
  form.contract_id = ''
  await load()
  ElMessage.success('Agent 任务已创建')
}

async function runTask() {
  current.value = (await api.post(`/agent-tasks/${current.value.id}/run`)).data.data
  await load()
}

async function confirmTool(approved: boolean) {
  const action = approved ? '批准执行' : '拒绝执行'
  await ElMessageBox.confirm(
    `${action}高风险工具“report.generate”？该操作会生成正式报告并写入任务记录。`,
    '人工确认',
    { confirmButtonText: action, cancelButtonText: '暂不处理', type: approved ? 'warning' : 'error' },
  )
  current.value = (
    await api.post(`/agent-tasks/${current.value.id}/confirmation`, {
      approved,
      note: approved ? '用户批准生成正式报告' : '用户拒绝生成正式报告',
    })
  ).data.data
  await load()
}

onMounted(load)
</script>

<template>
  <section class="agent-workbench">
    <header class="page-header">
      <div>
        <span class="page-header__eyebrow">Enterprise Agent</span>
        <h1>AI 工作台</h1>
        <p>将合同审查目标拆解为可追踪步骤，所有高风险操作均需人工确认。</p>
      </div>
      <el-button type="primary" @click="createDialog = true">新建 Agent 任务</el-button>
    </header>

    <div class="agent-shell glass-panel">
      <aside class="agent-task-list">
        <div class="agent-section-title"><strong>任务</strong><span>{{ tasks.length }}</span></div>
        <button
          v-for="task in tasks"
          :key="task.id"
          :class="['agent-task-item', { active: current?.id === task.id }]"
          @click="current = task"
        >
          <span>{{ task.objective }}</span>
          <small>{{ statusText[task.status] || task.status }}</small>
        </button>
        <div v-if="!tasks.length && !loading" class="agent-mini-empty">暂无任务</div>
      </aside>

      <main v-if="current" class="agent-canvas">
        <div class="agent-hero">
          <div>
            <el-tag :type="statusType">{{ statusText[current.status] || current.status }}</el-tag>
            <h2>{{ current.objective }}</h2>
            <p>任务类型：{{ current.task_type }} · 当前步骤 {{ current.current_step }}/{{ current.steps.length }}</p>
          </div>
          <el-button
            v-if="['created', 'running'].includes(current.status)"
            type="primary"
            @click="runTask"
          >开始执行</el-button>
        </div>

        <div v-if="current.status === 'waiting_confirmation'" class="agent-confirmation">
          <div>
            <strong>需要人工确认</strong>
            <p>Agent 准备调用高风险工具生成正式报告。确认前不会执行或写入正式产物。</p>
          </div>
          <div>
            <el-button @click="confirmTool(false)">拒绝</el-button>
            <el-button type="warning" @click="confirmTool(true)">确认执行</el-button>
          </div>
        </div>

        <section class="agent-timeline">
          <h3>执行计划与证据链</h3>
          <article v-for="step in current.steps" :key="step.id" class="agent-step">
            <i :class="`is-${step.status}`"></i>
            <div>
              <strong>{{ step.sequence }}. {{ step.name }}</strong>
              <span>{{ statusText[step.status] || step.status }}</span>
              <p v-if="step.output_data?.evidence_retained">已保留合同引用、工具参数与执行结果</p>
            </div>
          </article>
        </section>

        <section class="agent-result">
          <h3>任务结论</h3>
          <p v-if="current.result?.summary">{{ current.result.summary }}</p>
          <p v-else>任务完成后将在此展示结论、证据来源和人工复核提示。</p>
        </section>
      </main>
      <main v-else class="agent-canvas agent-empty">
        <h2>创建第一个 Agent 任务</h2>
        <p>选择合同审查、版本对比、风险汇总或报告生成。</p>
      </main>
    </div>

    <el-dialog v-model="createDialog" title="新建 Agent 任务" width="520px">
      <el-form label-position="top">
        <el-form-item label="任务类型">
          <el-select v-model="form.task_type" style="width:100%">
            <el-option label="合同审查" value="contract_review" />
            <el-option label="版本对比" value="contract_compare" />
            <el-option label="风险汇总" value="risk_summary" />
            <el-option label="正式报告生成" value="report_generation" />
          </el-select>
        </el-form-item>
        <el-form-item label="任务目标">
          <el-input v-model="form.objective" type="textarea" :rows="4" placeholder="例如：审查付款、违约责任与解除条款，并给出可追溯依据" />
        </el-form-item>
        <el-form-item label="合同 ID（可选）">
          <el-input v-model="form.contract_id" placeholder="contract_xxx" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createDialog = false">取消</el-button>
        <el-button type="primary" @click="createTask">创建任务</el-button>
      </template>
    </el-dialog>
  </section>
</template>
