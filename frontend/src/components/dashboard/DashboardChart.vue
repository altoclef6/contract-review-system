<script setup lang="ts">
import { nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { BarChart, LineChart, PieChart } from 'echarts/charts'
import { GridComponent, LegendComponent, TooltipComponent } from 'echarts/components'
import { init, use, type ECharts, type EChartsCoreOption } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import EmptyState from '../EmptyState.vue'
import ErrorState from '../ErrorState.vue'

use([LineChart, PieChart, BarChart, GridComponent, TooltipComponent, LegendComponent, CanvasRenderer])

const props = defineProps<{
  option: EChartsCoreOption
  empty: boolean
  emptyTitle?: string
  emptyDescription?: string
}>()

const container = ref<HTMLElement>()
const renderError = ref(false)
let chart: ECharts | undefined
let resizeObserver: ResizeObserver | undefined

async function renderChart() {
  if (props.empty) {
    chart?.clear()
    return
  }
  await nextTick()
  if (!container.value) return
  try {
    renderError.value = false
    chart ||= init(container.value, undefined, { renderer: 'canvas' })
    chart.setOption(props.option, true)
    chart.resize()
  } catch {
    renderError.value = true
    chart?.dispose()
    chart = undefined
  }
}

onMounted(() => {
  resizeObserver = new ResizeObserver(() => chart?.resize())
  if (container.value) resizeObserver.observe(container.value)
  renderChart()
})

watch(() => [props.option, props.empty], renderChart, { deep: true })

onBeforeUnmount(() => {
  resizeObserver?.disconnect()
  chart?.dispose()
})
</script>

<template>
  <ErrorState v-if="renderError" title="图表渲染失败" description="该图表暂时无法显示，其他工作台数据不受影响。" @retry="renderChart" />
  <EmptyState v-else-if="empty" compact :title="emptyTitle || '暂无图表数据'" :description="emptyDescription || '当前统计范围内没有可展示的数据。'" />
  <div v-show="!empty && !renderError" ref="container" class="dashboard-chart" role="img"></div>
</template>
