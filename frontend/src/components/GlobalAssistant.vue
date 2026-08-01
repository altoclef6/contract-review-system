<script setup lang="ts">
import { computed, nextTick, ref } from 'vue'
import { useRoute } from 'vue-router'
import { ChatLineRound, Close, Minus, Promotion } from '@element-plus/icons-vue'
import { api } from '../api'

const panelOpen = ref(false)
const minimized = ref(false)
const initialized = ref(false)
const loading = ref(false)
const sending = ref(false)
const error = ref('')
const input = ref('')
const sessions = ref<any[]>([])
const current = ref<any>()
const messageContainer = ref<HTMLElement>()
const route = useRoute()
const selectedContext = computed(() => String(route.params.reviewId || route.params.contractId || ''))
const selectedReviewId = computed(() => String(route.params.reviewId || ''))

const quickQuestions = [
  '这份合同有哪些高风险条款？',
  '帮我解释当前违约责任条款。',
  '总结这份合同的主要风险。',
  '根据当前风险生成修改建议。',
]

async function scrollToBottom() {
  await nextTick()
  if (messageContainer.value) messageContainer.value.scrollTop = messageContainer.value.scrollHeight
}

async function initialize() {
  if (initialized.value) return
  loading.value = true
  error.value = ''
  try {
    sessions.value = (await api.get('/chats')).data.data
    current.value = selectedReviewId.value
      ? sessions.value.find((item) => item.review_id === selectedReviewId.value)
      : undefined
    initialized.value = true
  } catch (cause: any) {
    error.value = cause?.response?.data?.message || cause?.response?.data?.detail || 'AI 助手暂时无法连接，请稍后重试'
  } finally {
    loading.value = false
    await scrollToBottom()
  }
}

async function togglePanel() {
  panelOpen.value = !panelOpen.value
  minimized.value = false
  if (panelOpen.value) await initialize()
}

async function ensureSession() {
  if (current.value) return current.value
  const session = (await api.post('/chats', {
    title: '合同风险咨询',
    review_id: selectedReviewId.value || null,
  })).data.data
  sessions.value.unshift(session)
  current.value = session
  return session
}

async function send(text = input.value) {
  const message = text.trim()
  if (!message || sending.value) return
  if (!selectedContext.value) {
    error.value = '请先打开合同详情或审查结果，再向 AI 助手提问。'
    return
  }
  sending.value = true
  error.value = ''
  input.value = ''
  try {
    const session = await ensureSession()
    current.value = (
      await api.post(`/chats/${session.id}/messages`, { message })
    ).data.data.session
    await scrollToBottom()
  } catch (cause: any) {
    input.value = message
    error.value = cause?.code === 'ECONNABORTED'
      ? 'AI 响应超时，请稍后重试'
      : cause?.response?.data?.message || cause?.response?.data?.detail || '消息发送失败，请检查服务连接'
  } finally {
    sending.value = false
  }
}
</script>

<template>
  <div class="global-assistant" :class="{ 'is-open': panelOpen && !minimized }">
    <Transition name="assistant-panel">
      <section v-if="panelOpen && !minimized" class="assistant-panel" aria-label="全局 AI 法务助手">
        <header>
          <span class="assistant-avatar"><el-icon><ChatLineRound /></el-icon></span>
          <div><strong>衡契 AI 助手</strong><small>合同风险与条款咨询</small></div>
          <el-button text circle aria-label="最小化 AI 助手" @click="minimized = true"><el-icon><Minus /></el-icon></el-button>
          <el-button text circle aria-label="关闭 AI 助手" @click="panelOpen = false"><el-icon><Close /></el-icon></el-button>
        </header>

        <div ref="messageContainer" class="assistant-messages">
          <div class="assistant-welcome">
            <strong>你好，我是衡契 AI 法务助手</strong>
            <p>我可以解释合同条款、归纳风险并提供修改思路。重要结论请交由专业法务复核。</p>
          </div>
          <div v-for="message in current?.messages || []" :key="message.id" :class="['assistant-message', message.role]">
            <span>{{ message.role === 'user' ? '你' : 'AI' }}</span><p>{{ message.content }}</p>
          </div>
          <div v-if="sending" class="assistant-message assistant is-loading"><span>AI</span><p>正在结合合同审查上下文分析…</p></div>
        </div>

        <div v-if="!current?.messages?.length" class="assistant-quick">
          <button v-for="question in quickQuestions" :key="question" type="button" :disabled="loading || sending" @click="send(question)">{{ question }}</button>
        </div>
        <el-alert v-if="error" :title="error" type="error" :closable="true" show-icon @close="error = ''" />
        <footer>
          <el-input v-model="input" type="textarea" :rows="2" resize="none" maxlength="500" placeholder="输入合同或条款问题" :disabled="loading" @keydown.ctrl.enter.prevent="send()" />
          <el-button type="primary" :icon="Promotion" :loading="sending || loading" :disabled="!input.trim()" @click="send()">发送</el-button>
        </footer>
      </section>
    </Transition>

    <button class="assistant-orb" type="button" :aria-label="panelOpen ? '打开 AI 助手' : '启动 AI 助手'" @click="togglePanel">
      <el-icon><ChatLineRound /></el-icon><span v-if="minimized" class="assistant-orb__dot"></span>
    </button>
  </div>
</template>

<style scoped>
.global-assistant { position: fixed; right: 28px; bottom: 26px; z-index: 2200; display: grid; justify-items: end; gap: 14px; pointer-events: none; }
.assistant-orb, .assistant-panel { pointer-events: auto; }
.assistant-orb { position: relative; display: grid; place-items: center; width: 58px; height: 58px; padding: 0; border: 1px solid rgba(255,255,255,.7); border-radius: 19px; color: #fff; background: #315f92; box-shadow: 0 12px 28px rgba(49,95,146,.25); font-size: 25px; cursor: pointer; transition: transform var(--transition-fast), box-shadow var(--transition-fast), background var(--transition-fast); }
.assistant-orb:hover { transform: translateY(-2px); background: #274f7d; box-shadow: 0 15px 32px rgba(49,95,146,.32), 0 0 0 6px rgba(79,132,185,.09); }
.assistant-orb:active { transform: translateY(0) scale(.97); }
.assistant-orb__dot { position: absolute; top: -2px; right: -2px; width: 12px; height: 12px; border: 2px solid #fff; border-radius: 50%; background: #37a878; }
.assistant-panel { width: min(390px, calc(100vw - 32px)); max-height: min(660px, calc(100vh - 120px)); overflow: hidden; border: 1px solid rgba(214,225,236,.92); border-radius: 24px; background: rgba(255,255,255,.97); box-shadow: 0 24px 70px rgba(35,57,81,.2); backdrop-filter: blur(14px); }
.assistant-panel > header { display: grid; grid-template-columns: auto minmax(0,1fr) auto auto; gap: 9px; align-items: center; padding: 16px; border-bottom: 1px solid var(--border); background: #f8fbfe; }
.assistant-avatar { display: grid; place-items: center; width: 38px; height: 38px; border-radius: 13px; color: #315f92; background: #e9f1f8; font-size: 19px; }
.assistant-panel header div { display: flex; flex-direction: column; min-width: 0; }
.assistant-panel header strong { font-size: 14px; }
.assistant-panel header small { color: var(--text-muted); font-size: 11px; }
.assistant-messages { display: grid; gap: 12px; min-height: 190px; max-height: 340px; overflow-y: auto; padding: 16px; background: #fbfcfe; }
.assistant-welcome { padding: 14px; border: 1px solid #dfeaf4; border-radius: 16px; background: #f2f7fb; }
.assistant-welcome strong { font-size: 13px; }
.assistant-welcome p { margin: 5px 0 0; color: var(--text-secondary); font-size: 12px; line-height: 1.65; }
.assistant-message { display: grid; grid-template-columns: 28px minmax(0,1fr); gap: 8px; align-items: start; }
.assistant-message > span { display: grid; place-items: center; width: 28px; height: 28px; border-radius: 10px; color: #315f92; background: #e9f1f8; font-size: 10px; font-weight: 700; }
.assistant-message p { margin: 0; padding: 10px 12px; border: 1px solid var(--border); border-radius: 4px 14px 14px; background: #fff; font-size: 12px; line-height: 1.65; white-space: pre-wrap; }
.assistant-message.user { grid-template-columns: minmax(0,1fr) 28px; }
.assistant-message.user > span { grid-column: 2; background: #315f92; color: #fff; }
.assistant-message.user p { grid-column: 1; grid-row: 1; border-color: #d7e4ef; border-radius: 14px 4px 14px 14px; background: #eef5fa; }
.assistant-message.is-loading p { color: var(--text-secondary); }
.assistant-quick { display: flex; flex-wrap: wrap; gap: 7px; padding: 0 16px 14px; background: #fbfcfe; }
.assistant-quick button { padding: 7px 9px; border: 1px solid #dbe6f0; border-radius: 10px; color: #49647e; background: #fff; font-size: 11px; cursor: pointer; }
.assistant-quick button:hover { border-color: #9db8d2; background: #f3f7fb; }
.assistant-panel :deep(.el-alert) { margin: 0 16px 12px; }
.assistant-panel > footer { display: grid; grid-template-columns: minmax(0,1fr) auto; gap: 9px; align-items: end; padding: 14px 16px 16px; border-top: 1px solid var(--border); }
.assistant-panel > footer .el-button { height: 56px; }
.assistant-panel-enter-active, .assistant-panel-leave-active { transition: opacity .18s ease, transform .18s ease; transform-origin: right bottom; }
.assistant-panel-enter-from, .assistant-panel-leave-to { opacity: 0; transform: translateY(12px) scale(.97); }
@media (max-width: 640px) { .global-assistant { right: 16px; bottom: 16px; } .assistant-panel { max-height: calc(100vh - 96px); } }
</style>
