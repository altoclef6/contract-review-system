<script setup lang="ts">
import { computed, nextTick, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Cpu, Delete, Document, Refresh, UploadFilled } from '@element-plus/icons-vue'
import { api } from '../api'

interface TextLocation {
  定位状态: '精确定位' | '相关上下文' | '缺失条款'
  字符起点: number | null
  字符终点: number | null
  定位文本: string
}

const file = ref<File>()
const uploadRef = ref<any>()
const type = ref('general')
const loading = ref(false)
const result = ref<any>()
const activeRisk = ref<any>()
const highlightedClause = ref<HTMLElement>()
const reviewStage = ref(0)
const reviewProgress = ref(0)
const elapsedSeconds = ref(0)
let elapsedTimer: number | undefined
const reviewStages = ['协调者接收合同', '提取者解析全文', '合规 Agent 检索风险', '修订 Agent 生成建议']
const progressHint = computed(() => {
  if (reviewProgress.value >= 100) return '审查结果已生成'
  return '后端正在执行文档解析、规则检查和审查流程'
})

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
  reviewStage.value = 0
  reviewProgress.value = 0
  elapsedSeconds.value = 0
  const startedAt = performance.now()
  window.clearInterval(elapsedTimer)
  elapsedTimer = window.setInterval(() => {
    elapsedSeconds.value = Math.floor((performance.now() - startedAt) / 1000)
  }, 1000)
  const form = new FormData()
  form.append('合同文件', file.value)
  form.append('合同类型', type.value)
  try {
    result.value = (await api.post('/reviews', form, { timeout: 300000 })).data
    reviewProgress.value = 100
    reviewStage.value = reviewStages.length - 1
    activeRisk.value = result.value.risk_findings.find(
      (risk: any) => risk.原文定位?.字符起点 !== null,
    ) || result.value.risk_findings[0]
    ElMessage.success('审查完成')
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

function riskTagType(level: string) {
  if (level === '高' || level === '严重') return 'danger'
  if (level === '中') return 'warning'
  return 'success'
}

const onChange = (upload: any) => { file.value = upload.raw }

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
    <header class="review-page-head">
      <div>
        <h1>智能审查工作台</h1>
        <p>风险清单与合同原文双栏联动审查</p>
      </div>
      <div class="ai-service-status" aria-label="AI 服务状态正常">
        <span class="ai-status-icon"><el-icon><Cpu /></el-icon></span>
        <span><b>AI服务正常</b><small>审查能力已就绪</small></span>
        <i></i>
      </div>
    </header>

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
          <div class="module-heading"><div><h2>审查配置</h2><p>选择合同类型与审查能力</p></div></div>
          <label for="contract-type">合同类型</label>
          <el-select id="contract-type" v-model="type">
            <el-option label="通用合同" value="general" /><el-option label="采购合同" value="purchase" />
            <el-option label="销售合同" value="sales" /><el-option label="劳动合同" value="employment" />
            <el-option label="租赁合同" value="lease" /><el-option label="保密协议" value="nda" />
            <el-option label="服务合同" value="service" />
          </el-select>
          <div class="capability-tags" aria-label="审查能力">
            <span>要素提取</span><span>合规校验</span><span>风险评分</span><span>条款优化</span>
          </div>
          <el-button class="start-review" type="primary" :loading="loading" :disabled="loading" @click="run">开始审查</el-button>
          <p class="duration-hint">预计耗时 20～40 秒</p>
        </div>
      </section>

      <section class="result-area" aria-label="审查结果">
        <div v-if="result" class="result-summary">
          <div :class="['metric-card', 'risk-level-card', overallRiskClass]">
            <span>综合风险</span>
            <strong><em>{{ result.final_report?.总体风险等级 }}</em>风险</strong>
          </div>
          <div class="metric-card score-card"><span>风险评分</span><strong>{{ result.final_report?.风险评分?.风险分 }} <small>/ 100</small></strong></div>
          <div class="metric-card count-card"><span>风险点</span><strong>{{ result.risk_findings.length }}<small>项</small></strong></div>
          <div class="metric-card severe-card"><span>严重风险</span><strong>{{ severeRiskCount }}<small>项</small></strong></div>
        </div>

        <div v-if="!result" class="empty-result">
          <span class="empty-result-icon"><el-icon><Document /></el-icon></span>
          <h2>尚未生成审查结果</h2>
          <p>上传合同并开始审查后，系统将在此展示风险条款、风险说明和修改建议。</p>
        </div>

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
      </section>
    </main>
  </div>

  <Teleport to="body">
    <Transition name="ritual-fade">
      <section v-if="loading" class="review-ritual" aria-live="polite">
        <div class="ritual-scene"></div><div class="ritual-shade"></div>
        <div class="ritual-content">
          <span class="ritual-code">CONTRACT / ANALYSIS</span>
          <h2>合同审查进行中</h2>
          <p>{{ reviewStages[reviewStage] }}</p>
          <div class="ritual-timing"><strong>{{ reviewProgress >= 100 ? '100%' : '处理中' }}</strong><span>已等待 {{ elapsedSeconds }} 秒 · {{ progressHint }}</span></div>
          <div class="ritual-agents">
            <div v-for="(stage, index) in reviewStages" :key="stage" :class="{ active: index <= reviewStage }">
              <i>{{ String(index + 1).padStart(2, '0') }}</i><span>{{ stage }}</span>
            </div>
          </div>
          <div class="ritual-progress"><span :style="{ width: `${reviewProgress}%` }"></span></div>
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
  background: var(--review-bg);
  box-shadow: 0 0 0 100vmax var(--review-bg);
  clip-path: inset(0 -100vmax);
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
.capability-tags { display: flex; flex-wrap: wrap; gap: 8px; margin: 16px 0 20px; }
.capability-tags span { padding: 5px 9px; border: 1px solid #dbeafe; border-radius: 6px; color: #1e40af; background: #eff6ff; font-size: 12px; line-height: 18px; }
.start-review { width: 100%; height: 46px; margin-top: auto; border: 0; border-radius: 8px; background: var(--review-primary); font-size: 14px; font-weight: 600; box-shadow: none; }
.start-review:hover,
.start-review:focus { background: var(--review-primary-hover); }
.start-review:active { transform: translateY(1px); background: #1e40af; }
.start-review.is-disabled { background: #93b4f3; }
.duration-hint { margin: 8px 0 0; color: var(--review-muted); font-size: 12px; line-height: 18px; text-align: center; }

.result-area { margin-top: 24px; }
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
  position: fixed; z-index: 3000; inset: 0; display: grid; place-items: center; padding: 24px; background: rgba(23, 32, 51, 0.46);
}
.ritual-scene { position: absolute; inset: 0; display: block; overflow: hidden; pointer-events: none; }
.ritual-scene::before,
.ritual-scene::after {
  content: "";
  position: absolute;
  inset: -18%;
  opacity: 0.48;
  background-image:
    radial-gradient(circle, rgba(147, 197, 253, 0.9) 0 1px, transparent 1.6px),
    radial-gradient(circle, rgba(37, 99, 235, 0.72) 0 1.4px, transparent 2px);
  background-position: 20px 28px, 84px 96px;
  background-size: 132px 132px, 196px 196px;
  animation: review-particles-drift 18s linear infinite;
}
.ritual-scene::after { opacity: 0.28; transform: scale(1.08); animation-duration: 26s; animation-direction: reverse; }
.ritual-shade { display: none; }
.ritual-content { position: relative; z-index: 1; width: min(520px, 100%); padding: 28px; border: 1px solid var(--review-border); border-radius: var(--review-radius); color: var(--review-text); background: #fff; box-shadow: 0 20px 50px rgba(23, 32, 51, 0.18); }
.ritual-code { color: var(--review-primary); font-size: 11px; line-height: 18px; font-weight: 700; letter-spacing: 0.08em; }
.ritual-content h2 { margin: 8px 0 4px; font-size: 22px; line-height: 30px; }
.ritual-content > p { margin: 0; color: var(--review-muted); font-size: 14px; line-height: 22px; }
.ritual-timing { display: flex; align-items: center; justify-content: space-between; gap: 16px; margin: 20px 0 16px; padding: 12px; border-radius: 8px; background: #f5f7fb; }
.ritual-timing strong { color: var(--review-primary); font-size: 14px; }
.ritual-timing span { color: var(--review-muted); font-size: 12px; text-align: right; }
.ritual-agents { display: grid; gap: 8px; }
.ritual-agents > div { display: flex; align-items: center; gap: 10px; color: #94a3b8; font-size: 12px; }
.ritual-agents > div.active { color: var(--review-text); }
.ritual-agents i { display: grid; place-items: center; width: 26px; height: 26px; border-radius: 50%; background: #eef2f7; font-size: 10px; font-style: normal; }
.ritual-agents > div.active i { color: #fff; background: var(--review-primary); }
.ritual-progress { height: 4px; margin-top: 20px; overflow: hidden; border-radius: 2px; background: #e2e8f0; }
.ritual-progress span { display: block; height: 100%; border-radius: inherit; background: var(--review-primary); transition: width 0.3s ease; }
.ritual-fade-enter-active,
.ritual-fade-leave-active { transition: opacity 0.2s ease; }
.ritual-fade-enter-from,
.ritual-fade-leave-to { opacity: 0; }

@keyframes review-particles-drift {
  from { translate: 0 0; }
  to { translate: 46px -54px; }
}

@media (prefers-reduced-motion: reduce) {
  .ritual-scene::before,
  .ritual-scene::after { animation: none; }
}

@media (max-width: 1024px) {
  .review-setup { grid-template-columns: minmax(0, 1fr) 300px; gap: 20px; }
  .result-summary { grid-template-columns: repeat(2, minmax(0, 1fr)); }
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
  .result-toolbar { align-items: flex-start; padding: 16px; }
  .contract-document { padding: 12px; }
  .contract-document pre { padding: 20px; }
  .ritual-content { padding: 20px; }
  .ritual-timing { align-items: flex-start; flex-direction: column; }
  .ritual-timing span { text-align: left; }
}
</style>
