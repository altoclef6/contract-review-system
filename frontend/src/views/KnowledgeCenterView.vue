
<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { api } from '../api'
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()
const loading = ref(false)
const entries = ref<any[]>([])
const selected = ref<any>(null)
const detailOpen = ref(false)
const history = ref<any[]>([])
const dialog = ref(false)
const historyOpen = ref(false)
const canManage = computed(() => ['admin', 'legal'].includes(auth.user?.role || ''))
const blank = () => ({ document_id: '', title: '', article_number: '', content: '', source_type: 'test_data', status: 'draft', issuing_authority: '', effective_date: null, expiry_date: null, source_url: '', contract_types: [], related_rule_ids: [] })
const form = ref<any>(blank())
const editingId = ref('')
const sourceLabels: Record<string,string> = { law:'正式法律', judicial_interpretation:'司法解释', regulation:'行政法规/规章', internal_policy:'内部制度', contract_template:'合同模板', review_guidance:'审查经验', test_data:'测试数据' }
const statusLabels: Record<string,string> = { draft:'草稿', effective:'有效', inactive:'停用', expired:'失效' }

async function load() {
  loading.value = true
  try { entries.value = (await api.get('/knowledge')).data.data.items }
  catch { ElMessage.error('知识库加载失败') }
  finally { loading.value = false }
}
function openDetail(row:any) { selected.value = row; detailOpen.value = true }
function create() { editingId.value = ''; form.value = blank(); dialog.value = true }
function edit(row:any) {
  editingId.value = row.id
  form.value = { ...row, source_url: row.source_url || '', contract_types: [...row.contract_types], related_rule_ids: [...row.related_rule_ids] }
  dialog.value = true
}
async function save() {
  const payload = { ...form.value }
  for (const key of ['id','version','created_at','updated_at','created_by','supersedes_id']) delete payload[key]
  if (editingId.value) { delete payload.document_id; await api.patch(`/knowledge/${editingId.value}`, payload) }
  else await api.post('/knowledge', payload)
  dialog.value = false
  ElMessage.success(editingId.value ? '知识新版本已创建' : '知识条目已创建')
  await load()
}
async function showHistory(row:any) { history.value = (await api.get(`/knowledge/${row.id}/history`)).data.data; historyOpen.value = true }
onMounted(load)
</script>

<template>
  <div class="page-head">
    <div><h1>知识库中心</h1><p>正式法规、内部制度、审查经验和测试数据分层管理，历史版本不被覆盖。</p></div>
    <div><el-button :loading="loading" @click="load">刷新</el-button><el-button v-if="canManage" type="primary" @click="create">新增知识</el-button></div>
  </div>
  <el-alert title="内置资料仅为项目参考，不代表完整或已核验的法律数据库。" type="warning" show-icon :closable="false" />
  <section class="panel table-panel center-table" v-loading="loading">
    <el-table :data="entries" @row-click="openDetail">
      <el-table-column prop="title" label="名称" min-width="180" />
      <el-table-column prop="article_number" label="条款编号" width="110" />
      <el-table-column label="来源类型" width="130"><template #default="s"><el-tag :type="['law','judicial_interpretation','regulation'].includes(s.row.source_type) ? 'danger' : s.row.source_type === 'test_data' ? 'info' : 'warning'">{{ sourceLabels[s.row.source_type] }}</el-tag></template></el-table-column>
      <el-table-column label="效力" width="85"><template #default="s"><el-tag :type="s.row.status === 'effective' ? 'success' : s.row.status === 'expired' ? 'danger' : 'info'">{{ statusLabels[s.row.status] }}</el-tag></template></el-table-column>
      <el-table-column prop="issuing_authority" label="发布机构" min-width="140" />
      <el-table-column prop="effective_date" label="生效日期" width="110" />
      <el-table-column prop="expiry_date" label="失效日期" width="110" />
      <el-table-column prop="version" label="版本" width="65" />
      <el-table-column prop="document_id" label="document_id" width="180" />
      <el-table-column label="操作" width="140"><template #default="s"><el-button text @click.stop="showHistory(s.row)">历史</el-button><el-button v-if="canManage" text type="primary" @click.stop="edit(s.row)">新版本</el-button></template></el-table-column>
    </el-table>
    <el-empty v-if="!loading && !entries.length" description="暂无知识条目" />
  </section>
  <el-drawer v-model="detailOpen" title="知识详情" size="520px">
    <template v-if="selected">
      <div class="knowledge-badges"><el-tag>{{ sourceLabels[selected.source_type] }}</el-tag><el-tag>{{ statusLabels[selected.status] }}</el-tag><el-tag>v{{ selected.version }}</el-tag></div>
      <h2>{{ selected.title }}</h2>
      <p class="knowledge-content">{{ selected.content }}</p>
      <el-descriptions :column="1" border>
        <el-descriptions-item label="条号">{{ selected.article_number || '未设置' }}</el-descriptions-item>
        <el-descriptions-item label="来源地址"><a v-if="selected.source_url" :href="selected.source_url" target="_blank" rel="noopener noreferrer">查看来源</a><span v-else>未提供</span></el-descriptions-item>
        <el-descriptions-item label="适用合同">{{ selected.contract_types.join('、') || '未限定' }}</el-descriptions-item>
        <el-descriptions-item label="关联规则">{{ selected.related_rule_ids.join('、') || '暂无' }}</el-descriptions-item>
        <el-descriptions-item label="关联风险">暂无真实关联统计</el-descriptions-item>
      </el-descriptions>
    </template>
  </el-drawer>
  <el-drawer v-model="historyOpen" title="版本历史" size="520px">
    <el-timeline><el-timeline-item v-for="item in history" :key="item.id" :timestamp="item.updated_at"><b>v{{ item.version }} · {{ statusLabels[item.status] }}</b><p>{{ item.title }}</p></el-timeline-item></el-timeline>
  </el-drawer>
  <el-dialog v-model="dialog" :title="editingId ? '创建知识新版本' : '新增知识条目'" width="680px">
    <el-form label-position="top">
      <el-form-item v-if="!editingId" label="document_id"><el-input v-model="form.document_id" placeholder="仅字母、数字、点、下划线和连字符" /></el-form-item>
      <el-form-item label="标题"><el-input v-model="form.title" /></el-form-item>
      <el-form-item label="正文"><el-input v-model="form.content" type="textarea" :rows="7" /></el-form-item>
      <div class="knowledge-form-grid">
        <el-form-item label="条款编号"><el-input v-model="form.article_number" /></el-form-item>
        <el-form-item label="来源类型"><el-select v-model="form.source_type"><el-option v-for="(label,value) in sourceLabels" :key="value" :label="label" :value="value" /></el-select></el-form-item>
        <el-form-item label="效力状态"><el-select v-model="form.status"><el-option v-for="(label,value) in statusLabels" :key="value" :label="label" :value="value" /></el-select></el-form-item>
        <el-form-item label="发布机构"><el-input v-model="form.issuing_authority" /></el-form-item>
        <el-form-item label="生效日期"><el-date-picker v-model="form.effective_date" value-format="YYYY-MM-DD" /></el-form-item>
        <el-form-item label="失效日期"><el-date-picker v-model="form.expiry_date" value-format="YYYY-MM-DD" /></el-form-item>
      </div>
      <el-form-item label="来源地址（必须真实存在）"><el-input v-model="form.source_url" /></el-form-item>
      <el-form-item label="适用合同类型"><el-select v-model="form.contract_types" multiple allow-create filterable /></el-form-item>
      <el-form-item label="关联规则"><el-select v-model="form.related_rule_ids" multiple allow-create filterable /></el-form-item>
    </el-form>
    <template #footer><el-button @click="dialog=false">取消</el-button><el-button type="primary" @click="save">保存</el-button></template>
  </el-dialog>
</template>
