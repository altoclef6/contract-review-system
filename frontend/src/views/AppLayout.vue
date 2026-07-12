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
const apiDocsUrl = import.meta.env.DEV ? 'http://127.0.0.1:8000/docs' : '/docs'
const menus = computed(() => [
  ['/dashboard', '经营看板', DataAnalysis, '01'], ['/contracts', '合同中心', Files, '02'], ['/review', '智能审查', Document, '03'],
  ['/assistant', 'AI 法务助手', ChatLineRound, '04'], ['/workflows', '审批流程', Operation, '05'],
  ...(auth.user?.role !== 'employee' ? [['/settings', '系统配置', Setting, '06'] as any] : []),
])
const activeModule = computed(() => menus.value.find((item) => route.path.startsWith(item[0] as string)) || menus.value[0])
onMounted(async () => { try { unread.value = (await api.get('/notifications')).data.data.unread_count } catch {} })
function logout() { auth.logout(); router.push('/login') }
function openApiDocs() {
  window.location.href = apiDocsUrl
}
</script>

<template>
  <div class="shell">
    <aside class="sidebar">
      <div class="brand"><span>衡</span><div><b>衡契</b><small>CONTRACT INTELLIGENCE</small></div></div>
      <div class="system-status"><i></i><span>审查中枢在线</span><small>HQ / 01</small></div>
      <nav><router-link v-for="item in menus" :key="item[0]" :to="item[0]" :class="{ active: route.path.startsWith(item[0] as string) }"><small>{{ item[3] }}</small><el-icon><component :is="item[2]" /></el-icon><span>{{ item[1] }}</span></router-link><a :href="apiDocsUrl" class="api-doc-link" title="打开 RESTful 接口文档"><small>API</small><el-icon><Link /></el-icon><span>接口文档</span></a></nav>
      <div class="account"><div class="avatar">{{ auth.user?.full_name?.slice(0, 1) }}</div><div><b>{{ auth.user?.full_name }}</b><small>{{ {admin:'管理员',legal:'法务',employee:'员工'}[auth.user?.role || 'employee'] }}</small></div><el-button text circle title="退出登录" @click="logout"><el-icon><SwitchButton /></el-icon></el-button></div>
    </aside>
    <section class="workspace">
      <header class="topbar"><div class="module-identity"><strong>{{ activeModule[3] }}</strong><div><small>CURRENT MODULE</small><b>{{ activeModule[1] }}</b></div></div><div class="topbar-heading"><small>ENTERPRISE ARCHIVE / CONTRACT CONTROL</small><b>企业合同风险控制中心</b><span><i></i> Multi-Agent 协同审查在线</span></div><div class="topbar-actions"><el-button title="打开 RESTful 接口文档" @click="openApiDocs"><el-icon><Link /></el-icon><span>接口文档</span></el-button><el-badge :value="unread" :hidden="!unread"><el-button circle title="通知中心"><el-icon><Bell /></el-icon></el-button></el-badge></div></header>
      <main class="page"><div class="page-calibration" aria-hidden="true"><span>HENGQI / SYSTEM</span><i></i><span>SECURE LEVEL 04</span></div><router-view /></main>
    </section>
  </div>
</template>
