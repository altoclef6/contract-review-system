<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  Bell,
  ChatLineRound,
  DataAnalysis,
  Document,
  Files,
  Link,
  Operation,
  Setting,
  SwitchButton,
} from '@element-plus/icons-vue'
import { api } from '../api'
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore(); const route = useRoute(); const router = useRouter(); const unread = ref(0)
const menus = computed(() => [
  ['/dashboard', '经营看板', DataAnalysis], ['/contracts', '合同中心', Files], ['/review', '智能审查', Document],
  ['/assistant', 'AI 法务助手', ChatLineRound], ['/workflows', '审批流程', Operation],
  ...(auth.user?.role !== 'employee' ? [['/settings', '系统配置', Setting] as any] : []),
])
onMounted(async () => { try { unread.value = (await api.get('/notifications')).data.data.unread_count } catch {} })
function logout() { auth.logout(); router.push('/login') }
function openApiDocs() {
  window.location.href = import.meta.env.DEV ? 'http://127.0.0.1:8000/docs' : '/docs'
}
</script>

<template>
  <div class="shell">
    <aside class="sidebar">
      <div class="brand"><span>衡</span><div><b>衡契</b><small>CONTRACT AI</small></div></div>
      <nav><router-link v-for="item in menus" :key="item[0]" :to="item[0]" :class="{ active: route.path.startsWith(item[0] as string) }"><el-icon><component :is="item[2]" /></el-icon>{{ item[1] }}</router-link></nav>
      <div class="account"><div class="avatar">{{ auth.user?.full_name?.slice(0, 1) }}</div><div><b>{{ auth.user?.full_name }}</b><small>{{ {admin:'管理员',legal:'法务',employee:'员工'}[auth.user?.role || 'employee'] }}</small></div><el-button text circle title="退出登录" @click="logout"><el-icon><SwitchButton /></el-icon></el-button></div>
    </aside>
    <section class="workspace">
      <header class="topbar"><div><b>企业合同风险控制中心</b><span>Multi-Agent 协同审查在线</span></div><div class="topbar-actions"><el-button title="打开 RESTful 接口文档" @click="openApiDocs"><el-icon><Link /></el-icon><span>接口文档</span></el-button><el-badge :value="unread" :hidden="!unread"><el-button circle title="通知中心"><el-icon><Bell /></el-icon></el-button></el-badge></div></header>
      <main class="page"><router-view /></main>
    </section>
  </div>
</template>
