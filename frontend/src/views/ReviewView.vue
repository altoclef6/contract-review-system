<script setup lang="ts">
import { computed, nextTick, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Delete, Document, Refresh, UploadFilled } from '@element-plus/icons-vue'
import { api } from '../api'
import EmptyState from '../components/EmptyState.vue'
import MetricCard from '../components/MetricCard.vue'
import PageHeader from '../components/PageHeader.vue'
import RiskLevelTag from '../components/RiskLevelTag.vue'

interface TextLocation {
  定位状态: '精确定位' | '相关上下文' | '缺失条款'
  字符起点: number | null
  字符终点: number | null
  定位文本: string
}

const file = ref<File>()
const uploadRef = ref<any>()
const type = ref('auto')
const manualOverride = ref(false)
const loading = ref(false)
const result = ref<any>()
const activeRisk = ref<any>()
const highlightedClause = ref<HTMLElement>()
const elapsedSeconds = ref(0)
let elapsedTimer: number | undefined

const maxFileSize = 50 * 1024 * 1024
const allowedExtensions = new Set(['pdf', 'doc', 'docx', 'png', 'jpg', 'jpeg', 'tif', 'tiff', 'bmp'])
const contractTypeNames: Record<string, string> = {
  software_development: '软件开发合同', technical_service: '技术服务合同',
  information_system: '信息系统建设合同', software_outsourcing: '软件外包合同',
  procurement: '采购合同', sales: '销售合同', labor: '劳动合同', lease: '租赁合同',
  nda: '保密协议', service: '服务合同', other: '其他合同', general: '通用合同',
}

const formattedFileSize = computed(() => {
  if (!file.value) return ''
  const megabytes = file.value.size / 1024 / 1024
  return megabytes >= 1 ? `${megabytes.toFixed(2)} MB` : `${Math.max(1, Math.round(file.value.size / 1024))} KB`
})
const severeRiskCount = computed(() => result.value?.risk_findings?.filter(
  (risk: any) => risk.风险等级 === '高' || risk.风险等级 === '严重',
).length || 0)
const overallRiskClass = computed(() => {
  const level = result.value?.final_report?.总体风险等级
  if (level === '高' || level === '严重') return 'is-high'
  if (level === '中') return 'is-medium'
  return 'is-low'
})
const detectedTypeLabel = computed(() => contractTypeNames[result.value?.contract_type] || result.value?.contract_type || '待识别')
const classificationConfidence = computed(() => {
  const confidence = result.value?.classification?.confidence
  return typeof confidence === 'number' ? `${Math.round(confidence * 100)}%` : '暂无'
})
const overallRiskLabel = computed(() => {
  const level = String(result.value?.final_report?.总体风险等级 || '暂无')
  return level.endsWith('风险') ? level : `${level}风险`
})

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
  elapsedSeconds.value = 0
  const startedAt = performance.now()
  window.clearInterval(elapsedTimer)
  elapsedTimer = window.setInterval(() => {
    elapsedSeconds.value = Math.floor((performance.now() - startedAt) / 1000)
  }, 1000)
  const form = new FormData()
  form.append('合同文件', file.value)
  form.append('合同类型', manualOverride.value ? type.value : 'auto')
  try {
    result.value = (await api.post('/reviews', form, { timeout: 300000 })).data
    activeRisk.value = result.value.risk_findings.find(
      (risk: any) => risk.原文定位?.字符起点 !== null,
    ) || result.value.risk_findings[0]
    ElMessage.success(result.value.contract_center_saved ? '审查完成，合同已自动加入合同中心' : '审查完成')
    await focusRisk(activeRisk.value)
    await new Promise((resolve) => window.setTimeout(resolve, 420))
  } catch (error: any) {
    if (error.code === 'ECONNABORTED') {
      ElMessage.error('外部模型响应超时，请稍后重试；合同文件已成功上传')
    } else if (!error.response) {
      ElMessage.error('审查服务连接中断，请确认后端服务正在运行')
    } else {
      ElMessage.error(error.response?.data?.detail || error.response?.data?.message || '审查失败')
    }
  } finally {
    window.clearInterval(elapsedTimer)
    loading.value = false
  }
}

async function focusRisk(risk: any) {
  activeRisk.value = risk
  await nextTick()
  highlightedClause.value?.scrollIntoView({ behavior: 'smooth', block: 'center' })
}

const onChange = (upload: any) => {
  const selected = upload.raw as File | undefined
  if (!selected) return
  const extension = selected.name.split('.').pop()?.toLowerCase() || ''
  if (!allowedExtensions.has(extension)) {
    ElMessage.error('不支持该文件类型，请上传 PDF、Word 或常见扫描图片')
    removeFile()
    return
  }
  if (selected.size <= 0) {
    ElMessage.error('文件内容为空，请重新选择')
    removeFile()
    return
  }
  if (selected.size > maxFileSize) {
    ElMessage.error('文件超过 50 MB，请压缩或拆分后再上传')
    removeFile()
    return
  }
  file.value = selected
  result.value = undefined
  activeRisk.value = undefined
}

function triggerUpload() {
  uploadRef.value?.clearFiles()
  window.requestAnimationFrame(() => {
    uploadRef.value?.$el?.querySelector('input[type="file"]')?.click()
  })
}

function removeFile() {
  uploadRef.value?.clearFiles()
  file.value = undefined
}
</script>

<template>
  <div class="review-page">
    <PageHeader title="智能审查工作台" description="上传合同后执行文档解析、确定性规则与 AI 辅助审查，并定位风险原文。" eyebrow="合同风险审查" />

    <main class="review-content">
      <section class="review-setup" aria-label="合同上传与审查配置">
        <div class="setup-card upload-card">
          <div class="module-heading">
            <div><h2>上传合同</h2><p>上传待审查的合同原始文件</p></div>
          </div>
          <el-upload
            ref="uploadRef"
            class="contract-uploader"
            drag
            :auto-upload="false"
            :limit="1"
            :show-file-list="false"
            accept=".pdf,.doc,.docx,.png,.jpg,.jpeg,.tif,.tiff,.bmp"
            :on-change="onChange"
          >
            <div v-if="!file" class="upload-placeholder">
              <span class="upload-icon-wrap"><el-icon><UploadFilled /></el-icon></span>
              <div><strong>拖放合同文件到此处，或点击选择</strong><small>支持 PDF、Word、扫描图片，单文件不超过 50 MB</small></div>
            </div>
            <div v-else class="selected-file" @click.stop>
              <span class="file-icon"><el-icon><Document /></el-icon></span>
              <div class="file-meta"><strong :title="file.name">{{ file.name }}</strong><span>{{ formattedFileSize }} · 等待开始审查</span></div>
              <span class="upload-success"><i></i>文件已就绪</span>
              <div class="file-actions">
                <el-button text :icon="Refresh" @click.stop="triggerUpload">重新上传</el-button>
                <el-button text class="delete-file" :icon="Delete" @click.stop="removeFile">删除</el-button>
              </div>
            </div>
          </el-upload>
        </div>

        <div class="setup-card review-options">
          <div class="module-heading"><div><h2>智能分类与归档</h2><p>默认读取合同正文自动识别，无需手动选择</p></div></div>
          <div class="auto-classification">
            <strong>自动识别合同类型</strong>
            <span>分类 Agent 将给出类型、置信度和识别依据；低置信度结果可在合同中心修正。</span>
          </div>
          <div class="override-row"><span>需要人工指定类型</span><el-switch v-model="manualOverride" /></div>
          <template v-if="manualOverride">
            <label for="contract-type">人工指定类型</label>
            <el-select id="contract-type" v-model="type">
              <el-option v-for="(label, value) in contractTypeNames" :key="value" :label="label" :value="value" />
            </el-select>
          </template>
          <div class="capability-tags" aria-label="审查能力">
            <span>自动分类</span><span>要素提取</span><span>合规校验</span><span>风险评分</span><span>自动归档</span>
          </div>
          <el-button class="start-review" type="primary" :loading="loading" :disabled="loading" @click="run">开始审查</el-button>
          <p class="duration-hint">审查成功后自动加入合同中心并生成报告、风险台账</p>
        </div>
      </section>

      <section class="result-area" aria-label="审查结果">
        <el-alert
          v-if="result?.errors?.length"
          type="warning"
          show-icon
          :closable="false"
          :title="result.errors.join('；')"
          class="result-warning"
        />
        <div v-if="result" class="classification-summary">
          <div><span>识别类型</span><strong>{{ detectedTypeLabel }}</strong></div>
          <div><span>分类置信度</span><strong>{{ classificationConfidence }}</strong></div>
          <div><span>分类方式</span><strong>{{ result.classification?.method === 'llm' ? 'AI 模型' : '内容规则' }}</strong></div>
          <div><span>合同中心</span><router-link v-if="result.contract_id" :to="`/contracts/${result.contract_id}`">查看已归档合同</router-link><strong v-else>未关联</strong></div>
          <p v-if="result.classification?.evidence?.length">识别依据：{{ result.classification.evidence.join('、') }}</p>
        </div>
        <div v-if="result" class="result-summary">
          <MetricCard label="综合风险" :value="overallRiskLabel" :tone="overallRiskClass === 'is-high' ? 'high' : overallRiskClass === 'is-medium' ? 'medium' : 'low'" />
          <MetricCard label="风险评分" :value="result.final_report?.风险评分?.风险分" unit="/ 100" tone="medium" />
          <MetricCard label="风险点" :value="result.risk_findings.length" unit="项" />
          <MetricCard label="严重风险" :value="severeRiskCount" unit="项" tone="high" />
        </div>

        <EmptyState v-if="!result" title="尚未生成审查结果" description="上传合同并开始审查后，系统将在此展示风险条款、风险说明和修改建议。" />

        <section v-else class="results">
          <div class="result-toolbar">
            <div><h2>审查结果</h2><p>选择风险项可在合同全文中定位相关原文</p></div>
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
              <RiskLevelTag :level="risk.风险等级" />
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
      </section>
    </main>
  </div>

  <Teleport to="body">
    <Transition name="ritual-fade">
      <section v-if="loading" class="review-ritual" aria-live="polite" aria-busy="true">
        <div class="ritual-content">
          <span class="ritual-brand"><el-icon><Document /></el-icon></span>
          <span class="ritual-code">CONTRACT REVIEW</span>
          <h2>合同审查进行中</h2>
          <p>后端正在执行文档解析、规则检查和审查流程</p>
          <div class="ritual-progress"><span></span></div>
          <div class="ritual-timing"><strong>处理中</strong><span>已等待 {{ elapsedSeconds }} 秒，请勿关闭当前页面</span></div>
          <small>此处仅显示请求活动状态，不代表具体后端阶段进度。</small>
        </div>
      </section>
    </Transition>
  </Teleport>
</template>

<style scoped>
.review-page {
  --review-primary: #2563eb;
  --review-primary-hover: #1d4ed8;
  --review-text: #172033;
  --review-muted: #64748b;
  --review-border: #e5eaf2;
  --review-bg: #f5f7fb;
  --review-danger: #dc2626;
  --review-warning: #f59e0b;
  --review-success: #16a34a;
  --review-radius: 12px;
  --review-shadow: 0 4px 16px rgba(23, 32, 51, 0.05);
  max-width: 1440px;
  min-width: 0;
  min-height: calc(100vh - 150px);
  margin: 0 auto;
  color: var(--review-text);
  background: transparent;
  box-shadow: none;
  font-family: Inter, "PingFang SC", "Microsoft YaHei", sans-serif;
}

.review-page-head {
  min-height: 76px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 24px;
  padding: 0 4px;
  border-bottom: 1px solid var(--review-border);
}

.review-page-head h1,
.module-heading h2,
.result-toolbar h2,
.empty-result h2 { margin: 0; color: var(--review-text); }
.review-page-head h1 { font-size: 26px; line-height: 34px; font-weight: 700; letter-spacing: -0.02em; }
.review-page-head p { margin: 4px 0 0; color: var(--review-muted); font-size: 13px; line-height: 20px; }

.ai-service-status {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 190px;
  padding: 8px 12px;
  border: 1px solid var(--review-border);
  border-radius: 10px;
  background: #fff;
}
.ai-status-icon { display: grid; place-items: center; width: 34px; height: 34px; border-radius: 50%; color: var(--review-primary); background: #eff6ff; font-size: 18px; }
.ai-service-status > span:nth-child(2) { display: flex; flex: 1; flex-direction: column; }
.ai-service-status b { color: var(--review-text); font-size: 13px; line-height: 18px; }
.ai-service-status small { color: var(--review-muted); font-size: 11px; line-height: 16px; }
.ai-service-status > i { width: 8px; height: 8px; border-radius: 50%; background: var(--review-success); box-shadow: 0 0 0 3px #dcfce7; }

.review-content { padding: 24px 0 32px; }
.review-setup { display: grid; grid-template-columns: minmax(0, 1fr) 320px; gap: 24px; align-items: stretch; }
.setup-card,
.result-summary,
.empty-result,
.results { background: #fff; border: 1px solid var(--review-border); border-radius: var(--review-radius); box-shadow: var(--review-shadow); }
.setup-card { min-width: 0; padding: 24px; }
.module-heading { display: flex; align-items: flex-start; justify-content: space-between; margin-bottom: 16px; }
.module-heading h2,
.result-toolbar h2 { font-size: 18px; line-height: 26px; font-weight: 700; }
.module-heading p,
.result-toolbar p { margin: 2px 0 0; color: var(--review-muted); font-size: 12px; line-height: 18px; }

.contract-uploader { display: block; min-width: 0; }
.contract-uploader :deep(.el-upload) { display: block; width: 100%; }
.contract-uploader :deep(.el-upload-dragger) {
  width: 100%; height: 150px; padding: 0; overflow: hidden;
  display: flex; align-items: center; justify-content: center;
  border: 1px dashed #bfdbfe; border-radius: 10px; background: #f8fbff;
  transition: border-color 0.2s ease, background 0.2s ease, box-shadow 0.2s ease;
}
.contract-uploader :deep(.el-upload-dragger:hover),
.contract-uploader :deep(.el-upload-dragger.is-dragover) { border-color: var(--review-primary); background: #eff6ff; box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.08); }
.upload-placeholder { display: flex; align-items: center; justify-content: center; gap: 16px; padding: 24px; text-align: left; }
.upload-icon-wrap { display: grid; flex: 0 0 auto; place-items: center; width: 52px; height: 52px; border-radius: 50%; color: var(--review-primary); background: #dbeafe; font-size: 25px; }
.upload-placeholder > div { display: flex; flex-direction: column; gap: 6px; }
.upload-placeholder strong { color: var(--review-text); font-size: 14px; line-height: 22px; }
.upload-placeholder small { color: var(--review-muted); font-size: 12px; line-height: 18px; }

.selected-file { width: 100%; min-width: 0; display: flex; align-items: center; gap: 14px; padding: 24px; text-align: left; cursor: default; }
.file-icon { display: grid; flex: 0 0 auto; place-items: center; width: 48px; height: 48px; border-radius: 10px; color: var(--review-primary); background: #eff6ff; font-size: 24px; }
.file-meta { min-width: 0; flex: 1; display: flex; flex-direction: column; gap: 5px; }
.file-meta strong { overflow: hidden; color: var(--review-text); font-size: 14px; line-height: 20px; text-overflow: ellipsis; white-space: nowrap; }
.file-meta span { color: var(--review-muted); font-size: 12px; line-height: 18px; }
.upload-success { display: inline-flex; align-items: center; gap: 6px; color: var(--review-success); font-size: 12px; white-space: nowrap; }
.upload-success i { width: 7px; height: 7px; border-radius: 50%; background: currentColor; }
.file-actions { display: flex; align-items: center; gap: 4px; }
.file-actions :deep(.el-button) { margin: 0; color: var(--review-primary); }
.file-actions :deep(.delete-file) { color: var(--review-danger); }

.review-options { display: flex; flex-direction: column; }
.review-options label { margin-bottom: 8px; color: var(--review-text); font-size: 13px; line-height: 20px; font-weight: 600; }
.review-options :deep(.el-select) { width: 100%; }
.review-options :deep(.el-select__wrapper) { min-height: 44px; border-radius: 8px; box-shadow: 0 0 0 1px var(--review-border) inset; }
.review-options :deep(.el-select__wrapper.is-focused) { box-shadow: 0 0 0 1px var(--review-primary) inset; }
.auto-classification { display: grid; gap: 5px; padding: 13px 14px; border: 1px solid #bfdbfe; border-radius: 9px; background: #eff6ff; }
.auto-classification strong { color: #1e40af; font-size: 13px; }
.auto-classification span { color: #475569; font-size: 12px; line-height: 18px; }
.override-row { display: flex; align-items: center; justify-content: space-between; gap: 12px; margin: 14px 0 10px; color: var(--review-muted); font-size: 12px; }
.capability-tags { display: flex; flex-wrap: wrap; gap: 8px; margin: 16px 0 20px; }
.capability-tags span { padding: 5px 9px; border: 1px solid #dbeafe; border-radius: 6px; color: #1e40af; background: #eff6ff; font-size: 12px; line-height: 18px; }
.start-review { width: 100%; height: 46px; margin-top: auto; border: 0; border-radius: 8px; background: var(--review-primary); font-size: 14px; font-weight: 600; box-shadow: none; }
.start-review:hover,
.start-review:focus { background: var(--review-primary-hover); }
.start-review:active { transform: translateY(1px); background: #1e40af; }
.start-review.is-disabled { background: #93b4f3; }
.duration-hint { margin: 8px 0 0; color: var(--review-muted); font-size: 12px; line-height: 18px; text-align: center; }

.result-area { margin-top: 24px; }
.result-warning { margin-bottom: 16px; }
.classification-summary { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; margin-bottom: 16px; padding: 16px 18px; border: 1px solid #dbeafe; border-radius: var(--review-radius); background: #f8fbff; }
.classification-summary > div { display: grid; gap: 4px; }
.classification-summary span { color: var(--review-muted); font-size: 12px; }
.classification-summary strong,.classification-summary a { color: var(--review-text); font-size: 14px; font-weight: 600; }
.classification-summary a { color: var(--review-primary); }
.classification-summary p { grid-column: 1 / -1; margin: 2px 0 0; color: var(--review-muted); font-size: 12px; }
.result-summary { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 16px; padding: 16px; }
.metric-card { position: relative; min-width: 0; padding: 18px 20px; overflow: hidden; border: 1px solid var(--review-border); border-radius: 10px; background: #fafcff; }
.metric-card::before { content: ""; position: absolute; inset: 0 auto 0 0; width: 3px; background: var(--review-primary); }
.metric-card > span { display: block; margin-bottom: 8px; color: var(--review-muted); font-size: 12px; line-height: 18px; }
.metric-card strong { display: flex; align-items: baseline; gap: 4px; color: var(--review-text); font-size: 28px; line-height: 34px; font-weight: 700; }
.metric-card strong small { color: var(--review-muted); font-size: 14px; line-height: 20px; font-weight: 500; }
.severe-card::before { background: var(--review-danger); }
.risk-level-card strong { font-size: 18px; }
.risk-level-card strong em { padding: 4px 9px; border-radius: 6px; font-size: 16px; line-height: 24px; font-style: normal; }
.risk-level-card.is-high::before { background: var(--review-danger); }
.risk-level-card.is-high strong em { color: var(--review-danger); background: #fef2f2; }
.risk-level-card.is-medium::before { background: var(--review-warning); }
.risk-level-card.is-medium strong em { color: #b45309; background: #fffbeb; }
.risk-level-card.is-low::before { background: var(--review-success); }
.risk-level-card.is-low strong em { color: var(--review-success); background: #f0fdf4; }
.score-card::before { background: var(--review-warning); }

.empty-result { min-height: 280px; display: flex; flex-direction: column; align-items: center; justify-content: center; margin-top: 16px; padding: 40px 24px; text-align: center; }
.empty-result-icon { display: grid; place-items: center; width: 56px; height: 56px; margin-bottom: 16px; border-radius: 50%; color: var(--review-primary); background: #eff6ff; font-size: 25px; }
.empty-result h2 { font-size: 18px; line-height: 26px; font-weight: 700; }
.empty-result p { max-width: 520px; margin: 8px 0 0; color: var(--review-muted); font-size: 14px; line-height: 22px; }

.results { margin-top: 16px; overflow: hidden; }
.result-toolbar { display: flex; align-items: center; justify-content: space-between; gap: 16px; padding: 20px 24px; border-bottom: 1px solid var(--review-border); }
.result-toolbar :deep(.el-button) { height: 38px; border-color: var(--review-border); border-radius: 8px; color: var(--review-primary); }
.review-result-workbench { height: min(680px, calc(100vh - 160px)); min-height: 560px; display: grid; grid-template-columns: minmax(320px, 38%) minmax(0, 1fr); margin-top: 0; overflow: hidden; }
.risk-pane { min-width: 0; border-right: 1px solid var(--review-border); background: #fbfcfe; }
.risk-pane > header,
.contract-pane > header { min-height: 66px; display: flex; align-items: center; justify-content: space-between; gap: 16px; padding: 14px 20px; border-bottom: 1px solid var(--review-border); background: #fff; }
.risk-pane header h2,
.contract-pane header h2 { margin: 0; color: var(--review-text); font-size: 16px; line-height: 24px; }
.risk-pane header span,
.contract-pane header span { display: block; margin-top: 2px; overflow: hidden; color: var(--review-muted); font-size: 12px; line-height: 18px; text-overflow: ellipsis; white-space: nowrap; }
.risk-pane header b { display: grid; place-items: center; min-width: 30px; height: 30px; padding: 0 8px; border-radius: 15px; color: var(--review-primary); background: #eff6ff; font-size: 13px; }
.risk-pane-list { max-height: 640px; padding: 12px; overflow-y: auto; }
.linked-risk { width: 100%; margin: 0 0 10px; padding: 16px; border: 1px solid var(--review-border); border-radius: 10px; color: var(--review-text); background: #fff; text-align: left; cursor: pointer; transition: border-color 0.2s ease, box-shadow 0.2s ease, background 0.2s ease; }
.linked-risk:hover,
.linked-risk:focus-visible,
.linked-risk.active { outline: 0; border-color: #93c5fd; background: #f8fbff; box-shadow: 0 2px 10px rgba(37, 99, 235, 0.08); }
.linked-risk-title { display: flex; align-items: center; gap: 8px; }
.linked-risk-title strong { min-width: 0; flex: 1; overflow: hidden; font-size: 14px; text-overflow: ellipsis; white-space: nowrap; }
.linked-risk-title small { color: var(--review-muted); font-size: 11px; }
.linked-risk > p { margin: 10px 0 5px; color: var(--review-text); font-size: 14px; line-height: 21px; font-weight: 600; }
.linked-risk > span { display: -webkit-box; overflow: hidden; color: var(--review-muted); font-size: 12px; line-height: 19px; -webkit-box-orient: vertical; -webkit-line-clamp: 2; }
.location-state { margin-top: 10px; color: var(--review-primary); font-size: 12px; line-height: 18px; }
.location-state.missing { color: var(--review-warning); }
.active-risk-advice { display: grid; gap: 4px; margin-top: 12px; padding: 10px 12px; border-left: 3px solid var(--review-primary); border-radius: 0 6px 6px 0; background: #eff6ff; }
.active-risk-advice b { color: var(--review-text); font-size: 12px; }
.active-risk-advice span { color: var(--review-muted); font-size: 12px; line-height: 19px; }
.contract-pane { min-width: 0; background: #fff; }
.contract-pane > header > div { min-width: 0; }
.contract-document { max-height: 640px; padding: 24px; overflow: auto; background: #f8fafc; }
.contract-document pre { min-height: 520px; margin: 0; padding: 28px 32px; border: 1px solid var(--review-border); border-radius: 8px; color: var(--review-text); background: #fff; font-family: "PingFang SC", "Microsoft YaHei", sans-serif; font-size: 14px; line-height: 2; white-space: pre-wrap; word-break: break-word; box-shadow: 0 2px 8px rgba(23, 32, 51, 0.04); }
.contract-document mark { padding: 2px 0; color: inherit; background: #fef3c7; box-shadow: 0 0 0 2px #fef3c7; }

.review-ritual {
  --review-primary: #2563eb;
  --review-text: #172033;
  --review-muted: #64748b;
  --review-border: #e5eaf2;
  --review-radius: 12px;
  position: fixed; z-index: 3000; inset: 0; display: grid; place-items: center; padding: 32px; overflow: hidden; background: #f5f7fb !important;
}
.ritual-content {
  position: relative !important;
  z-index: 1;
  inset: auto !important;
  left: auto !important;
  top: auto !important;
  width: min(760px, 100%);
  padding: 0;
  transform: none !important;
  border: 0;
  color: var(--review-text);
  background: transparent;
  box-shadow: none;
  text-align: center;
}
.ritual-code { display: inline-flex; align-items: center; gap: 10px; color: var(--review-primary); font: 700 11px/18px Inter, sans-serif; letter-spacing: 0.18em; }
.ritual-code::before,
.ritual-code::after { content: ""; width: 34px; height: 1px; background: #93c5fd; }
.ritual-content h2 { margin: 22px 0 8px; color: var(--review-text); font-size: clamp(28px, 4vw, 42px); line-height: 1.25; font-weight: 600; letter-spacing: 0.22em; }
.ritual-content > p { margin: 0; color: var(--review-muted); font-size: 14px; line-height: 22px; letter-spacing: 0.16em; }
.ritual-timing { display: flex; align-items: center; flex-direction: column; justify-content: center; gap: 8px; margin: 34px auto 28px; padding: 0; background: transparent; text-align: center; }
.ritual-timing strong { display: grid; place-items: center; min-width: 104px; height: 38px; padding: 0 18px; border: 1px solid #bfdbfe; border-radius: 19px; color: var(--review-primary); background: #eff6ff; font-size: 14px; font-weight: 700; letter-spacing: 0.12em; }
.ritual-timing span { color: var(--review-muted); font-size: 12px; line-height: 20px; text-align: center; }
.ritual-agents { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 0; border-top: 1px solid var(--review-border); border-bottom: 1px solid var(--review-border); }
.ritual-agents > div { min-width: 0; display: flex; align-items: center; justify-content: center; gap: 8px; padding: 16px 10px; color: #94a3b8; background: transparent; font-size: 12px; }
.ritual-agents > div + div { border-left: 1px solid var(--review-border); }
.ritual-agents > div.active { color: var(--review-text); background: rgba(219, 234, 254, 0.52); }
.ritual-agents i { display: grid; flex: 0 0 auto; place-items: center; width: 24px; height: 24px; border-radius: 50%; color: #94a3b8; background: #eef2f7; font-size: 9px; font-style: normal; }
.ritual-agents > div.active i { color: #fff; background: var(--review-primary); }
.ritual-progress { position: relative; height: 3px; margin-top: 28px; overflow: hidden; background: #dbe3ef; }
.ritual-progress::before,
.ritual-progress::after { content: ""; position: absolute; top: -3px; width: 1px; height: 9px; background: #94a3b8; }
.ritual-progress::before { left: 0; }
.ritual-progress::after { right: 0; }
.ritual-progress span { position: absolute; top: 0; left: 0; display: block; width: 32%; height: 100%; background: var(--review-primary); animation: review-loading-scan 1.45s cubic-bezier(0.4, 0, 0.2, 1) infinite; }
.ritual-progress.complete span { width: 100%; animation: none; }
.ritual-fade-enter-active,
.ritual-fade-leave-active { transition: opacity 0.2s ease; }
.ritual-fade-enter-from,
.ritual-fade-leave-to { opacity: 0; }

@keyframes review-loading-scan {
  from { transform: translateX(-105%); }
  to { transform: translateX(315%); }
}

@media (prefers-reduced-motion: reduce) {
  .ritual-progress span { animation: none; }
  .ritual-progress span { left: 34%; }
  .ritual-progress.complete span { left: 0; }
}

@media (max-width: 1024px) {
  .review-setup { grid-template-columns: minmax(0, 1fr) 300px; gap: 20px; }
  .result-summary { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .classification-summary { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .review-result-workbench { grid-template-columns: minmax(280px, 42%) minmax(0, 1fr); }
}

@media (max-width: 820px) {
  .review-page-head { min-height: auto; padding: 12px 0 16px; }
  .ai-service-status { min-width: auto; }
  .ai-service-status small { display: none; }
  .review-setup { grid-template-columns: 1fr; }
  .review-result-workbench { height: auto; min-height: 0; grid-template-columns: 1fr; }
  .risk-pane { border-right: 0; border-bottom: 1px solid var(--review-border); }
  .risk-pane-list { max-height: 420px; }
}

@media (max-width: 600px) {
  .review-page-head { align-items: flex-start; }
  .review-page-head h1 { font-size: 22px; line-height: 30px; }
  .ai-service-status { padding: 7px; }
  .ai-service-status > span:nth-child(2) { display: none; }
  .setup-card { padding: 16px; }
  .upload-placeholder { flex-direction: column; text-align: center; }
  .selected-file { flex-wrap: wrap; padding: 16px; }
  .file-meta { flex-basis: calc(100% - 66px); }
  .upload-success { margin-left: 62px; }
  .file-actions { margin-left: auto; }
  .result-summary { grid-template-columns: 1fr; }
  .classification-summary { grid-template-columns: 1fr; }
  .result-toolbar { align-items: flex-start; padding: 16px; }
  .contract-document { padding: 12px; }
  .contract-document pre { padding: 20px; }
  .ritual-content { padding: 20px; }
  .ritual-content h2 { letter-spacing: 0.12em; }
  .ritual-agents { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .ritual-agents > div:nth-child(3) { border-left: 0; border-top: 1px solid var(--review-border); }
  .ritual-agents > div:nth-child(4) { border-top: 1px solid var(--review-border); }
}
</style>

<style scoped>
.review-page {
  max-width: none;
  min-height: calc(100vh - 160px);
  background: transparent;
  box-shadow: none;
  clip-path: none;
}

.review-content { padding: 0 0 24px; }

.result-summary {
  gap: 16px;
  padding: 0;
  border: 0;
  background: transparent;
  box-shadow: none;
}

.review-ritual { background: rgba(245, 247, 251, 0.96) !important; }

.ritual-content {
  width: min(560px, 100%);
  padding: 36px 40px;
  border: 1px solid var(--review-border);
  border-radius: 16px;
  background: #fff;
  box-shadow: 0 18px 50px rgba(23, 32, 51, 0.12);
}

.ritual-brand {
  width: 52px;
  height: 52px;
  display: grid;
  place-items: center;
  margin: 0 auto 16px;
  border-radius: 14px;
  color: #fff;
  background: var(--review-primary);
  font-size: 24px;
}

.ritual-code::before,
.ritual-code::after { display: none; }

.ritual-content h2 {
  margin: 12px 0 8px;
  font-size: 28px;
  letter-spacing: 0.04em;
}

.ritual-content > p { letter-spacing: 0; }

.ritual-progress {
  width: 100%;
  height: 4px;
  margin: 28px 0 18px;
  border-radius: 2px;
}

.ritual-timing {
  flex-direction: row;
  gap: 12px;
  margin: 0;
}

.ritual-timing strong {
  min-width: 72px;
  height: 30px;
  padding: 0 12px;
  border-radius: 15px;
  letter-spacing: 0;
}

.ritual-content > small {
  display: block;
  margin-top: 18px;
  color: var(--review-muted);
  font-size: 11px;
}

@media (max-width: 600px) {
  .ritual-content { padding: 28px 20px; }
  .ritual-timing { align-items: center; flex-direction: column; }
}
</style>
