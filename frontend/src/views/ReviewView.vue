<script setup lang="ts">
import { computed, nextTick, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { UploadFilled } from '@element-plus/icons-vue'
import { api } from '../api'

interface TextLocation {
  定位状态: '精确定位' | '相关上下文' | '缺失条款'
  字符起点: number | null
  字符终点: number | null
  定位文本: string
}

const file = ref<File>()
const type = ref('general')
const loading = ref(false)
const result = ref<any>()
const activeRisk = ref<any>()
const highlightedClause = ref<HTMLElement>()

const activeLocation = computed<TextLocation | undefined>(() => activeRisk.value?.原文定位)
const locationStart = computed(() => activeLocation.value?.字符起点 ?? -1)
const locationEnd = computed(() => activeLocation.value?.字符终点 ?? -1)
const textBefore = computed(() => {
  if (locationStart.value < 0) return result.value?.contract_text || ''
  return result.value.contract_text.slice(0, locationStart.value)
})
const textHighlighted = computed(() => {
  if (locationStart.value < 0) return ''
  return result.value.contract_text.slice(locationStart.value, locationEnd.value)
})
const textAfter = computed(() => {
  if (locationStart.value < 0) return ''
  return result.value.contract_text.slice(locationEnd.value)
})

async function run() {
  if (!file.value) return ElMessage.warning('请选择合同文件')
  loading.value = true
  const form = new FormData()
  form.append('合同文件', file.value)
  form.append('合同类型', type.value)
  try {
    result.value = (await api.post('/reviews', form)).data
    activeRisk.value = result.value.risk_findings.find(
      (risk: any) => risk.原文定位?.字符起点 !== null,
    ) || result.value.risk_findings[0]
    ElMessage.success('审查完成')
    await focusRisk(activeRisk.value)
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || '审查失败')
  } finally {
    loading.value = false
  }
}

async function focusRisk(risk: any) {
  activeRisk.value = risk
  await nextTick()
  highlightedClause.value?.scrollIntoView({ behavior: 'smooth', block: 'center' })
}

function riskTagType(level: string) {
  if (level === '高' || level === '严重') return 'danger'
  if (level === '中') return 'warning'
  return 'success'
}

const onChange = (upload: any) => { file.value = upload.raw }
</script>

<template>
  <div class="page-head">
    <div><h1>智能审查工作台</h1><p>风险清单与合同原文双栏联动审查</p></div>
  </div>

  <section class="review-setup">
    <div class="upload-zone">
      <el-upload drag :auto-upload="false" :limit="1" accept=".pdf,.doc,.docx,.png,.jpg,.jpeg,.tif,.tiff,.bmp" :on-change="onChange">
        <el-icon class="upload-icon"><UploadFilled /></el-icon>
        <div>拖放合同文件到此处，或点击选择</div>
        <small>支持 PDF、Word、扫描图片，单文件不超过 50 MB</small>
      </el-upload>
    </div>
    <div class="review-options">
      <label>合同类型</label>
      <el-select v-model="type">
        <el-option label="通用合同" value="general" /><el-option label="采购合同" value="purchase" />
        <el-option label="销售合同" value="sales" /><el-option label="劳动合同" value="employment" />
        <el-option label="租赁合同" value="lease" /><el-option label="保密协议" value="nda" />
        <el-option label="服务合同" value="service" />
      </el-select>
      <p>Agent 协同：要素提取 · 合规校验 · 风险评分 · 条款优化</p>
      <el-button type="primary" size="large" :loading="loading" @click="run">开始审查</el-button>
    </div>
  </section>

  <section v-if="result" class="results">
    <div class="result-summary">
      <div><span>总体风险</span><strong>{{ result.final_report?.总体风险等级 }}</strong></div>
      <div><span>风险评分</span><strong>{{ result.final_report?.风险评分?.风险分 }}</strong></div>
      <div><span>风险点</span><strong>{{ result.risk_findings.length }}</strong></div>
      <router-link v-if="file?.type === 'application/pdf'" :to="`/reader/${result.review_id}`"><el-button>PDF 阅读器</el-button></router-link>
    </div>

    <div class="review-result-workbench">
      <aside class="risk-pane">
        <header><div><h2>风险点</h2><span>移入风险可定位原文</span></div><b>{{ result.risk_findings.length }}</b></header>
        <div class="risk-pane-list">
          <button
            v-for="risk in result.risk_findings"
            :key="risk.风险编号"
            :class="['linked-risk', { active: activeRisk?.风险编号 === risk.风险编号 }]"
            @mouseenter="focusRisk(risk)"
            @focus="focusRisk(risk)"
            @click="focusRisk(risk)"
          >
            <div class="linked-risk-title">
              <el-tag :type="riskTagType(risk.风险等级)" size="small">{{ risk.风险等级 }}</el-tag>
              <strong>{{ risk.短标题 || risk.风险类别 }}</strong>
              <small>{{ risk.风险编号 }}</small>
            </div>
            <p>{{ risk.风险标题 }}</p>
            <span>{{ risk.问题说明 }}</span>
            <div class="location-state" :class="risk.原文定位?.定位状态 === '缺失条款' ? 'missing' : ''">
              {{ risk.原文定位?.定位状态 === '缺失条款' ? '缺失条款，建议补充' : `${risk.原文定位?.定位状态} · 移入查看` }}
            </div>
            <div v-if="activeRisk?.风险编号 === risk.风险编号" class="active-risk-advice">
              <b>修改方向</b><span>{{ risk.修改方向 }}</span>
            </div>
          </button>
        </div>
      </aside>

      <article class="contract-pane">
        <header>
          <div><h2>合同全文</h2><span>{{ result.file_name }}</span></div>
          <el-tag v-if="activeLocation" :type="activeLocation.定位状态 === '缺失条款' ? 'info' : 'success'">{{ activeLocation.定位状态 }}</el-tag>
        </header>
        <div class="contract-document">
          <pre><span>{{ textBefore }}</span><mark v-if="textHighlighted" ref="highlightedClause">{{ textHighlighted }}</mark><span>{{ textAfter }}</span></pre>
        </div>
      </article>
    </div>
  </section>
</template>
