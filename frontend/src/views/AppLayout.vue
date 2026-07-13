<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import AppShell from '../components/layout/AppShell.vue'
import { api } from '../api'
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()
const route = useRoute()
const router = useRouter()
const unread = ref(0)
const collapsed = ref(window.innerWidth < 1100)
const passwordDialog = ref(false)
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

function logout() {
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
    logout()
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
  >
    <router-view v-slot="{ Component, route: currentRoute }">
      <transition name="page-fade" mode="out-in">
        <div :key="currentRoute.path" class="route-stage"><component :is="Component" /></div>
      </transition>
    </router-view>
  </AppShell>

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
