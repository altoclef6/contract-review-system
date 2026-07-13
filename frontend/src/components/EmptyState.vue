<script setup lang="ts">
import { Document } from '@element-plus/icons-vue'

withDefaults(defineProps<{ title: string; description: string; compact?: boolean }>(), { compact: false })
</script>

<template>
  <section class="common-state common-empty-state" :class="{ 'is-compact': compact }">
    <span class="common-state__icon"><el-icon><Document /></el-icon></span>
    <h2>{{ title }}</h2><p>{{ description }}</p><slot />
  </section>
</template>
