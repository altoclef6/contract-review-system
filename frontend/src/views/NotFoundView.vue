<script setup lang="ts">
import { Compass } from '@element-plus/icons-vue'
</script>

<template>
  <section class="route-error-page">
    <span><el-icon><Compass /></el-icon></span><small>404</small>
    <h1>页面不存在</h1>
    <p>链接可能已失效或页面已调整。返回工作台可继续查看合同与审查任务。</p>
    <router-link to="/dashboard"><el-button type="primary">返回工作台</el-button></router-link>
  </section>
</template>
