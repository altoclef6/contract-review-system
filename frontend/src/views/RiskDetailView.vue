<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ArrowLeft, DocumentChecked, Refresh } from '@element-plus/icons-vue'
import EmptyState from '../components/EmptyState.vue'
import ErrorState from '../components/ErrorState.vue'
import PageHeader from '../components/PageHeader.vue'
import RiskLevelTag from '../components/RiskLevelTag.vue'
import StatusTag from '../components/StatusTag.vue'
import { useAuthStore } from '../stores/auth'
import { addRiskComment, assignRisk, fetchRisk, saveRiskRevision, transitionRisk, type RiskRecord, type RiskStatus } from '../services/risks'

const route = useRoute(); const router = useRouter(); const auth = useAuthStore()
const risk = ref<RiskRecord | null>(null); const loading = ref(false); const saving = ref(false); const error = ref('')
const comment = ref(''); const revisedClause = ref(''); const assigneeId = ref('')
let controller: AbortController | null = null
const isReviewer = computed(() => ['admin', 'legal'].includes(auth.user?.role || ''))
const statusMap: Record<RiskStatus, { label: string; tone: 'neutral' | 'info' | 'success' | 'warning' | 'danger' }> = {
  pending_review: { label: '待复核', tone: 'warning' }, confirmed: { label: '已确认', tone: 'danger' }, rejected: { label: '已驳回', tone: 'neutral' }, remediating: { label: '整改中', tone: 'info' }, remediated: { label: '已整改', tone: 'success' }, closed: { label: '已关闭', tone: 'neutral' },
}
const actions = computed(() => {
  if (!risk.value) return []
  if (risk.value.status === 'pending_review' && isReviewer.value) return [{ key: 'confirm', label: '确认风险', type: 'danger' }, { key: 'reject', label: '驳回风险', type: 'default' }]
  if (risk.value.status === 'confirmed') return [{ key: 'start-remediation', label: '开始整改', type: 'primary' }, ...(isReviewer.value ? [{ key: 'close', label: '关闭风险', type: 'default' }] : [])]
  if (risk.value.status === 'rejected' && isReviewer.value) return [{ key: 'close', label: '关闭风险', type: 'default' }]
  if (risk.value.status === 'remediating') return [{ key: 'mark-remediated', label: '标记已整改', type: 'success' }]
  if (risk.value.status === 'remediated') return [{ key: 'start-remediation', label: '继续整改', type: 'primary' }, ...(isReviewer.value ? [{ key: 'close', label: '关闭风险', type: 'default' }] : [])]
  return []
})

async function load() {
  controller?.abort(); controller = new AbortController(); loading.value = true; error.value = ''
  try { risk.value = await fetchRisk(String(route.params.riskId), controller.signal); revisedClause.value = risk.value.revised_clause || ''; assigneeId.value = risk.value.assignee_id || '' }
  catch (cause: any) { if (cause?.code !== 'ERR_CANCELED') error.value = cause?.response?.data?.detail || '风险详情加载失败' }
  finally { loading.value = false }
}
async function runAction(action: string, label: string) {
  if (!risk.value) return
  try {
    const result = await ElMessageBox.prompt(`请输入“${label}”的原因或说明（可留空）`, label, { inputType: 'textarea', inputPlaceholder: '操作原因或复核意见', inputValidator: (value) => value.length <= 1000 || '最多 1000 个字符' })
    saving.value = true; risk.value = await transitionRisk(risk.value, action as any, result.value); ElMessage.success(`${label}成功`)
  } catch (cause: any) { if (cause !== 'cancel' && cause !== 'close') ElMessage.error(cause?.response?.data?.detail || `${label}失败`) }
  finally { saving.value = false }
}
async function saveClause() { if (!risk.value || !revisedClause.value.trim()) return ElMessage.warning('请输入人工修改条款'); saving.value = true; try { risk.value = await saveRiskRevision(risk.value, revisedClause.value); ElMessage.success('人工修改条款已保存') } catch (cause: any) { ElMessage.error(cause?.response?.data?.detail || '保存失败') } finally { saving.value = false } }
async function submitComment() { if (!risk.value || !comment.value.trim()) return; saving.value = true; try { risk.value = await addRiskComment(risk.value, comment.value); comment.value = ''; ElMessage.success('评论已添加') } catch (cause: any) { ElMessage.error(cause?.response?.data?.detail || '评论失败') } finally { saving.value = false } }
async function submitAssign() { if (!risk.value) return; saving.value = true; try { risk.value = await assignRisk(risk.value, assigneeId.value || null); ElMessage.success(assigneeId.value ? '负责人已分配' : '负责人已取消') } catch (cause: any) { ElMessage.error(cause?.response?.data?.detail || '分配失败') } finally { saving.value = false } }
function formatDate(value?: string | null) { return value ? new Date(value).toLocaleString('zh-CN', { hour12: false }) : '暂无' }
function basisText(value: Record<string, unknown>) {
  const name = value.title || value.name || value.document_id || '知识依据'
  const article = value.article_number ? ` · ${value.article_number}` : ''
  const status = value.status ? ` · ${value.status}` : ''
  return `${name}${article}${status}`
}
onMounted(load); onBeforeUnmount(() => controller?.abort())
</script>

<template>
  <div class="risk-detail page-stack">
    <PageHeader title="风险详情" description="复核结论、整改内容、评论与状态历史均保存到后端。" eyebrow="RISK REVIEW">
      <template #actions><el-button :icon="ArrowLeft" @click="router.push('/risks')">返回台账</el-button><el-button :icon="Refresh" :loading="loading" @click="load">刷新</el-button></template>
    </PageHeader>
    <ErrorState v-if="error" title="风险详情加载失败" :description="error" @retry="load" />
    <div v-else-if="risk" class="detail-grid" v-loading="loading">
      <main class="page-stack">
        <section class="panel hero"><div><RiskLevelTag :level="risk.severity"/><StatusTag :label="statusMap[risk.status].label" :tone="statusMap[risk.status].tone"/></div><h2>{{ risk.title }}</h2><p>{{ risk.contract_title || '独立审查' }} · {{ risk.contract_version ? `V${risk.contract_version}` : '暂无版本' }} · {{ risk.category }}</p><div class="actions"><el-button v-for="action in actions" :key="action.key" :type="action.type as any" :loading="saving" @click="runAction(action.key,action.label)">{{ action.label }}</el-button><el-button v-if="risk.review_id" :icon="DocumentChecked" @click="router.push(`/reader/${risk.review_id}`)">进入审查工作区</el-button></div></section>
        <section class="panel content"><h3>命中原文</h3><blockquote>{{ risk.matched_text || '该风险为缺失条款检查，没有命中原文。' }}</blockquote><dl class="metadata"><div><dt>原文位置</dt><dd>{{ risk.page_number ? `第 ${risk.page_number} 页` : risk.start_offset !== null && risk.start_offset !== undefined ? `字符 ${risk.start_offset}–${risk.end_offset}` : '暂无定位' }}</dd></div><div><dt>规则</dt><dd>{{ risk.rule_id || '语义分析' }}</dd></div><div><dt>检测来源</dt><dd>{{ risk.detection_source }}</dd></div><div><dt>AI 参与</dt><dd>{{ risk.ai_involved ? '是' : '否' }}</dd></div></dl></section>
        <section class="panel content"><h3>风险说明</h3><p>{{ risk.explanation || '暂无风险说明' }}</p><h3>修改建议</h3><p>{{ risk.recommendation || '暂无修改建议' }}</p></section>
        <section class="panel content"><h3>规则与知识依据</h3><div v-if="risk.legal_basis.length" class="basis"><article v-for="(basis,index) in risk.legal_basis" :key="index">{{ basisText(basis) }}</article></div><p v-else class="muted">暂无已验证知识依据</p></section>
        <section class="panel content"><h3>人工修改条款</h3><el-input v-model="revisedClause" type="textarea" :rows="6" maxlength="10000" show-word-limit placeholder="输入人工确认后的最终修改条款"/><el-button type="primary" :loading="saving" @click="saveClause">保存人工修改</el-button></section>
      </main>
      <aside class="page-stack">
        <section v-if="isReviewer" class="panel side"><h3>负责人</h3><el-input v-model="assigneeId" clearable placeholder="输入系统用户 ID"/><el-button :loading="saving" @click="submitAssign">保存分配</el-button><small>仅管理员或法务可分配；后端会校验用户是否存在。</small></section>
        <section class="panel side"><h3>添加评论</h3><el-input v-model="comment" type="textarea" :rows="3" maxlength="2000" show-word-limit placeholder="输入复核或整改说明"/><el-button type="primary" :loading="saving" @click="submitComment">添加评论</el-button></section>
        <section class="panel side"><h3>评论</h3><div v-if="risk.comments.length" class="timeline"><article v-for="item in [...risk.comments].reverse()" :key="item.comment_id"><strong>{{ item.author_id }}</strong><p>{{ item.content }}</p><small>{{ formatDate(item.created_at) }}</small></article></div><EmptyState v-else compact title="暂无评论" description="添加评论后会显示在这里。"/></section>
        <section class="panel side"><h3>状态历史</h3><div class="timeline"><article v-for="item in [...risk.state_history].reverse()" :key="item.event_id"><strong>{{ item.old_status ? `${statusMap[item.old_status].label} → ` : '' }}{{ statusMap[item.new_status].label }}</strong><p v-if="item.reason">{{ item.reason }}</p><small>{{ item.actor_id }} · {{ formatDate(item.created_at) }}</small></article></div></section>
        <section class="panel side"><h3>记录信息</h3><dl class="metadata"><div><dt>负责人</dt><dd>{{ risk.assignee_name || '未分配' }}</dd></div><div><dt>复核人</dt><dd>{{ risk.reviewer_id || '暂无' }}</dd></div><div><dt>发现时间</dt><dd>{{ formatDate(risk.created_at) }}</dd></div><div><dt>更新时间</dt><dd>{{ formatDate(risk.updated_at) }}</dd></div></dl></section>
      </aside>
    </div>
  </div>
</template>

<style scoped>
.page-stack { display:grid; gap:var(--space-5); }.detail-grid { display:grid; grid-template-columns:minmax(0,1fr) 340px; gap:var(--space-5); align-items:start; }.hero,.content,.side { padding:var(--space-5); }.hero>div:first-child,.actions { display:flex; gap:var(--space-2); flex-wrap:wrap; }.hero h2 { margin:var(--space-3) 0 var(--space-2); }.hero p,.content p,.muted { color:var(--text-secondary); line-height:1.75; }.actions { margin-top:var(--space-4); }.content h3,.side h3 { margin:0 0 var(--space-3); font-size:16px; }.content h3:not(:first-child) { margin-top:var(--space-5); }.content blockquote { margin:0; padding:var(--space-4); border-left:3px solid var(--primary); background:var(--surface-soft); color:var(--text-primary); white-space:pre-wrap; }.content>.el-button,.side>.el-button { margin-top:var(--space-3); }.metadata { display:grid; gap:10px; margin:var(--space-4) 0 0; }.metadata div { display:grid; grid-template-columns:80px 1fr; gap:var(--space-2); }.metadata dt { color:var(--text-muted); }.metadata dd { margin:0; overflow-wrap:anywhere; }.timeline { display:grid; gap:var(--space-3); }.timeline article { padding-left:var(--space-3); border-left:2px solid var(--border-strong); }.timeline p { margin:6px 0; color:var(--text-secondary); white-space:pre-wrap; }.timeline small,.side>small { display:block; margin-top:8px; color:var(--text-muted); line-height:1.5; }.basis article { padding:var(--space-3); background:var(--surface-soft); border:1px solid var(--border); border-radius:var(--radius-sm); overflow-wrap:anywhere; }
@media(max-width:1050px){.detail-grid{grid-template-columns:1fr}}
</style>
