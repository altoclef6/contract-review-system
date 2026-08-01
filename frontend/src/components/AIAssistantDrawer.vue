<script setup lang="ts">
import { computed, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ChatDotRound, Close, Promotion } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { api } from '../api'

const route = useRoute()
const router = useRouter()
const open = ref(false)
const submitting = ref(false)
const recentTask = ref<any>()
const form = reactive({ objective: '' })
const pageContext = computed(() => ({
  path: route.path,
  page_title: String(route.meta.title || ''),
  contract_id: typeof route.params.contractId === 'string' ? route.params.contractId : null,
  risk_id: typeof route.params.riskId === 'string' ? route.params.riskId : null,
}))
const recommendations = computed(() => {
  if (pageContext.value.contract_id) {
    return ['审查当前合同的关键风险', '汇总付款与违约责任条款', '生成当前合同风险摘要']
  }
  if (pageContext.value.risk_id) return ['解释当前风险及法律依据', '给出可执行的修改建议']
  if (route.path.startsWith('/contracts')) return ['查找近期高风险合同', '汇总待处理合同风险']
  return ['创建合同审查任务', '汇总我的待处理风险']
})

async function submit() {
  if (!form.objective.trim()) {
    ElMessage.warning('请描述希望 AI 完成的任务')
    return
  }
  submitting.value = true
  try {
    recentTask.value = (await api.post('/agent-tasks', {
      task_type: 'contract_review',
      objective: form.objective,
      contract_id: pageContext.value.contract_id,
      context: pageContext.value,
    })).data.data
    form.objective = ''
    ElMessage.success('已创建 Agent 任务')
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <button class="ai-orb" type="button" aria-label="打开全局 AI 助手" @click="open = true">
    <el-icon><ChatDotRound /></el-icon><span>AI</span>
  </button>
  <el-drawer v-model="open" size="440px" :with-header="false" append-to-body class="ai-context-drawer">
    <div class="ai-drawer-head">
      <div><small>CONTEXT AGENT</small><h2>全局 AI 助手</h2></div>
      <el-button circle text :icon="Close" @click="open = false" />
    </div>
    <div class="ai-context-card">
      <span>当前上下文</span><strong>{{ pageContext.page_title || '合同审查工作台' }}</strong>
      <small>{{ pageContext.contract_id || pageContext.risk_id || pageContext.path }}</small>
    </div>
    <section class="ai-suggestions">
      <h3>推荐操作</h3>
      <button v-for="item in recommendations" :key="item" @click="form.objective = item">
        <span>{{ item }}</span><el-icon><Promotion /></el-icon>
      </button>
    </section>
    <section v-if="recentTask" class="ai-created-task">
      <small>刚刚创建</small><strong>{{ recentTask.objective }}</strong>
      <span>任务已保存，等待你在工作台中启动。</span>
      <el-button text type="primary" @click="open = false; router.push('/agent-workbench')">前往 AI 工作台</el-button>
    </section>
    <div class="ai-drawer-composer">
      <el-input v-model="form.objective" type="textarea" :rows="5" resize="none" placeholder="描述目标。AI 会先生成计划，高风险操作仍需你确认。" />
      <el-button type="primary" :loading="submitting" @click="submit">创建任务</el-button>
      <p>AI 输出仅供辅助审查，正式决策需由授权人员复核。</p>
    </div>
  </el-drawer>
</template>
