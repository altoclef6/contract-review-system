<script setup lang="ts">
withDefaults(defineProps<{ title?: string; description?: string }>(), {
  title: '正在加载',
  description: '请稍候，系统正在获取最新数据。',
})
</script>

<template>
  <section class="common-state common-loading-state" aria-live="polite" aria-busy="true">
    <span class="common-loading-indicator"></span><h2>{{ title }}</h2><p>{{ description }}</p>
  </section>
</template>
