<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{ level?: string }>()
const normalized = computed(() => {
  if (props.level === '严重') return 'critical'
  if (props.level === '高') return 'high'
  if (props.level === '中') return 'medium'
  return 'low'
})
</script>

<template><span class="risk-level-tag" :class="`is-${normalized}`">{{ level || '低' }}风险</span></template>
