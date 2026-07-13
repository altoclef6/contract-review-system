<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Document, Lock, Message } from '@element-plus/icons-vue'
import { api } from '../api'
import { useAuthStore } from '../stores/auth'

const email = ref('')
const password = ref('')
const loading = ref(false)
const forgotDialog = ref(false)
const forgotEmail = ref('')
const forgotLoading = ref(false)
const auth = useAuthStore()
const router = useRouter()

async function submit() {
  if (!email.value || !password.value) {
    ElMessage.warning('请输入企业邮箱和登录密码')
    return
  }
  loading.value = true
  try {
    await auth.login(email.value, password.value)
    await router.push('/dashboard')
  } catch (error: any) {
    if (!error.response) ElMessage.error('无法连接服务器，请确认后端服务正在运行')
    else if (error.response.status === 401) ElMessage.error('账号或密码不正确')
    else ElMessage.error(error.response?.data?.message || '登录失败，请稍后重试')
  } finally {
    loading.value = false
  }
}

function openForgotPassword() {
  forgotEmail.value = email.value
  forgotDialog.value = true
}

async function submitForgotPassword() {
  if (!forgotEmail.value) {
    ElMessage.warning('请输入注册邮箱')
    return
  }
  forgotLoading.value = true
  try {
    await api.post('/auth/forgot-password', { email: forgotEmail.value })
    forgotDialog.value = false
    ElMessage.success('如该账号存在，系统将按已配置渠道发送重置说明')
  } catch (error: any) {
    ElMessage.error(error.response?.data?.message || '请求提交失败，请稍后重试')
  } finally {
    forgotLoading.value = false
  }
}
</script>

<template>
  <main class="enterprise-login">
    <section class="login-overview">
      <div class="login-brand"><span><el-icon><Document /></el-icon></span><div><strong>衡契</strong><small>企业合同审查与合规管理平台</small></div></div>
      <div class="login-overview__copy">
        <span>ENTERPRISE CONTRACT REVIEW</span>
        <h1>让合同风险审查<br>更清晰、更可追溯</h1>
        <p>统一管理合同、审查结果与协同流程，为企业法务和业务团队提供 AI 辅助风险识别能力。</p>
        <ul><li>确定性规则优先</li><li>风险原文可定位</li><li>重要结论人工复核</li></ul>
      </div>
      <p class="login-disclaimer">AI 辅助合同风险审查，不构成正式法律意见，重要合同应由专业法务或律师结合交易背景进行人工复核。</p>
    </section>

    <section class="login-form-panel">
      <div class="login-form-card">
        <header><span>安全登录</span><h2>欢迎使用衡契</h2><p>请输入企业账号进入合同审查平台</p></header>
        <el-form label-position="top" @submit.prevent="submit">
          <el-form-item label="企业邮箱">
            <el-input v-model="email" size="large" autocomplete="username" placeholder="name@company.com" :prefix-icon="Message" />
          </el-form-item>
          <el-form-item label="登录密码">
            <el-input v-model="password" type="password" show-password size="large" autocomplete="current-password" placeholder="请输入登录密码" :prefix-icon="Lock" @keyup.enter="submit" />
          </el-form-item>
          <div class="login-form-actions"><button type="button" @click="openForgotPassword">忘记密码？</button></div>
          <el-button type="primary" size="large" :loading="loading" class="login-submit" @click="submit">登录工作台</el-button>
        </el-form>
        <footer><i></i><span>登录即表示您同意遵守企业数据与合同保密制度</span></footer>
      </div>
    </section>
  </main>

  <el-dialog v-model="forgotDialog" title="找回密码" width="420px" append-to-body>
    <p class="dialog-description">提交注册邮箱后，系统会返回统一安全提示，不会披露账号是否存在。</p>
    <el-form label-position="top" @submit.prevent="submitForgotPassword">
      <el-form-item label="注册邮箱"><el-input v-model="forgotEmail" autocomplete="email" placeholder="name@company.com" @keyup.enter="submitForgotPassword" /></el-form-item>
    </el-form>
    <template #footer><el-button @click="forgotDialog = false">取消</el-button><el-button type="primary" :loading="forgotLoading" @click="submitForgotPassword">提交申请</el-button></template>
  </el-dialog>
</template>
