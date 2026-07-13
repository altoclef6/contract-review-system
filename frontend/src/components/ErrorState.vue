<script setup lang="ts">
import { Warning } from '@element-plus/icons-vue'

withDefaults(defineProps<{ title?: string; description?: string }>(), {
  title: '内容加载失败',
  description: '请检查网络连接后重试。',
})
const emit = defineEmits<{ retry: [] }>()
</script>

<template>
  <section class="common-state common-error-state" role="alert">
    <span class="common-state__icon"><el-icon><Warning /></el-icon></span><h2>{{ title }}</h2><p>{{ description }}</p>
    <el-button @click="emit('retry')">重新加载</el-button>
  </section>
</template>
