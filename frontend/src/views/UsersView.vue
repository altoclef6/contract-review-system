<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import PageHeader from '../components/PageHeader.vue'
import ErrorState from '../components/ErrorState.vue'
import EmptyState from '../components/EmptyState.vue'
import { api } from '../api'

const loading = ref(false)
const error = ref('')
const users = ref<any[]>([])
const actionId = ref('')
const roles: Record<string, string> = { admin: '管理员', legal: '法务', employee: '业务人员' }

async function load() {
  loading.value = true; error.value = ''
  try { users.value = (await api.get('/admin/users')).data.data }
  catch (cause: any) { error.value = cause?.response?.data?.message || cause?.response?.data?.detail || '用户列表加载失败' }
  finally { loading.value = false }
}

async function changeRole(row: any, role: string) {
  actionId.value = row.id
  try { await api.patch(`/admin/users/${row.id}/role`, { role }); ElMessage.success('用户角色已更新'); await load() }
  catch (cause: any) { ElMessage.error(cause?.response?.data?.message || cause?.response?.data?.detail || '角色更新失败') }
  finally { actionId.value = '' }
}

async function toggle(row: any) {
  const disabled = row.is_active
  await ElMessageBox.confirm(`确认${disabled ? '禁用' : '启用'}账号“${row.full_name}”？`, '账号状态确认', { type: 'warning' })
  actionId.value = row.id
  try { await api.patch(`/admin/users/${row.id}/disabled`, { disabled }); ElMessage.success('账号状态已更新'); await load() }
  catch (cause: any) { ElMessage.error(cause?.response?.data?.message || cause?.response?.data?.detail || '账号状态更新失败') }
  finally { actionId.value = '' }
}

async function resetPassword(row: any) {
  await ElMessageBox.confirm(`重置“${row.full_name}”的登录密码？旧密码会立即失效。`, '重置密码', { type: 'warning' })
  actionId.value = row.id
  try {
    const result = (await api.post(`/admin/users/${row.id}/reset-password`)).data.data
    await ElMessageBox.alert(`一次性临时密码：${result.temporary_password}\n请通过安全渠道交给用户，并要求登录后立即修改。`, '密码已重置', { confirmButtonText: '我已安全保存' })
  } catch (cause: any) { ElMessage.error(cause?.response?.data?.message || cause?.response?.data?.detail || '密码重置失败') }
  finally { actionId.value = '' }
}

function formatDate(value?: string) { return value ? new Date(value).toLocaleString('zh-CN', { hour12: false }) : '从未登录' }
onMounted(load)
</script>

<template>
  <div class="users-center">
    <PageHeader title="用户与权限" description="管理真实用户角色和账号状态，所有变更均写入审计日志。" eyebrow="ACCESS CONTROL" />
    <ErrorState v-if="error" title="用户加载失败" :description="error" @retry="load" />
    <section v-else class="panel table-panel">
      <el-table v-loading="loading" :data="users" row-key="id">
        <el-table-column prop="full_name" label="姓名" min-width="150" />
        <el-table-column prop="email" label="邮箱" min-width="220" show-overflow-tooltip />
        <el-table-column label="角色" width="170"><template #default="{ row }"><el-select :model-value="row.role" :loading="actionId === row.id" @change="changeRole(row, $event)"><el-option v-for="(label, value) in roles" :key="value" :label="label" :value="value" /></el-select></template></el-table-column>
        <el-table-column label="状态" width="100"><template #default="{ row }"><el-tag :type="row.is_active ? 'success' : 'info'">{{ row.is_active ? '启用' : '禁用' }}</el-tag></template></el-table-column>
        <el-table-column label="最近登录" width="190"><template #default="{ row }">{{ formatDate(row.last_login_at) }}</template></el-table-column>
        <el-table-column label="操作" width="220" fixed="right"><template #default="{ row }"><el-button link :type="row.is_active ? 'danger' : 'primary'" :loading="actionId === row.id" @click="toggle(row)">{{ row.is_active ? '禁用' : '启用' }}</el-button><el-button link @click="resetPassword(row)">重置密码</el-button></template></el-table-column>
        <template #empty><EmptyState compact title="暂无用户" description="当前系统中没有可管理的用户记录。" /></template>
      </el-table>
    </section>
  </div>
</template>
