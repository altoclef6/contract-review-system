<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Connection, Plus, Refresh, Setting } from '@element-plus/icons-vue'
import EmptyState from '../components/EmptyState.vue'
import ErrorState from '../components/ErrorState.vue'
import PageHeader from '../components/PageHeader.vue'
import { api } from '../api'

const SETTINGS_KEY = 'contract-review:system-settings'
const tab = ref('general')
const loading = ref(false)
const error = ref('')
const models = ref<any[]>([])
const prompts = ref<any[]>([])
const providers = ref<any[]>([])
const dialog = ref(false)
const savingModel = ref(false)
const testing = ref(false)
const systemSaving = ref(false)

const system = reactive({
  systemName: '衡契合同审查平台', enterpriseName: '示例科技有限公司', language: 'zh-CN',
  defaultModel: '规则引擎（无 Key 可用）', aiReviewEnabled: true, autoReportEnabled: true,
  riskThreshold: 'medium', maxFileSizeMb: 50, allowedTypes: 'PDF、DOC、DOCX、PNG、JPG、TIFF',
  retentionDays: 365,
})
const modelForm = reactive({
  name: '', provider: 'deepseek', api_key: '', base_url: 'https://api.deepseek.com/v1',
  model_name: 'deepseek-chat', temperature: 0.1, max_tokens: 4096, timeout_seconds: 60,
})

const staticProviders = [
  { provider: 'deepseek', label: 'DeepSeek', default_base_url: 'https://api.deepseek.com/v1', default_model_name: 'deepseek-chat' },
  { provider: 'openai', label: 'OpenAI', default_base_url: 'https://api.openai.com/v1', default_model_name: 'gpt-4.1-mini' },
  { provider: 'qwen', label: '通义千问 Qwen', default_base_url: 'https://dashscope.aliyuncs.com/compatible-mode/v1', default_model_name: 'qwen-plus' },
  { provider: 'openai_compatible', label: 'OpenAI 兼容接口', default_base_url: '', default_model_name: '' },
]

function loadLocalSettings() {
  try {
    const saved = JSON.parse(localStorage.getItem(SETTINGS_KEY) || 'null')
    if (saved && typeof saved === 'object') Object.assign(system, saved)
  } catch { /* Local storage failures must not block the settings page. */ }
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    const [modelResponse, promptResponse, providerResponse] = await Promise.all([
      api.get('/model-configs'), api.get('/prompt-templates'), api.get('/model-configs/providers'),
    ])
    models.value = modelResponse.data.data
    prompts.value = promptResponse.data.data
    providers.value = providerResponse.data.data
  } catch (cause: any) {
    providers.value = staticProviders
    error.value = cause?.response?.data?.message || cause?.response?.data?.detail || '模型与 Prompt 配置加载失败'
  } finally { loading.value = false }
}

function saveSystem() {
  systemSaving.value = true
  try {
    localStorage.setItem(SETTINGS_KEY, JSON.stringify(system))
    ElMessage.success('系统展示配置已保存')
  } catch { ElMessage.error('浏览器存储不可用，配置未能保存') }
  finally { window.setTimeout(() => { systemSaving.value = false }, 250) }
}

function openModelDialog() {
  Object.assign(modelForm, { name: '', provider: 'deepseek', api_key: '', base_url: 'https://api.deepseek.com/v1', model_name: 'deepseek-chat', temperature: 0.1, max_tokens: 4096, timeout_seconds: 60 })
  dialog.value = true
}

function syncProvider() {
  const provider = providers.value.find((item) => item.provider === modelForm.provider)
  if (!provider) return
  modelForm.base_url = provider.default_base_url || ''
  modelForm.model_name = provider.default_model_name || ''
}

function validateModelForm() {
  if (!modelForm.name.trim()) { ElMessage.warning('请输入配置名称'); return false }
  if (modelForm.api_key.length < 8) { ElMessage.warning('请输入有效的 API Key'); return false }
  if (!modelForm.model_name.trim()) { ElMessage.warning('请输入模型名称'); return false }
  return true
}

async function testConnection() {
  if (!validateModelForm()) return
  testing.value = true
  try {
    const response = await api.post('/llm/validate', {
      provider: modelForm.provider, api_key: modelForm.api_key,
      model_name: modelForm.model_name, base_url: modelForm.base_url,
    }, { timeout: Math.max(5, modelForm.timeout_seconds) * 1000 })
    ElMessage.success(`连接成功，响应耗时 ${response.data.latency_ms} ms`)
  } catch (cause: any) {
    ElMessage.error(cause?.code === 'ECONNABORTED' ? '连接测试超时' : cause?.response?.data?.detail || '连接测试失败，请检查 Key、地址和模型名称')
  } finally { testing.value = false }
}

async function saveModel() {
  if (!validateModelForm()) return
  savingModel.value = true
  try {
    await api.post('/model-configs', { ...modelForm })
    dialog.value = false
    ElMessage.success('模型配置已加密保存')
    await load()
  } catch (cause: any) { ElMessage.error(cause?.response?.data?.message || cause?.response?.data?.detail || '模型配置保存失败') }
  finally { savingModel.value = false }
}

async function activate(id: string) {
  try { await api.post(`/model-configs/${id}/active`); ElMessage.success('默认模型已切换'); await load() }
  catch (cause: any) { ElMessage.error(cause?.response?.data?.detail || '模型切换失败') }
}

onMounted(() => { loadLocalSettings(); void load() })
</script>

<template>
  <div class="settings-page">
    <PageHeader title="系统设置" description="集中维护系统策略、模型凭据和审查 Prompt；敏感密钥仅由后端加密保存。" eyebrow="SYSTEM SETTINGS">
      <template #actions><el-button :icon="Refresh" :loading="loading" @click="load">刷新配置</el-button></template>
    </PageHeader>

    <el-tabs v-model="tab" class="settings-tabs">
      <el-tab-pane label="基础设置" name="general">
        <section class="panel settings-section">
          <header><span><el-icon><Setting /></el-icon></span><div><h2>系统与审查策略</h2><p>用于当前设备的验收展示偏好；真实 AI 与安全策略仍以后端环境配置为准。</p></div></header>
          <el-form label-position="top">
            <div class="settings-grid">
              <el-form-item label="系统名称"><el-input v-model="system.systemName" maxlength="50" /></el-form-item>
              <el-form-item label="企业名称"><el-input v-model="system.enterpriseName" maxlength="80" /></el-form-item>
              <el-form-item label="默认语言"><el-select v-model="system.language"><el-option label="简体中文" value="zh-CN"/><el-option label="English" value="en-US"/></el-select></el-form-item>
              <el-form-item label="默认模型"><el-select v-model="system.defaultModel"><el-option label="规则引擎（无 Key 可用）" value="规则引擎（无 Key 可用）"/><el-option v-for="item in models" :key="item.id" :label="item.name" :value="item.name"/></el-select></el-form-item>
              <el-form-item label="默认风险阈值"><el-select v-model="system.riskThreshold"><el-option label="中风险及以上" value="medium"/><el-option label="仅高风险" value="high"/><el-option label="全部风险" value="low"/></el-select></el-form-item>
              <el-form-item label="数据保留时间"><el-input-number v-model="system.retentionDays" :min="30" :max="3650" /><span class="field-unit">天</span></el-form-item>
              <el-form-item label="文件大小限制"><el-input-number v-model="system.maxFileSizeMb" :min="1" :max="200" /><span class="field-unit">MB</span></el-form-item>
              <el-form-item label="允许的文件类型"><el-input v-model="system.allowedTypes" /></el-form-item>
            </div>
            <div class="switch-list"><label><span><strong>启用 AI 辅助审查</strong><small>外部模型不可用时仍保留确定性规则结果</small></span><el-switch v-model="system.aiReviewEnabled" /></label><label><span><strong>自动生成审查报告</strong><small>审查完成后同步生成 PDF、Word 与 Excel 报告</small></span><el-switch v-model="system.autoReportEnabled" /></label></div>
            <div class="settings-actions"><el-button type="primary" :loading="systemSaving" @click="saveSystem">保存基础设置</el-button></div>
          </el-form>
        </section>
      </el-tab-pane>

      <el-tab-pane label="API 与模型" name="models">
        <ErrorState v-if="error" title="模型配置加载失败" :description="error" @retry="load" />
        <section v-else class="panel table-panel">
          <div class="settings-toolbar"><div><h2>模型配置</h2><p>API Key 默认隐藏，接口与持久化均不返回明文。</p></div><el-button type="primary" :icon="Plus" @click="openModelDialog">添加模型</el-button></div>
          <el-table v-loading="loading" :data="models">
            <el-table-column prop="name" label="配置名称" min-width="180"/><el-table-column prop="provider" label="服务商" width="130"/><el-table-column prop="model_name" label="模型" min-width="180"/><el-table-column prop="api_key_masked" label="API Key" width="130"/><el-table-column prop="timeout_seconds" label="超时" width="90"><template #default="{ row }">{{ row.timeout_seconds || 60 }} 秒</template></el-table-column><el-table-column label="状态" width="100"><template #default="{ row }"><el-tag :type="row.is_active ? 'success' : 'info'">{{ row.is_active ? '使用中' : '未启用' }}</el-tag></template></el-table-column><el-table-column label="操作" width="100"><template #default="{ row }"><el-button link type="primary" :disabled="row.is_active" @click="activate(row.id)">设为默认</el-button></template></el-table-column>
            <template #empty><EmptyState compact title="尚未配置外部模型" description="系统仍可使用确定性规则完成基础审查；添加模型后可启用 AI 增强。"><el-button type="primary" @click="openModelDialog">添加模型</el-button></EmptyState></template>
          </el-table>
        </section>
      </el-tab-pane>

      <el-tab-pane label="Prompt 模板" name="prompts">
        <section class="panel table-panel"><div class="settings-toolbar"><div><h2>审查 Prompt 模板</h2><p>按合同类型和 Agent 阶段管理审查指令版本。</p></div></div><el-table v-loading="loading" :data="prompts"><el-table-column prop="name" label="模板名称"/><el-table-column prop="contract_type" label="合同类型"/><el-table-column prop="stage" label="Agent 阶段"/><el-table-column prop="version" label="版本" width="80"/><el-table-column label="状态" width="100"><template #default="{ row }"><el-tag :type="row.is_enabled ? 'success' : 'info'">{{ row.is_enabled ? '启用' : '停用' }}</el-tag></template></el-table-column><template #empty><EmptyState compact title="暂无 Prompt 模板" description="添加模板后可针对不同合同类型细化审查策略。" /></template></el-table></section>
      </el-tab-pane>
    </el-tabs>

    <el-dialog v-model="dialog" title="添加外部模型" width="620px" destroy-on-close>
      <el-alert title="API Key 将提交至后端并加密保存，前端不会写入代码或浏览器存储。" type="info" :closable="false" show-icon />
      <el-form label-position="top" class="model-form">
        <div class="settings-grid"><el-form-item label="配置名称" required><el-input v-model="modelForm.name" placeholder="例如：生产审查模型" /></el-form-item><el-form-item label="模型提供商" required><el-select v-model="modelForm.provider" @change="syncProvider"><el-option v-for="provider in providers.length ? providers : staticProviders" :key="provider.provider" :label="provider.label" :value="provider.provider"/></el-select></el-form-item></div>
        <el-form-item label="API Base URL"><el-input v-model="modelForm.base_url" placeholder="https://api.example.com/v1" /></el-form-item>
        <el-form-item label="API Key" required><el-input v-model="modelForm.api_key" type="password" show-password autocomplete="new-password" placeholder="仅在本次提交中使用" /></el-form-item>
        <div class="settings-grid"><el-form-item label="模型名称" required><el-input v-model="modelForm.model_name" /></el-form-item><el-form-item label="超时时间"><el-input-number v-model="modelForm.timeout_seconds" :min="5" :max="600" /><span class="field-unit">秒</span></el-form-item><el-form-item label="Temperature"><el-input-number v-model="modelForm.temperature" :min="0" :max="2" :step="0.1" /></el-form-item><el-form-item label="最大 Token"><el-input-number v-model="modelForm.max_tokens" :min="256" :max="128000" :step="256" /></el-form-item></div>
      </el-form>
      <template #footer><el-button @click="dialog = false">取消</el-button><el-button :icon="Connection" :loading="testing" @click="testConnection">测试连接</el-button><el-button type="primary" :loading="savingModel" @click="saveModel">加密保存</el-button></template>
    </el-dialog>
  </div>
</template>

<style scoped>
.settings-page { display: grid; gap: var(--space-6); }
.settings-tabs :deep(.el-tabs__content) { overflow: visible; }
.settings-section { padding: 26px; }
.settings-section > header, .settings-toolbar { display: flex; align-items: center; justify-content: space-between; gap: 16px; margin-bottom: 24px; }
.settings-section > header { justify-content: flex-start; }
.settings-section > header > span { display: grid; place-items: center; width: 44px; height: 44px; border-radius: 15px; color: #315f92; background: #eaf2f8; font-size: 21px; }
.settings-section h2, .settings-toolbar h2 { margin: 0; font-size: 17px; }
.settings-section p, .settings-toolbar p { margin: 4px 0 0; color: var(--text-secondary); font-size: 12px; }
.settings-grid { display: grid; grid-template-columns: repeat(2, minmax(0,1fr)); gap: 0 20px; }
.field-unit { margin-left: 8px; color: var(--text-secondary); font-size: 12px; }
.switch-list { display: grid; gap: 10px; margin-top: 4px; }
.switch-list label { display: flex; align-items: center; justify-content: space-between; gap: 18px; padding: 14px 16px; border: 1px solid var(--border); border-radius: 14px; background: var(--surface-soft); }
.switch-list span { display: flex; flex-direction: column; }
.switch-list strong { font-size: 13px; }
.switch-list small { color: var(--text-muted); font-size: 11px; }
.settings-actions { display: flex; justify-content: flex-end; margin-top: 22px; }
.settings-toolbar { margin: 0; padding: 20px 22px; border-bottom: 1px solid var(--border); }
.table-panel { overflow: hidden; }
.model-form { margin-top: 18px; }
@media (max-width: 720px) { .settings-grid { grid-template-columns: 1fr; } .settings-toolbar { align-items: flex-start; flex-direction: column; } }
</style>
