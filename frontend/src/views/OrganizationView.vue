<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { api } from '../api'

const data = ref<any>({ company: null, departments: [], members: [] })
const departmentDialog = ref(false)
const memberDialog = ref(false)
const department = reactive({ name: '', code: '', parent_id: '' })
const member = reactive({
  email: '',
  password: '',
  full_name: '',
  role: 'member',
  department_id: '',
  job_title: '',
})

async function load() {
  data.value = (await api.get('/organization/overview')).data.data
}
async function createDepartment() {
  await api.post('/organization/departments', {
    name: department.name,
    code: department.code || null,
    parent_id: department.parent_id || null,
  })
  departmentDialog.value = false
  Object.assign(department, { name: '', code: '', parent_id: '' })
  await load()
  ElMessage.success('部门已创建')
}
async function createMember() {
  await api.post('/organization/members', {
    ...member,
    department_id: member.department_id || null,
    job_title: member.job_title || null,
  })
  memberDialog.value = false
  Object.assign(member, {
    email: '', password: '', full_name: '', role: 'member', department_id: '', job_title: '',
  })
  await load()
  ElMessage.success('成员已加入企业')
}
const roleName: Record<string, string> = {
  admin: '系统管理员',
  company_admin: '企业管理员',
  legal_manager: '法务负责人',
  legal: '法务成员',
  member: '企业成员',
  employee: '普通成员',
}
onMounted(load)
</script>

<template>
  <section>
    <header class="page-header">
      <div>
        <span class="page-header__eyebrow">Organization</span>
        <h1>企业与成员</h1>
        <p>管理企业资料、组织部门和成员角色，数据访问始终限定在当前企业。</p>
      </div>
      <div class="page-header__actions">
        <el-button @click="departmentDialog = true">新建部门</el-button>
        <el-button type="primary" @click="memberDialog = true">添加成员</el-button>
      </div>
    </header>

    <div v-if="data.company" class="organization-overview">
      <article class="org-company glass-panel">
        <span>当前企业</span>
        <h2>{{ data.company.name }}</h2>
        <p>企业代码 {{ data.company.code }} · 状态正常</p>
        <div class="org-stats">
          <div><strong>{{ data.members.length }}</strong><span>企业成员</span></div>
          <div><strong>{{ data.departments.length }}</strong><span>组织部门</span></div>
        </div>
      </article>
      <article class="org-departments glass-panel">
        <div class="agent-section-title"><strong>部门结构</strong><span>{{ data.departments.length }}</span></div>
        <div v-if="data.departments.length" class="org-chip-list">
          <span v-for="item in data.departments" :key="item.id">{{ item.name }}<small>{{ item.code || '未设置编码' }}</small></span>
        </div>
        <p v-else class="agent-mini-empty">尚未创建部门</p>
      </article>
    </div>

    <section class="org-members glass-panel">
      <div class="agent-section-title"><strong>企业成员</strong><span>{{ data.members.length }}</span></div>
      <el-table :data="data.members" class="enterprise-table">
        <el-table-column label="成员" min-width="220">
          <template #default="{ row }">
            <div class="member-identity"><i>{{ row.full_name.slice(0, 1) }}</i><div><strong>{{ row.full_name }}</strong><span>{{ row.email }}</span></div></div>
          </template>
        </el-table-column>
        <el-table-column label="角色" width="140"><template #default="{ row }"><el-tag>{{ roleName[row.role] || row.role }}</el-tag></template></el-table-column>
        <el-table-column prop="job_title" label="职位" min-width="150" />
        <el-table-column label="状态" width="110"><template #default="{ row }"><el-tag :type="row.is_active ? 'success' : 'info'">{{ row.is_active ? '正常' : '已停用' }}</el-tag></template></el-table-column>
      </el-table>
    </section>

    <el-dialog v-model="departmentDialog" title="新建部门" width="480px">
      <el-form label-position="top">
        <el-form-item label="部门名称"><el-input v-model="department.name" /></el-form-item>
        <el-form-item label="部门编码"><el-input v-model="department.code" /></el-form-item>
      </el-form>
      <template #footer><el-button @click="departmentDialog = false">取消</el-button><el-button type="primary" @click="createDepartment">创建</el-button></template>
    </el-dialog>
    <el-dialog v-model="memberDialog" title="添加企业成员" width="520px">
      <el-form label-position="top">
        <el-form-item label="姓名"><el-input v-model="member.full_name" /></el-form-item>
        <el-form-item label="邮箱"><el-input v-model="member.email" /></el-form-item>
        <el-form-item label="初始密码"><el-input v-model="member.password" type="password" show-password /></el-form-item>
        <el-form-item label="角色"><el-select v-model="member.role" style="width:100%"><el-option label="企业成员" value="member" /><el-option label="法务成员" value="legal" /><el-option label="法务负责人" value="legal_manager" /><el-option label="企业管理员" value="company_admin" /></el-select></el-form-item>
        <el-form-item label="部门"><el-select v-model="member.department_id" clearable style="width:100%"><el-option v-for="item in data.departments" :key="item.id" :label="item.name" :value="item.id" /></el-select></el-form-item>
        <el-form-item label="职位"><el-input v-model="member.job_title" /></el-form-item>
      </el-form>
      <template #footer><el-button @click="memberDialog = false">取消</el-button><el-button type="primary" @click="createMember">添加成员</el-button></template>
    </el-dialog>
  </section>
</template>
