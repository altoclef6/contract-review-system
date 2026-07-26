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
const registerDialog = ref(false)
const registerName = ref('')
const registerEmail = ref('')
const registerPassword = ref('')
const registerPasswordConfirm = ref('')
const registerLoading = ref(false)
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

function openRegister() {
  registerEmail.value = email.value
  registerDialog.value = true
}

async function submitRegister() {
  if (!registerName.value.trim() || !registerEmail.value.trim() || !registerPassword.value) {
    ElMessage.warning('请填写姓名、邮箱和密码')
    return
  }
  if (registerPassword.value.length < 8) {
    ElMessage.warning('密码至少需要 8 个字符')
    return
  }
  if (registerPassword.value !== registerPasswordConfirm.value) {
    ElMessage.warning('两次输入的密码不一致')
    return
  }
  registerLoading.value = true
  try {
    await api.post('/auth/register', {
      full_name: registerName.value.trim(),
      email: registerEmail.value.trim(),
      password: registerPassword.value,
    })
    await auth.login(registerEmail.value.trim(), registerPassword.value)
    registerPassword.value = ''
    registerPasswordConfirm.value = ''
    registerDialog.value = false
    ElMessage.success('账号创建成功')
    await router.push('/dashboard')
  } catch (error: any) {
    if (!error.response) ElMessage.error('无法连接服务器，请确认后端服务正在运行')
    else if (error.response.status === 409) ElMessage.error('该邮箱已注册，请直接登录')
    else ElMessage.error(error.response?.data?.message || '注册失败，请稍后重试')
  } finally {
    registerLoading.value = false
  }
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
    <div class="login-bg-shapes" aria-hidden="true">
      <div class="shape shape-1"></div>
      <div class="shape shape-2"></div>
      <div class="shape shape-3"></div>
    </div>

    <div class="login-container">
      <section class="login-overview">
        <div class="login-brand">
          <span class="brand-logo"><el-icon><Document /></el-icon></span>
          <div class="brand-text">
            <strong>衡契</strong>
            <small>企业合同审查与合规管理平台</small>
          </div>
        </div>

        <div class="login-overview__copy">
          <span class="copy-tag">ENTERPRISE CONTRACT REVIEW</span>
          <h1>让合同风险审查<br>更清晰、更可追溯</h1>
          <p>统一管理合同、审查结果与协同流程，为企业法务和业务团队提供 AI 辅助风险识别能力。</p>
          <ul>
            <li>确定性规则优先</li>
            <li>风险原文可定位</li>
            <li>重要结论人工复核</li>
          </ul>
        </div>

        <p class="login-disclaimer">
          <el-icon><Document /></el-icon>
          <span>AI 辅助合同风险审查，不构成正式法律意见，重要合同应由专业法务或律师结合交易背景进行人工复核。</span>
        </p>
      </section>

      <section class="login-form-panel">
        <div class="login-form-card">
          <header>
            <span class="header-badge">安全登录</span>
            <h2>欢迎使用衡契</h2>
            <p>请输入企业账号进入合同审查平台</p>
          </header>

          <el-form label-position="top" @submit.prevent="submit">
            <el-form-item label="企业邮箱">
              <el-input v-model="email" size="large" autocomplete="username" placeholder="name@company.com" :prefix-icon="Message" />
            </el-form-item>
            <el-form-item label="登录密码">
              <el-input v-model="password" type="password" show-password size="large" autocomplete="current-password" placeholder="请输入登录密码" :prefix-icon="Lock" @keyup.enter="submit" />
            </el-form-item>

            <div class="login-form-actions">
              <button type="button" class="action-link" @click="openRegister">创建本地账号</button>
              <button type="button" class="action-link" @click="openForgotPassword">忘记密码？</button>
            </div>

            <el-button type="primary" size="large" :loading="loading" class="login-submit" @click="submit">
              登录工作台
            </el-button>
          </el-form>

          <footer>
            <i class="status-dot"></i>
            <span>登录即表示您同意遵守企业数据与合同保密制度</span>
          </footer>
        </div>
      </section>
    </div>
  </main>

  <el-dialog v-model="registerDialog" title="创建本地账号" width="440px" append-to-body class="glass-dialog">
    <p class="dialog-description">账号和合同数据仅保存在当前电脑。新账号默认为普通用户权限。</p>
    <el-form label-position="top" @submit.prevent="submitRegister">
      <el-form-item label="姓名">
        <el-input v-model="registerName" maxlength="80" autocomplete="name" placeholder="请输入姓名" />
      </el-form-item>
      <el-form-item label="邮箱">
        <el-input v-model="registerEmail" autocomplete="email" placeholder="name@example.com" />
      </el-form-item>
      <el-form-item label="密码">
        <el-input v-model="registerPassword" type="password" show-password maxlength="128" autocomplete="new-password" placeholder="至少 8 个字符" />
      </el-form-item>
      <el-form-item label="确认密码">
        <el-input v-model="registerPasswordConfirm" type="password" show-password maxlength="128" autocomplete="new-password" placeholder="请再次输入密码" @keyup.enter="submitRegister" />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="registerDialog = false">取消</el-button>
      <el-button type="primary" :loading="registerLoading" @click="submitRegister">创建并登录</el-button>
    </template>
  </el-dialog>

  <el-dialog v-model="forgotDialog" title="找回密码" width="420px" append-to-body class="glass-dialog">
    <p class="dialog-description">提交注册邮箱后，系统会返回统一安全提示，不会披露账号是否存在。</p>
    <el-form label-position="top" @submit.prevent="submitForgotPassword">
      <el-form-item label="注册邮箱"><el-input v-model="forgotEmail" autocomplete="email" placeholder="name@company.com" @keyup.enter="submitForgotPassword" /></el-form-item>
    </el-form>
    <template #footer><el-button @click="forgotDialog = false">取消</el-button><el-button type="primary" :loading="forgotLoading" @click="submitForgotPassword">提交申请</el-button></template>
  </el-dialog>
</template>
