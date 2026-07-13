
<script setup lang="ts">
import { computed, nextTick, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { api } from '../api'

const route = useRoute()
const contractId = ref(String(route.query.contract_id || ''))
const contracts = ref<any[]>([])
const versions = ref<any[]>([])
const baseId = ref('')
const targetId = ref('')
const result = ref<any>(null)
const loading = ref(false)
const activeDiff = ref(0)
const feedbackOpen = ref(false)
const feedbackRisk = ref<any>(null)
const feedbackVersionId = ref('')
const feedback = ref({ feedback_type: 'confirmed_risk', suggested_severity: '', reason: '' })
const changedSegments = computed(() => result.value?.text_segments?.filter((item:any) => item.change_type !== 'unchanged') || [])
const statusLabel:Record<string,string> = { added:'新增风险', removed:'风险消失', unchanged:'风险未变', severity_increased:'等级上升', severity_decreased:'等级下降', text_changed:'条款变化', remediated:'已人工标记整改', uncertain_match:'匹配不确定' }

async function loadContracts() {
  contracts.value = (await api.get('/contracts', { params: { page_size: 100 } })).data.data.items
  if (!contractId.value && contracts.value.length) contractId.value = contracts.value[0].id
  await loadVersions()
}
async function loadVersions() {
  result.value = null
  if (!contractId.value) return
  versions.value = (await api.get(`/contracts/${contractId.value}/versions`)).data.data
  if (versions.value.length >= 2) {
    baseId.value = versions.value.at(-2).id
    targetId.value = versions.value.at(-1).id
  } else { baseId.value = ''; targetId.value = '' }
}
async function compare() {
  if (!baseId.value || !targetId.value) return ElMessage.warning('请选择两个版本')
  loading.value = true
  try {
    result.value = (await api.post(`/version-comparisons/${contractId.value}`, { base_version_id: baseId.value, target_version_id: targetId.value })).data.data
    activeDiff.value = 0
  } catch (e:any) { ElMessage.error(e.response?.data?.message || e.response?.data?.detail || '版本对比失败') }
  finally { loading.value = false }
}
async function nextDiff() {
  if (!changedSegments.value.length) return
  activeDiff.value = (activeDiff.value + 1) % changedSegments.value.length
  await nextTick()
  document.querySelector(`[data-diff-index="${activeDiff.value}"]`)?.scrollIntoView({ behavior:'smooth', block:'center' })
}
function openFeedback(change:any) {
  feedbackRisk.value = change.target_risk || change.base_risk
  feedbackVersionId.value = change.target_risk ? targetId.value : baseId.value
  feedback.value = { feedback_type:'confirmed_risk', suggested_severity:'', reason:'' }
  feedbackOpen.value = true
}
async function submitFeedback() {
  const risk = feedbackRisk.value
  await api.post('/risk-feedback', {
    contract_id: contractId.value, contract_version_id: feedbackVersionId.value,
    risk_id: risk.risk_id || risk.风险编号 || `${risk.规则编号 || risk.rule_id || 'risk'}-${risk.风险标题 || risk.title || 'unknown'}`,
    rule_id: risk.rule_id || risk.规则编号 || null,
    contract_type: contracts.value.find(item => item.id === contractId.value)?.category || null,
    ...feedback.value,
    suggested_severity: feedback.value.suggested_severity || null,
  })
  feedbackOpen.value = false
  ElMessage.success('反馈已保存，不会自动训练模型')
}
onMounted(loadContracts)
</script>

<template>
  <div class="page-head"><div><h1>合同版本对比</h1><p>按中文段落和条款比较真实版本文本，并对风险进行可解释匹配。</p></div></div>
  <section class="panel version-selector">
    <el-select v-model="contractId" placeholder="选择合同" filterable @change="loadVersions"><el-option v-for="item in contracts" :key="item.id" :label="item.title" :value="item.id" /></el-select>
    <el-select v-model="baseId" placeholder="基础版本"><el-option v-for="item in versions" :key="item.id" :label="`v${item.version_no} · ${item.file_name}`" :value="item.id" /></el-select>
    <el-select v-model="targetId" placeholder="目标版本"><el-option v-for="item in versions" :key="item.id" :label="`v${item.version_no} · ${item.file_name}`" :value="item.id" /></el-select>
    <el-button type="primary" :loading="loading" :disabled="!baseId || !targetId" @click="compare">开始对比</el-button>
    <el-button :disabled="!changedSegments.length" @click="nextDiff">下一处差异</el-button>
  </section>
  <el-empty v-if="!result" description="请选择同一合同的两个版本开始对比" />
  <template v-else>
    <section class="metrics comparison-metrics">
      <article><span>新增段落</span><strong>{{ result.summary.added || 0 }}</strong></article>
      <article><span>删除段落</span><strong>{{ result.summary.removed || 0 }}</strong></article>
      <article><span>修改段落</span><strong>{{ result.summary.modified || 0 }}</strong></article>
      <article><span>风险变化</span><strong>{{ result.risk_changes.length }}</strong></article>
    </section>
    <section class="version-diff-grid">
      <div class="panel"><div class="panel-title"><h2>基础版本</h2></div><div class="diff-document"><div v-for="(item,index) in changedSegments" :key="`base-${index}`" :data-diff-index="index" :class="['diff-block',item.change_type]">{{ item.base_text || '—' }}</div></div></div>
      <div class="panel"><div class="panel-title"><h2>目标版本</h2></div><div class="diff-document"><div v-for="(item,index) in changedSegments" :key="`target-${index}`" :class="['diff-block',item.change_type]">{{ item.target_text || '—' }}</div></div></div>
    </section>
    <section class="panel risk-change-panel"><div class="panel-title"><h2>风险变化</h2><span>“风险消失”仅表示未再次识别，不自动等同于已整改</span></div><el-table :data="result.risk_changes"><el-table-column label="状态" width="130"><template #default="s"><el-tag :type="s.row.status==='added'||s.row.status==='severity_increased'?'danger':s.row.status==='removed'||s.row.status==='severity_decreased'?'success':s.row.status==='uncertain_match'?'warning':'info'">{{statusLabel[s.row.status]}}</el-tag></template></el-table-column><el-table-column label="风险" min-width="180"><template #default="s">{{(s.row.target_risk||s.row.base_risk)?.风险标题 || (s.row.target_risk||s.row.base_risk)?.title}}</template></el-table-column><el-table-column prop="match_score" label="匹配分" width="90" /><el-table-column prop="explanation" label="说明" min-width="260" /><el-table-column label="操作" width="90"><template #default="s"><el-button text type="primary" @click="openFeedback(s.row)">反馈</el-button></template></el-table-column></el-table></section>
  </template>
  <el-dialog v-model="feedbackOpen" title="风险反馈" width="520px"><el-form label-position="top"><el-form-item label="反馈类型"><el-select v-model="feedback.feedback_type"><el-option label="确认风险" value="confirmed_risk" /><el-option label="不是风险" value="not_a_risk" /><el-option label="风险等级不准确" value="inaccurate_severity" /><el-option label="修改建议不可用" value="unusable_suggestion" /></el-select></el-form-item><el-form-item v-if="feedback.feedback_type==='inaccurate_severity'" label="建议等级"><el-select v-model="feedback.suggested_severity"><el-option label="低" value="low"/><el-option label="中" value="medium"/><el-option label="高" value="high"/><el-option label="严重" value="critical"/></el-select></el-form-item><el-form-item label="反馈原因"><el-input v-model="feedback.reason" type="textarea" :rows="4" /></el-form-item></el-form><el-alert title="反馈用于规则优化分析，不会自动训练模型。" type="info" :closable="false"/><template #footer><el-button @click="feedbackOpen=false">取消</el-button><el-button type="primary" @click="submitFeedback">提交</el-button></template></el-dialog>
</template>
