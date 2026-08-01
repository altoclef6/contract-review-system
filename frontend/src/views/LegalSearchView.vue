<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { api } from '../api'
import EmptyState from '../components/EmptyState.vue'

const loading = ref(false)
const articles = ref<any[]>([])
const detail = ref<any>()
const drawer = ref(false)
const filters = ref({ law_name: '', article_no: '', keyword: '', legal_topic: '', contract_type: '' })

async function search() {
  loading.value = true
  try {
    const params = Object.fromEntries(Object.entries(filters.value).filter(([, value]) => value))
    articles.value = (await api.get('/legal-knowledge/articles', { params })).data.data.items
  } catch (cause: any) {
    ElMessage.error(cause?.response?.data?.detail || '法律条文检索失败')
  } finally { loading.value = false }
}
function show(row: any) { detail.value = row; drawer.value = true }
onMounted(search)
</script>

<template>
  <div class="search-page">
    <header><div><span>VERIFIED SOURCES ONLY</span><h1>已核验法律条文检索</h1><p>员工仅能查看已公开、已核验且当前有效的条文；待核验、停用和失效内容不会出现在结果中。</p></div></header>
    <section class="panel filters"><el-input v-model="filters.law_name" clearable placeholder="法律名称" /><el-input v-model="filters.article_no" clearable placeholder="条号" /><el-input v-model="filters.keyword" clearable placeholder="关键词" /><el-input v-model="filters.legal_topic" clearable placeholder="法律主题" /><el-input v-model="filters.contract_type" clearable placeholder="合同类型" /><el-button type="primary" :loading="loading" @click="search">查询</el-button></section>
    <section class="results" v-loading="loading"><button v-for="item in articles" :key="item.id" class="article-card" @click="show(item)"><div><el-tag type="success">已核验</el-tag><span>{{ item.law_version }}</span></div><h2>《{{ item.law_name }}》{{ item.article_no }}</h2><h3>{{ item.title }}</h3><p>{{ item.content }}</p><small>{{ item.source_name }} · 更新于 {{ item.updated_at }}</small></button><EmptyState v-if="!loading && !articles.length" title="未找到已核验法律条文" description="系统不会用待核验数据或 AI 生成内容填充检索结果。" /></section>
    <el-drawer v-model="drawer" title="法律条文详情" size="560px"><template v-if="detail"><h2>《{{ detail.law_name }}》{{ detail.article_no }}</h2><h3>{{ detail.title }}</h3><p class="content">{{ detail.content }}</p><el-descriptions :column="1" border><el-descriptions-item label="版本">{{ detail.law_version }}</el-descriptions-item><el-descriptions-item label="法律主题">{{ detail.legal_topics.join('、') || '未设置' }}</el-descriptions-item><el-descriptions-item label="来源">{{ detail.source_name }}</el-descriptions-item><el-descriptions-item label="官方来源"><a v-if="detail.source_url" :href="detail.source_url" target="_blank" rel="noopener noreferrer">打开官方来源</a><span v-else>未提供</span></el-descriptions-item></el-descriptions></template></el-drawer>
  </div>
</template>

<style scoped>
.search-page{display:grid;gap:18px}.search-page>header{padding:28px;border-radius:18px;background:#173e36;color:white}.search-page>header span{font-size:12px;letter-spacing:.15em;opacity:.7}.search-page h1{margin:8px 0}.search-page>header p{margin:0;color:#d8e8e3}.filters{display:flex;gap:10px;padding:16px;flex-wrap:wrap}.filters .el-input{width:170px}.results{display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:14px;min-height:180px}.article-card{display:grid;gap:8px;padding:20px;border:1px solid #e1e9e6;border-radius:14px;background:white;text-align:left;cursor:pointer}.article-card:hover{border-color:#6f968b;box-shadow:0 8px 24px rgba(33,70,61,.08)}.article-card>div{display:flex;align-items:center;gap:8px;color:#6d847e}.article-card h2,.article-card h3,.article-card p{margin:0}.article-card p,.content{white-space:pre-wrap;line-height:1.8;color:#435b55}.article-card small{color:#758a84}
</style>
