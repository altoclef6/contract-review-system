<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useAuthStore } from '../stores/auth'

const email = ref('admin@example.com')
const password = ref('Admin12345!')
const loading = ref(false)
const auth = useAuthStore()
const router = useRouter()
async function submit() {
  loading.value = true
  try { await auth.login(email.value, password.value); await router.push('/dashboard') }
  catch (error: any) { ElMessage.error(error.response?.data?.message || '登录失败，请检查账号和密码') }
  finally { loading.value = false }
}
</script>

<template>
  <main class="login-page">
    <section class="login-panel">
      <div class="brand-mark">衡</div>
      <h1>衡契</h1><p>企业合同智能审查平台</p>
      <el-form label-position="top" @submit.prevent="submit">
        <el-form-item label="企业邮箱"><el-input v-model="email" size="large" /></el-form-item>
        <el-form-item label="登录密码"><el-input v-model="password" type="password" show-password size="large" @keyup.enter="submit" /></el-form-item>
        <el-button type="primary" size="large" :loading="loading" class="full" @click="submit">登录工作台</el-button>
      </el-form>
      <button class="text-button">忘记密码</button>
    </section>
  </main>
</template>
