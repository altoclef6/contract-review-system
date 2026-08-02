<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{ level?: string }>()
const normalized = computed(() => {
  const value = String(props.level || '').toUpperCase()
  if (props.level === '严重' || value === 'CRITICAL') return 'critical'
  if (props.level === '高' || value === 'HIGH') return 'high'
  if (props.level === '中' || value === 'MEDIUM') return 'medium'
  return 'low'
})
const label = computed(() => ({ critical: '严重', high: '高', medium: '中', low: '低' }[normalized.value]))
</script>

<template><span class="risk-level-tag" :class="`is-${normalized}`">{{ label }}风险</span></template>
