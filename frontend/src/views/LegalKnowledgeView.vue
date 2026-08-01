<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { api } from '../api'
import EmptyState from '../components/EmptyState.vue'
import ErrorState from '../components/ErrorState.vue'
import LoadingState from '../components/LoadingState.vue'

type AnyRecord = Record<string, any>

const activeTab = ref('documents')
const loading = ref(false)
const error = ref('')
const documents = ref<AnyRecord[]>([])
const articles = ref<AnyRecord[]>([])
const rules = ref<AnyRecord[]>([])
const versions = ref<AnyRecord[]>([])
const clauses = ref<AnyRecord[]>([])
const documentFilters = ref({ name: '', document_type: '', effect_status: '' })
const articleFilters = ref({ law_name: '', article_no: '', keyword: '', legal_topic: '', contract_type: '' })

const documentDialog = ref(false)
const articleDialog = ref(false)
const ruleDialog = ref(false)
const detailDrawer = ref(false)
const selectedArticle = ref<AnyRecord | null>(null)
const editingDocumentId = ref('')
const editingArticleId = ref('')
const editingRuleId = ref('')

const blankDocument = () => ({
  name: '', document_type: 'law', issuing_authority: '', document_number: '',
  publication_date: null, effective_date: null, expiry_date: null,
  effect_status: 'pending_effective', version_number: '1.0', official_source_url: '',
  source_name: '', full_text: '', verification_status: 'pending_verification',
  is_enabled: true, change_summary: '',
})
const blankArticle = () => ({
  legal_document_id: '', legal_document_version_id: '', chapter_no: '', chapter_name: '',
  article_no: '', article_no_numeric: null, title: '', content: '', keywords: [],
  legal_topics: [], contract_types: ['all'], is_effective: false,
  verification_status: 'pending_verification',
})
const blankRule = () => ({
  rule_code: '', rule_name: '', contract_types: ['all'], clause_type: '', risk_level: 'medium',
  trigger_condition: '', keywords: [], model_prompt: '仅依据系统提供的已核验法律条文判断，不得补造法条。',
  risk_description: '', possible_consequence: '', modification_advice: '',
  recommended_clause: '', is_enabled: true, legal_article_ids: [],
})
const documentForm = ref<AnyRecord>(blankDocument())
const articleForm = ref<AnyRecord>(blankArticle())
const ruleForm = ref<AnyRecord>(blankRule())

const effectLabels: Record<string, string> = {
  effective: '有效', amended: '已修改', repealed: '已废止', pending_effective: '尚未施行',
}
const verificationLabels: Record<string, string> = {
  pending_verification: '待核验', verified: '已核验', rejected: '已驳回',
}
const riskLabels: Record<string, string> = { low: '低', medium: '中', high: '高', critical: '严重' }
const currentDocument = computed(() => documents.value.find(item => item.id === articleForm.value.legal_document_id))
const availableVersions = computed(() => versions.value.filter(item => item.legal_document_id === articleForm.value.legal_document_id))

function paramsOf(value: AnyRecord) {
  return Object.fromEntries(Object.entries(value).filter(([, item]) => item !== '' && item !== null && item !== undefined))
}

async function loadAll() {
  loading.value = true
  error.value = ''
  try {
    const [docRes, articleRes, ruleRes, versionRes, clauseRes] = await Promise.all([
      api.get('/legal-knowledge/documents', { params: { ...paramsOf(documentFilters.value), include_disabled: true } }),
      api.get('/legal-knowledge/articles', { params: { ...paramsOf(articleFilters.value), include_unverified: true } }),
      api.get('/legal-knowledge/rules'),
      api.get('/legal-knowledge/versions'),
      api.get('/legal-knowledge/standard-clauses'),
    ])
    documents.value = docRes.data.data.items
    articles.value = articleRes.data.data.items
    rules.value = ruleRes.data.data.items
    versions.value = versionRes.data.data
    clauses.value = clauseRes.data.data
  } catch (cause: any) {
    error.value = cause?.response?.data?.detail || '法律知识库加载失败'
  } finally {
    loading.value = false
  }
}

async function importDemo() {
  const response = await api.post('/legal-knowledge/imports/demo')
  ElMessage.success(response.data.message || '演示结构已导入')
  await loadAll()
}

function createDocument() {
  editingDocumentId.value = ''
  documentForm.value = blankDocument()
  documentDialog.value = true
}
function editDocument(row: AnyRecord) {
  editingDocumentId.value = row.id
  documentForm.value = { ...row, official_source_url: row.official_source_url || '', change_summary: '' }
  documentDialog.value = true
}
async function saveDocument() {
  const payload = { ...documentForm.value }
  for (const key of ['id', 'created_by', 'created_at', 'updated_at']) delete payload[key]
  if (editingDocumentId.value) await api.patch(`/legal-knowledge/documents/${editingDocumentId.value}`, payload)
  else await api.post('/legal-knowledge/documents', payload)
  documentDialog.value = false
  ElMessage.success(editingDocumentId.value ? '法律新版本已创建' : '法律文件已创建')
  await loadAll()
}
async function toggleDocument(row: AnyRecord) {
  await api.patch(`/legal-knowledge/documents/${row.id}`, { is_enabled: !row.is_enabled })
  ElMessage.success(row.is_enabled ? '法律文件已停用' : '法律文件已启用')
  await loadAll()
}

function createArticle() {
  editingArticleId.value = ''
  articleForm.value = blankArticle()
  articleDialog.value = true
}
function editArticle(row: AnyRecord) {
  editingArticleId.value = row.id
  articleForm.value = {
    ...row, keywords: [...row.keywords], legal_topics: [...row.legal_topics], contract_types: [...row.contract_types],
  }
  articleDialog.value = true
}
function selectDocumentVersion() {
  articleForm.value.legal_document_version_id = availableVersions.value[0]?.id || ''
}
async function saveArticle() {
  const payload = { ...articleForm.value }
  for (const key of ['id', 'law_name', 'law_version', 'effect_status', 'source_name', 'source_url', 'created_by', 'created_at', 'updated_at']) delete payload[key]
  if (editingArticleId.value) {
    delete payload.legal_document_id
    delete payload.legal_document_version_id
    await api.patch(`/legal-knowledge/articles/${editingArticleId.value}`, payload)
  } else await api.post('/legal-knowledge/articles', payload)
  articleDialog.value = false
  ElMessage.success(editingArticleId.value ? '法律条文已更新' : '法律条文已创建')
  await loadAll()
}
async function deactivateArticle(row: AnyRecord) {
  await ElMessageBox.confirm(`确认停用“${row.law_name} ${row.article_no}”吗？`, '停用法律条文', { type: 'warning' })
  await api.delete(`/legal-knowledge/articles/${row.id}`)
  ElMessage.success('法律条文已停用')
  await loadAll()
}
function showArticle(row: AnyRecord) {
  selectedArticle.value = row
  detailDrawer.value = true
}

function createRule() {
  editingRuleId.value = ''
  ruleForm.value = blankRule()
  ruleDialog.value = true
}
function editRule(row: AnyRecord) {
  editingRuleId.value = row.id
  ruleForm.value = { ...row, contract_types: [...row.contract_types], keywords: [...row.keywords], legal_article_ids: [...row.legal_article_ids] }
  ruleDialog.value = true
}
async function saveRule() {
  const payload = { ...ruleForm.value }
  for (const key of ['id', 'created_by', 'created_at', 'updated_at']) delete payload[key]
  if (editingRuleId.value) {
    delete payload.rule_code
    await api.patch(`/legal-knowledge/rules/${editingRuleId.value}`, payload)
  } else await api.post('/legal-knowledge/rules', payload)
  ruleDialog.value = false
  ElMessage.success(editingRuleId.value ? '风险规则已更新' : '风险规则已创建')
  await loadAll()
}
async function toggleRule(row: AnyRecord) {
  await api.patch(`/legal-knowledge/rules/${row.id}`, { is_enabled: !row.is_enabled })
  ElMessage.success(row.is_enabled ? '风险规则已停用' : '风险规则已启用')
  await loadAll()
}

onMounted(loadAll)
</script>

<template>
  <div class="legal-page">
    <header class="legal-hero">
      <div><span>LEGAL KNOWLEDGE</span><h1>自建法律知识库</h1><p>结构化管理法律版本、具体条文、合同风险规则与审查引用。只有已核验且当前有效的法条会进入正式审查。</p></div>
      <div><el-button :loading="loading" @click="loadAll">刷新</el-button><el-button type="primary" @click="importDemo">导入待核验演示结构</el-button></div>
    </header>
    <el-alert title="AI 生成或整理的内容只能处于“待核验”状态；必须提供官方来源并经管理员确认后，才能作为审查法律依据。" type="warning" show-icon :closable="false" />
    <LoadingState v-if="loading && !documents.length" title="正在加载法律知识库" />
    <ErrorState v-else-if="error" title="法律知识库暂不可用" :description="error" @retry="loadAll" />
    <section v-else class="panel legal-workspace">
      <el-tabs v-model="activeTab">
        <el-tab-pane label="法律法规" name="documents">
          <div class="toolbar"><el-input v-model="documentFilters.name" clearable placeholder="按名称查询" /><el-input v-model="documentFilters.document_type" clearable placeholder="文件类型" /><el-select v-model="documentFilters.effect_status" clearable placeholder="效力状态"><el-option v-for="(label,value) in effectLabels" :key="value" :label="label" :value="value" /></el-select><el-button @click="loadAll">查询</el-button><el-button type="primary" @click="createDocument">新增法律文件</el-button></div>
          <el-table :data="documents">
            <el-table-column prop="name" label="法律名称" min-width="220" />
            <el-table-column prop="document_type" label="文件类型" width="120" />
            <el-table-column prop="issuing_authority" label="发布机关" min-width="150" />
            <el-table-column prop="document_number" label="文号" width="150" />
            <el-table-column label="效力" width="100"><template #default="s"><el-tag :type="s.row.effect_status === 'effective' ? 'success' : s.row.effect_status === 'repealed' ? 'danger' : 'warning'">{{ effectLabels[s.row.effect_status] }}</el-tag></template></el-table-column>
            <el-table-column label="核验" width="100"><template #default="s"><el-tag :type="s.row.verification_status === 'verified' ? 'success' : 'warning'">{{ verificationLabels[s.row.verification_status] }}</el-tag></template></el-table-column>
            <el-table-column prop="version_number" label="当前版本" width="100" />
            <el-table-column prop="updated_at" label="更新时间" width="180" />
            <el-table-column label="操作" width="230" fixed="right"><template #default="s"><el-button text type="primary" @click="editDocument(s.row)">编辑/新版本</el-button><el-button text @click="activeTab='articles'; articleFilters.law_name=s.row.name; loadAll()">查看条文</el-button><el-button text :type="s.row.is_enabled ? 'danger' : 'success'" @click="toggleDocument(s.row)">{{ s.row.is_enabled ? '停用' : '启用' }}</el-button></template></el-table-column>
          </el-table>
          <EmptyState v-if="!documents.length" title="暂无法律文件" description="可先导入待核验演示结构，或新增来自官方来源的法律文件。" />
        </el-tab-pane>

        <el-tab-pane label="法律条文" name="articles">
          <div class="toolbar"><el-input v-model="articleFilters.law_name" clearable placeholder="法律名称" /><el-input v-model="articleFilters.article_no" clearable placeholder="条号" /><el-input v-model="articleFilters.keyword" clearable placeholder="关键词" /><el-input v-model="articleFilters.legal_topic" clearable placeholder="法律主题" /><el-input v-model="articleFilters.contract_type" clearable placeholder="合同类型" /><el-button @click="loadAll">查询</el-button><el-button type="primary" @click="createArticle">新增法律条文</el-button></div>
          <el-table :data="articles" @row-click="showArticle">
            <el-table-column prop="law_name" label="法律名称" min-width="200" />
            <el-table-column prop="article_no" label="条号" width="120" />
            <el-table-column prop="title" label="条文标题" min-width="160" />
            <el-table-column label="法律主题" min-width="160"><template #default="s">{{ s.row.legal_topics.join('、') || '未设置' }}</template></el-table-column>
            <el-table-column label="适用合同" min-width="150"><template #default="s">{{ s.row.contract_types.join('、') || '不限' }}</template></el-table-column>
            <el-table-column label="状态" width="110"><template #default="s"><el-tag :type="s.row.is_effective && s.row.verification_status === 'verified' ? 'success' : 'warning'">{{ s.row.is_effective ? verificationLabels[s.row.verification_status] : '停用/待核验' }}</el-tag></template></el-table-column>
            <el-table-column label="操作" width="150" fixed="right"><template #default="s"><el-button text type="primary" @click.stop="editArticle(s.row)">编辑</el-button><el-button text type="danger" :disabled="!s.row.is_effective" @click.stop="deactivateArticle(s.row)">停用</el-button></template></el-table-column>
          </el-table>
          <EmptyState v-if="!articles.length" title="暂无匹配条文" description="待核验条文不会提供给员工搜索，也不会进入 AI 审查。" />
        </el-tab-pane>

        <el-tab-pane label="风险规则" name="rules">
          <div class="toolbar end"><el-button type="primary" @click="createRule">新增风险规则</el-button></div>
          <el-table :data="rules">
            <el-table-column prop="rule_code" label="规则编码" width="150" />
            <el-table-column prop="rule_name" label="规则名称" min-width="180" />
            <el-table-column prop="clause_type" label="条款类型" width="120" />
            <el-table-column label="合同类型" min-width="140"><template #default="s">{{ s.row.contract_types.join('、') }}</template></el-table-column>
            <el-table-column label="等级" width="85"><template #default="s"><el-tag :type="['high','critical'].includes(s.row.risk_level) ? 'danger' : s.row.risk_level === 'medium' ? 'warning' : 'info'">{{ riskLabels[s.row.risk_level] }}</el-tag></template></el-table-column>
            <el-table-column label="关联法条" width="100"><template #default="s">{{ s.row.legal_article_ids.length }} 条</template></el-table-column>
            <el-table-column label="状态" width="85"><template #default="s"><el-tag :type="s.row.is_enabled ? 'success' : 'info'">{{ s.row.is_enabled ? '启用' : '停用' }}</el-tag></template></el-table-column>
            <el-table-column label="操作" width="150"><template #default="s"><el-button text type="primary" @click="editRule(s.row)">编辑</el-button><el-button text :type="s.row.is_enabled ? 'danger' : 'success'" @click="toggleRule(s.row)">{{ s.row.is_enabled ? '停用' : '启用' }}</el-button></template></el-table-column>
          </el-table>
        </el-tab-pane>

        <el-tab-pane label="标准条款" name="clauses">
          <div class="clause-grid"><article v-for="item in clauses" :key="item.rule_id"><span>{{ item.clause_type }} · {{ item.contract_types }}</span><h3>{{ item.rule_name }}</h3><p>{{ item.recommended_clause }}</p></article></div>
          <EmptyState v-if="!clauses.length" title="暂无标准条款" description="在风险规则中填写推荐条款后会自动汇总到这里。" />
        </el-tab-pane>

        <el-tab-pane label="版本记录" name="versions">
          <el-table :data="versions"><el-table-column prop="legal_document_id" label="法律文件 ID" min-width="210" /><el-table-column prop="version_number" label="版本" width="110" /><el-table-column label="效力" width="100"><template #default="s">{{ effectLabels[s.row.effect_status] }}</template></el-table-column><el-table-column label="核验状态" width="110"><template #default="s">{{ verificationLabels[s.row.verification_status] }}</template></el-table-column><el-table-column prop="change_summary" label="变更说明" min-width="220" /><el-table-column prop="created_by" label="操作人" width="170" /><el-table-column prop="created_at" label="创建时间" width="190" /></el-table>
        </el-tab-pane>
      </el-tabs>
    </section>

    <el-dialog v-model="documentDialog" :title="editingDocumentId ? '编辑法律文件并创建新版本' : '新增法律文件'" width="760px">
      <el-form label-position="top"><div class="form-grid"><el-form-item label="名称"><el-input v-model="documentForm.name" /></el-form-item><el-form-item label="文件类型"><el-input v-model="documentForm.document_type" /></el-form-item><el-form-item label="发布机关"><el-input v-model="documentForm.issuing_authority" /></el-form-item><el-form-item label="文号"><el-input v-model="documentForm.document_number" /></el-form-item><el-form-item label="公布日期"><el-date-picker v-model="documentForm.publication_date" value-format="YYYY-MM-DD" /></el-form-item><el-form-item label="施行日期"><el-date-picker v-model="documentForm.effective_date" value-format="YYYY-MM-DD" /></el-form-item><el-form-item label="失效日期"><el-date-picker v-model="documentForm.expiry_date" value-format="YYYY-MM-DD" /></el-form-item><el-form-item label="效力状态"><el-select v-model="documentForm.effect_status"><el-option v-for="(label,value) in effectLabels" :key="value" :label="label" :value="value" /></el-select></el-form-item><el-form-item label="版本号"><el-input v-model="documentForm.version_number" /></el-form-item><el-form-item label="核验状态"><el-select v-model="documentForm.verification_status"><el-option v-for="(label,value) in verificationLabels" :key="value" :label="label" :value="value" /></el-select></el-form-item></div><el-form-item label="来源名称"><el-input v-model="documentForm.source_name" /></el-form-item><el-form-item label="官方来源地址"><el-input v-model="documentForm.official_source_url" placeholder="标记已核验时必填" /></el-form-item><el-form-item label="法律全文"><el-input v-model="documentForm.full_text" type="textarea" :rows="7" placeholder="不得让 AI 生成并直接标记为已核验" /></el-form-item><el-form-item v-if="editingDocumentId" label="版本变更说明"><el-input v-model="documentForm.change_summary" /></el-form-item></el-form>
      <template #footer><el-button @click="documentDialog=false">取消</el-button><el-button type="primary" @click="saveDocument">保存</el-button></template>
    </el-dialog>

    <el-dialog v-model="articleDialog" :title="editingArticleId ? '编辑法律条文' : '新增法律条文'" width="760px">
      <el-form label-position="top"><div class="form-grid"><el-form-item label="所属法律文件"><el-select v-model="articleForm.legal_document_id" :disabled="!!editingArticleId" filterable @change="selectDocumentVersion"><el-option v-for="item in documents" :key="item.id" :label="item.name" :value="item.id" /></el-select></el-form-item><el-form-item label="具体法律版本"><el-select v-model="articleForm.legal_document_version_id" :disabled="!!editingArticleId"><el-option v-for="item in availableVersions" :key="item.id" :label="item.version_number" :value="item.id" /></el-select></el-form-item><el-form-item label="章节编号"><el-input v-model="articleForm.chapter_no" /></el-form-item><el-form-item label="章节名称"><el-input v-model="articleForm.chapter_name" /></el-form-item><el-form-item label="条号"><el-input v-model="articleForm.article_no" /></el-form-item><el-form-item label="数字条号"><el-input-number v-model="articleForm.article_no_numeric" :min="0" /></el-form-item><el-form-item label="条文标题"><el-input v-model="articleForm.title" /></el-form-item><el-form-item label="核验状态"><el-select v-model="articleForm.verification_status"><el-option v-for="(label,value) in verificationLabels" :key="value" :label="label" :value="value" /></el-select></el-form-item></div><el-form-item label="条文正文"><el-input v-model="articleForm.content" type="textarea" :rows="6" /></el-form-item><div class="form-grid"><el-form-item label="关键词"><el-select v-model="articleForm.keywords" multiple allow-create filterable /></el-form-item><el-form-item label="法律主题"><el-select v-model="articleForm.legal_topics" multiple allow-create filterable /></el-form-item><el-form-item label="适用合同类型"><el-select v-model="articleForm.contract_types" multiple allow-create filterable /></el-form-item><el-form-item label="是否有效"><el-switch v-model="articleForm.is_effective" :disabled="articleForm.verification_status !== 'verified'" /></el-form-item></div><el-alert v-if="currentDocument?.verification_status !== 'verified'" title="所属法律文件尚未核验，本条文不会进入正式审查。" type="warning" :closable="false" /></el-form>
      <template #footer><el-button @click="articleDialog=false">取消</el-button><el-button type="primary" @click="saveArticle">保存</el-button></template>
    </el-dialog>

    <el-dialog v-model="ruleDialog" :title="editingRuleId ? '编辑合同风险规则' : '新增合同风险规则'" width="780px">
      <el-form label-position="top"><div class="form-grid"><el-form-item label="规则编码"><el-input v-model="ruleForm.rule_code" :disabled="!!editingRuleId" /></el-form-item><el-form-item label="规则名称"><el-input v-model="ruleForm.rule_name" /></el-form-item><el-form-item label="合同类型"><el-select v-model="ruleForm.contract_types" multiple allow-create filterable /></el-form-item><el-form-item label="条款类型"><el-input v-model="ruleForm.clause_type" /></el-form-item><el-form-item label="风险等级"><el-select v-model="ruleForm.risk_level"><el-option v-for="(label,value) in riskLabels" :key="value" :label="label" :value="value" /></el-select></el-form-item><el-form-item label="关键词"><el-select v-model="ruleForm.keywords" multiple allow-create filterable /></el-form-item></div><el-form-item label="触发条件"><el-input v-model="ruleForm.trigger_condition" /></el-form-item><el-form-item label="模型识别提示"><el-input v-model="ruleForm.model_prompt" type="textarea" :rows="2" /></el-form-item><el-form-item label="风险说明"><el-input v-model="ruleForm.risk_description" type="textarea" :rows="2" /></el-form-item><el-form-item label="可能后果"><el-input v-model="ruleForm.possible_consequence" type="textarea" :rows="2" /></el-form-item><el-form-item label="修改建议"><el-input v-model="ruleForm.modification_advice" type="textarea" :rows="2" /></el-form-item><el-form-item label="推荐条款"><el-input v-model="ruleForm.recommended_clause" type="textarea" :rows="3" /></el-form-item><el-form-item label="关联多个法律条文"><el-select v-model="ruleForm.legal_article_ids" multiple filterable><el-option v-for="item in articles" :key="item.id" :label="`${item.law_name} ${item.article_no}（${verificationLabels[item.verification_status]}）`" :value="item.id" /></el-select></el-form-item><el-form-item label="启用规则"><el-switch v-model="ruleForm.is_enabled" /></el-form-item></el-form>
      <template #footer><el-button @click="ruleDialog=false">取消</el-button><el-button type="primary" @click="saveRule">保存</el-button></template>
    </el-dialog>

    <el-drawer v-model="detailDrawer" title="法律条文详情" size="560px"><template v-if="selectedArticle"><div class="detail-tags"><el-tag>{{ selectedArticle.law_version }}</el-tag><el-tag :type="selectedArticle.verification_status === 'verified' ? 'success' : 'warning'">{{ verificationLabels[selectedArticle.verification_status] }}</el-tag><el-tag>{{ effectLabels[selectedArticle.effect_status] }}</el-tag></div><h2>{{ selectedArticle.law_name }} {{ selectedArticle.article_no }}</h2><h3>{{ selectedArticle.title }}</h3><p class="article-content">{{ selectedArticle.content }}</p><el-descriptions :column="1" border><el-descriptions-item label="法律主题">{{ selectedArticle.legal_topics.join('、') || '未设置' }}</el-descriptions-item><el-descriptions-item label="适用合同">{{ selectedArticle.contract_types.join('、') || '不限' }}</el-descriptions-item><el-descriptions-item label="来源">{{ selectedArticle.source_name }}</el-descriptions-item><el-descriptions-item label="官方地址"><a v-if="selectedArticle.source_url" :href="selectedArticle.source_url" target="_blank" rel="noopener noreferrer">打开官方来源</a><span v-else>待核验，未提供</span></el-descriptions-item></el-descriptions></template></el-drawer>
  </div>
</template>

<style scoped>
.legal-page{display:grid;gap:18px}.legal-hero{display:flex;justify-content:space-between;gap:24px;align-items:flex-end;padding:28px;border-radius:18px;background:linear-gradient(135deg,#173e36,#285c50);color:white}.legal-hero span{font-size:12px;letter-spacing:.18em;opacity:.75}.legal-hero h1{margin:8px 0;font-size:28px}.legal-hero p{max-width:760px;margin:0;color:#d9ebe6;line-height:1.7}.legal-workspace{padding:20px}.toolbar{display:flex;gap:10px;align-items:center;margin:4px 0 18px}.toolbar .el-input,.toolbar .el-select{width:170px}.toolbar.end{justify-content:flex-end}.form-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:0 18px}.clause-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:14px}.clause-grid article{padding:18px;border:1px solid #e4ebe8;border-radius:14px;background:#fbfdfc}.clause-grid span{color:#69827b;font-size:12px}.clause-grid h3{margin:8px 0}.clause-grid p,.article-content{white-space:pre-wrap;line-height:1.8;color:#334b45}.detail-tags{display:flex;gap:8px;margin-bottom:16px}@media(max-width:900px){.legal-hero{align-items:flex-start;flex-direction:column}.toolbar{flex-wrap:wrap}.form-grid{grid-template-columns:1fr}}
</style>
