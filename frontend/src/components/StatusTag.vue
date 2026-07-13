<script setup lang="ts">
defineProps<{ label: string; tone?: 'neutral' | 'info' | 'success' | 'warning' | 'danger' }>()
</script>

<template><span class="status-tag" :class="`is-${tone || 'neutral'}`"><i></i>{{ label }}</span></template>
