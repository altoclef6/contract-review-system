<script setup lang="ts">
import { Lock } from '@element-plus/icons-vue'
</script>

<template>
  <section class="route-error-page">
    <span><el-icon><Lock /></el-icon></span><small>403</small>
    <h1>当前账号无权访问</h1>
    <p>该模块仅向获得相应权限的角色开放。你可以返回工作台继续使用已授权功能。</p>
    <router-link to="/dashboard"><el-button type="primary">返回工作台</el-button></router-link>
  </section>
</template>
