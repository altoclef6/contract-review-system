<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import AppShell from '../components/layout/AppShell.vue'
import GlobalAssistant from '../components/GlobalAssistant.vue'
import { api } from '../api'
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()
const route = useRoute()
const router = useRouter()
const unread = ref(0)
const collapsed = ref(window.innerWidth < 1100)
const passwordDialog = ref(false)
const profileDialog = ref(false)
const passwordLoading = ref(false)
const passwordForm = reactive({ current: '', next: '', confirm: '' })
const apiDocsUrl = import.meta.env.DEV ? 'http://127.0.0.1:8000/docs' : '/docs'

const role = computed(() => auth.user?.role || 'employee')
const pageTitle = computed(() => String(route.meta.title || '衡契合同审查平台'))
const breadcrumb = computed(() => String(route.meta.section || '业务中心'))

function onResize() {
  if (window.innerWidth < 900) collapsed.value = true
}

onMounted(async () => {
  window.addEventListener('resize', onResize)
  try {
    unread.value = (await api.get('/notifications')).data.data.unread_count
  } catch {
    unread.value = 0
  }
})

onBeforeUnmount(() => window.removeEventListener('resize', onResize))

watch(() => route.path, () => {
  if (window.innerWidth < 900) collapsed.value = true
})

async function logout() {
  try {
    await ElMessageBox.confirm('退出后需要重新登录，确认退出当前账号吗？', '退出登录', {
      type: 'warning', confirmButtonText: '确认退出', cancelButtonText: '取消',
    })
  } catch { return }
  auth.logout()
  router.push('/login')
}

function handleNavigate() {
  if (window.innerWidth < 900) collapsed.value = true
}

function openPasswordDialog() {
  passwordForm.current = ''
  passwordForm.next = ''
  passwordForm.confirm = ''
  passwordDialog.value = true
}

async function changePassword() {
  if (!passwordForm.current || !passwordForm.next) {
    ElMessage.warning('请填写当前密码和新密码')
    return
  }
  if (passwordForm.next.length < 8) {
    ElMessage.warning('新密码至少需要 8 个字符')
    return
  }
  if (passwordForm.next !== passwordForm.confirm) {
    ElMessage.warning('两次输入的新密码不一致')
    return
  }
  passwordLoading.value = true
  try {
    await api.post('/auth/change-password', {
      old_password: passwordForm.current,
      new_password: passwordForm.next,
    })
    passwordDialog.value = false
    ElMessage.success('密码已修改，请重新登录')
    auth.logout()
    router.push('/login')
  } catch (error: any) {
    ElMessage.error(error.response?.data?.message || '密码修改失败，请检查当前密码')
  } finally {
    passwordLoading.value = false
  }
}
</script>

<template>
  <AppShell
    :collapsed="collapsed"
    :page-title="pageTitle"
    :breadcrumb="breadcrumb"
    :unread="unread"
    :user-name="auth.user?.full_name || ''"
    :role="role"
    :api-docs-url="apiDocsUrl"
    @toggle="collapsed = !collapsed"
    @navigate="handleNavigate"
    @logout="logout"
    @change-password="openPasswordDialog"
    @profile="profileDialog = true"
  >
    <router-view v-slot="{ Component, route: currentRoute }">
      <transition name="page-fade" mode="out-in">
        <div :key="currentRoute.path" class="route-stage"><component :is="Component" /></div>
      </transition>
    </router-view>
  </AppShell>
  <GlobalAssistant />

  <el-dialog v-model="profileDialog" title="个人中心" width="460px" append-to-body>
    <el-descriptions :column="1" border>
      <el-descriptions-item label="姓名">{{ auth.user?.full_name || '当前用户' }}</el-descriptions-item>
      <el-descriptions-item label="登录账号">{{ auth.user?.email }}</el-descriptions-item>
      <el-descriptions-item label="账号角色">{{ role === 'admin' ? '管理员' : role === 'legal' ? '法务' : '员工' }}</el-descriptions-item>
      <el-descriptions-item label="数据范围">{{ role === 'admin' ? '企业全部授权数据' : '本人上传、负责或被授权的数据' }}</el-descriptions-item>
    </el-descriptions>
    <template #footer><el-button @click="openPasswordDialog">修改密码</el-button><el-button type="primary" @click="profileDialog = false">完成</el-button></template>
  </el-dialog>

  <el-dialog v-model="passwordDialog" title="修改登录密码" width="440px" append-to-body>
    <el-form label-position="top" @submit.prevent="changePassword">
      <el-form-item label="当前密码"><el-input v-model="passwordForm.current" type="password" show-password autocomplete="current-password" /></el-form-item>
      <el-form-item label="新密码"><el-input v-model="passwordForm.next" type="password" show-password autocomplete="new-password" /></el-form-item>
      <el-form-item label="确认新密码"><el-input v-model="passwordForm.confirm" type="password" show-password autocomplete="new-password" @keyup.enter="changePassword" /></el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="passwordDialog = false">取消</el-button>
      <el-button type="primary" :loading="passwordLoading" @click="changePassword">确认修改</el-button>
    </template>
  </el-dialog>
</template>
