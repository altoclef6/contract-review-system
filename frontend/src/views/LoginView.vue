<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { ArrowRight, View } from '@element-plus/icons-vue'
import { useAuthStore } from '../stores/auth'

const email = ref('admin@example.com')
const password = ref('Admin12345!')
const loading = ref(false)
const auth = useAuthStore()
const router = useRouter()
const apiDocsUrl = import.meta.env.DEV ? 'http://127.0.0.1:8000/docs' : '/docs'

async function submit() {
  loading.value = true
  try {
    await auth.login(email.value, password.value)
    await router.push('/dashboard')
  } catch (error: any) {
    if (!error.response) {
      ElMessage.error('无法连接服务器，请先启动后端服务')
    } else if (error.response.status === 401) {
      ElMessage.error('账号或密码不正确')
    } else {
      ElMessage.error(error.response?.data?.message || '登录失败，请稍后重试')
    }
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <main class="login-page immersive-login">
    <div class="immersive-scene" aria-hidden="true">
      <div class="scene-image"></div>
      <div class="scene-vignette"></div>
    </div>

    <header class="immersive-brand">
      <span class="brand-seal">衡</span>
      <div><b>衡契</b><small>ENTERPRISE CONTRACT INTELLIGENCE</small></div>
    </header>

    <section class="login-narrative">
      <p class="narrative-index">ARCHIVE / 01</p>
      <h1>衡契</h1>
      <p class="narrative-en">THE COVENANT<br>INTELLIGENCE ARCHIVE</p>
      <div class="narrative-rule"><span></span><i></i></div>
      <p class="narrative-copy">进入合同风险控制域</p>
    </section>

    <section class="immersive-login-form">
      <div class="form-heading"><span>探索者信息</span><b>身份核验</b></div>
      <el-form label-position="top" @submit.prevent="submit">
        <el-form-item label="企业邮箱"><el-input v-model="email" size="large" /></el-form-item>
        <el-form-item label="登录密码"><el-input v-model="password" type="password" show-password size="large" @keyup.enter="submit" /></el-form-item>
        <el-button type="primary" size="large" :loading="loading" class="immersive-enter" @click="submit">
          进入工作台<el-icon><ArrowRight /></el-icon>
        </el-button>
      </el-form>
      <div class="login-links"><button class="text-button">忘记密码</button><a :href="apiDocsUrl"><el-icon><View /></el-icon>接口文档</a></div>
    </section>

    <footer class="immersive-footer"><span>SECURE CHANNEL</span><i></i><span>MULTI-AGENT ONLINE</span></footer>
  </main>
</template>
