<script setup lang="ts">
defineProps<{ label: string; value: string | number; unit?: string; tone?: 'default' | 'critical' | 'high' | 'medium' | 'low' }>()
</script>

<template>
  <article class="common-metric-card" :class="`is-${tone || 'default'}`">
    <span>{{ label }}</span>
    <strong>{{ value }}<small v-if="unit">{{ unit }}</small></strong>
    <slot />
  </article>
</template>
