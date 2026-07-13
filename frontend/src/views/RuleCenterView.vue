
<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { api } from '../api'
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()
const loading = ref(false)
const error = ref('')
const rules = ref<any[]>([])
const selected = ref<any>(null)
const detailOpen = ref(false)
const dialog = ref(false)
const form = ref<any>({})
const feedbackStats = ref<any>(null)
const canManage = computed(() => ['admin', 'legal'].includes(auth.user?.role || ''))
const severityMap: Record<string, string> = { critical: '严重', high: '高', medium: '中', low: '低' }

async function load() {
  loading.value = true
  error.value = ''
  try {
    rules.value = (await api.get('/rules')).data.data.items
    if (canManage.value) feedbackStats.value = (await api.get('/risk-feedback/statistics')).data.data
  }
  catch (e: any) { error.value = e.response?.data?.message || '规则加载失败' }
  finally { loading.value = false }
}
function openDetail(row: any) { selected.value = row; detailOpen.value = true }
function edit(row: any) {
  selected.value = row
  form.value = { enabled: row.enabled, severity: row.severity, contract_types: [...row.contract_types], display_name: row.name, business_description: row.description, recommendation: row.recommendation }
  dialog.value = true
}
async function save() {
  await api.patch(`/rules/${selected.value.rule_id}`, form.value)
  dialog.value = false
  ElMessage.success('规则配置已更新')
  await load()
}
onMounted(load)
</script>

<template>
  <div class="page-head">
    <div><h1>规则中心</h1><p>代码规则与安全业务配置统一查看；页面不接受 Python 或任意表达式。</p></div>
    <el-button :loading="loading" @click="load">刷新</el-button>
  </div>
  <el-alert v-if="error" :title="error" type="error" show-icon :closable="false" />
  <section v-if="feedbackStats" class="metrics comparison-metrics">
    <article><span>反馈总数</span><strong>{{ feedbackStats.total }}</strong></article>
    <article><span>确认率</span><strong>{{ feedbackStats.confirmation_rate == null ? '—' : `${feedbackStats.confirmation_rate}%` }}</strong></article>
    <article><span>等级调整</span><strong>{{ feedbackStats.severity_adjustment_count }}</strong></article>
    <article><span>建议不可用</span><strong>{{ feedbackStats.unusable_suggestion_count }}</strong></article>
  </section>
  <section class="panel table-panel center-table" v-loading="loading">
    <el-table :data="rules" @row-click="openDetail">
      <el-table-column prop="rule_id" label="规则编号" width="175" />
      <el-table-column prop="name" label="名称" min-width="150" />
      <el-table-column prop="category" label="风险类别" width="110" />
      <el-table-column label="合同类型" min-width="180"><template #default="s">{{ s.row.contract_types.join('、') }}</template></el-table-column>
      <el-table-column label="等级" width="80"><template #default="s"><el-tag :type="['high','critical'].includes(s.row.severity) ? 'danger' : s.row.severity === 'medium' ? 'warning' : 'success'">{{ severityMap[s.row.severity] }}</el-tag></template></el-table-column>
      <el-table-column prop="detection_method" label="检测方式" width="150" />
      <el-table-column label="状态" width="80"><template #default="s"><el-tag :type="s.row.enabled ? 'success' : 'info'">{{ s.row.enabled ? '启用' : '停用' }}</el-tag></template></el-table-column>
      <el-table-column prop="version" label="版本" width="70" />
      <el-table-column label="命中/确认/驳回" width="150"><template #default="s">{{ s.row.hit_count == null ? '暂无数据' : `${s.row.hit_count}/${s.row.confirmed_count}/${s.row.rejected_count}` }}</template></el-table-column>
      <el-table-column label="确认率" width="90"><template #default="s">{{ s.row.confirmation_rate == null ? '暂无数据' : `${s.row.confirmation_rate}%` }}</template></el-table-column>
      <el-table-column label="操作" width="90"><template #default="s"><el-button v-if="canManage" text type="primary" @click.stop="edit(s.row)">配置</el-button></template></el-table-column>
    </el-table>
    <el-empty v-if="!loading && !rules.length" description="暂无规则" />
  </section>
  <section v-if="feedbackStats" class="panel table-panel center-table">
    <div class="panel-title"><h2>最近反馈与待优化线索</h2><span>低确认率仅作为人工优化线索</span></div>
    <el-table :data="feedbackStats.recent_feedback">
      <el-table-column prop="rule_id" label="规则" width="180" />
      <el-table-column prop="contract_type" label="合同类型" width="130" />
      <el-table-column prop="feedback_type" label="反馈类型" width="180" />
      <el-table-column prop="reason" label="原因" min-width="220" show-overflow-tooltip />
      <el-table-column prop="created_at" label="时间" width="190" />
    </el-table>
    <el-empty v-if="!feedbackStats.recent_feedback.length" description="暂无真实反馈" />
  </section>
  <el-drawer v-model="detailOpen" title="规则详情" size="480px">
    <el-descriptions v-if="selected" :column="1" border>
      <el-descriptions-item label="规则编号">{{ selected.rule_id }}</el-descriptions-item>
      <el-descriptions-item label="描述">{{ selected.description }}</el-descriptions-item>
      <el-descriptions-item label="命中逻辑">{{ selected.match_logic_summary }}</el-descriptions-item>
      <el-descriptions-item label="排除逻辑">{{ selected.exclusion_logic_summary }}</el-descriptions-item>
      <el-descriptions-item label="标准建议">{{ selected.recommendation }}</el-descriptions-item>
      <el-descriptions-item label="测试样本">{{ selected.test_samples.join('；') }}</el-descriptions-item>
      <el-descriptions-item label="反馈统计">尚无真实人工反馈统计</el-descriptions-item>
    </el-descriptions>
  </el-drawer>
  <el-dialog v-model="dialog" title="安全规则配置" width="560px">
    <el-form label-position="top">
      <el-form-item label="显示名称"><el-input v-model="form.display_name" /></el-form-item>
      <el-form-item label="启用状态"><el-switch v-model="form.enabled" /></el-form-item>
      <el-form-item label="风险等级"><el-select v-model="form.severity"><el-option v-for="(label, value) in severityMap" :key="value" :label="label" :value="value" /></el-select></el-form-item>
      <el-form-item label="适用合同类型"><el-select v-model="form.contract_types" multiple allow-create filterable /></el-form-item>
      <el-form-item label="业务说明"><el-input v-model="form.business_description" type="textarea" :rows="3" /></el-form-item>
      <el-form-item label="标准建议"><el-input v-model="form.recommendation" type="textarea" :rows="4" /></el-form-item>
    </el-form>
    <template #footer><el-button @click="dialog=false">取消</el-button><el-button type="primary" @click="save">保存</el-button></template>
  </el-dialog>
</template>
