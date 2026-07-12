<script setup lang="ts">
import { onMounted, ref } from 'vue'
import * as echarts from 'echarts'
import { api } from '../api'

const stats = ref<any>({ total_reviews: 0, average_risk_score: 0, average_duration_ms: 0, risk_levels: {}, contract_types: {}, models: {} })
const recent = ref<any[]>([])
onMounted(async () => {
  try {
    stats.value = (await api.get('/analysis-history/statistics')).data.data
    recent.value = (await api.get('/analysis-history?page_size=6')).data.data.items
    const chart = echarts.init(document.getElementById('risk-chart')!)
    chart.setOption({ tooltip:{trigger:'item'}, color:['#DC2626','#D97706','#16A34A','#2563EB'], series:[{type:'pie',radius:['54%','76%'],label:{color:'#475569'},data:Object.entries(stats.value.risk_levels).map(([name,value])=>({name,value}))}] })
  } catch {}
})
</script>
<template>
  <div class="page-head"><div><h1>经营看板</h1><p>合同风险、审查效率与模型运行概览</p></div><router-link to="/review"><el-button type="primary">发起智能审查</el-button></router-link></div>
  <section class="metrics"><article><span>累计审查</span><strong>{{ stats.total_reviews }}</strong><small>份合同</small></article><article><span>平均风险分</span><strong>{{ stats.average_risk_score }}</strong><small>/ 100</small></article><article><span>平均处理耗时</span><strong>{{ Math.round(stats.average_duration_ms / 1000) }}</strong><small>秒</small></article><article><span>运行模型</span><strong>{{ Object.keys(stats.models).length }}</strong><small>个配置</small></article></section>
  <section class="dashboard-grid"><div class="panel"><div class="panel-title"><h2>风险等级分布</h2><span>全部审查记录</span></div><div id="risk-chart" class="chart"></div></div><div class="panel"><div class="panel-title"><h2>最近审查</h2><router-link to="/contracts">查看全部</router-link></div><el-table :data="recent" height="300"><el-table-column prop="file_name" label="合同" min-width="160" /><el-table-column prop="overall_risk_level" label="风险" width="90" /><el-table-column prop="risk_score" label="评分" width="70" /></el-table></div></section>
</template>
