<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Download, Refresh } from '@element-plus/icons-vue'
import EmptyState from '../components/EmptyState.vue'
import ErrorState from '../components/ErrorState.vue'
import PageHeader from '../components/PageHeader.vue'
import RiskLevelTag from '../components/RiskLevelTag.vue'
import { api } from '../api'

const loading = ref(false)
const error = ref('')
const records = ref<any[]>([])

async function load() {
  loading.value = true
  error.value = ''
  try { records.value = (await api.get('/reviews')).data }
  catch (cause: any) { error.value = cause?.response?.data?.message || cause?.response?.data?.detail || '报告列表加载失败' }
  finally { loading.value = false }
}

async function download(row: any, type: string) {
  try {
    const response = await api.get(`/reviews/${row.review_id}/download`, { params: { file_type: type }, responseType: 'blob' })
    const url = URL.createObjectURL(response.data)
    const anchor = document.createElement('a')
    anchor.href = url
    anchor.download = `${row.review_id}.${type}`
    anchor.click()
    URL.revokeObjectURL(url)
  } catch (cause: any) { ElMessage.error(cause?.response?.data?.message || '报告下载失败') }
}

function formatDate(value?: string) { return value ? new Date(value).toLocaleString('zh-CN', { hour12: false }) : '暂无数据' }
onMounted(load)
</script>

<template>
  <div class="report-center">
    <PageHeader title="报告中心" description="查看当前授权范围内已经真实生成的审查报告。" eyebrow="REPORTS">
      <template #actions><el-button :icon="Refresh" :loading="loading" @click="load">刷新</el-button></template>
    </PageHeader>
    <ErrorState v-if="error" title="报告加载失败" :description="error" @retry="load" />
    <section v-else class="panel table-panel">
      <el-table v-loading="loading" :data="records" row-key="review_id">
        <el-table-column prop="file_name" label="合同名称" min-width="220" show-overflow-tooltip />
        <el-table-column prop="contract_type" label="合同类型" width="150" />
        <el-table-column label="风险等级" width="110"><template #default="{ row }"><RiskLevelTag v-if="row.overall_risk_level" :level="row.overall_risk_level"/><span v-else>暂无</span></template></el-table-column>
        <el-table-column prop="risk_score" label="风险评分" width="100" />
        <el-table-column label="生成时间" width="190"><template #default="{ row }">{{ formatDate(row.created_at) }}</template></el-table-column>
        <el-table-column label="导出" width="270" fixed="right"><template #default="{ row }">
          <el-button link type="primary" :icon="Download" @click="download(row, 'pdf')">PDF</el-button>
          <el-button link @click="download(row, 'docx')">Word</el-button>
          <el-button link @click="download(row, 'xlsx')">Excel</el-button>
          <el-button link @click="download(row, 'markdown')">Markdown</el-button>
        </template></el-table-column>
        <template #empty><EmptyState compact title="暂无审查报告" description="完成一次合同审查后，系统会在这里展示真实生成的报告。" /></template>
      </el-table>
    </section>
  </div>
</template>
