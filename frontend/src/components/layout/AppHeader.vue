<script setup lang="ts">
import { ref } from 'vue'
import { ArrowDown, Bell, Expand, Fold, Link, Lock, SwitchButton } from '@element-plus/icons-vue'
import { floatingGlow as vGlow } from '../../directives/glow'

type UserRole = 'admin' | 'company_admin' | 'legal_manager' | 'legal' | 'member' | 'employee'

defineProps<{
  collapsed: boolean
  pageTitle: string
  breadcrumb: string
  unread: number
  userName: string
  role: UserRole
  apiDocsUrl: string
}>()

const emit = defineEmits<{
  toggle: []
  logout: []
  changePassword: []
}>()

const accountMenuOpen = ref(false)

const roleNames: Record<UserRole, string> = {
  company_admin: '企业管理员',
  legal_manager: '法务负责人',
  member: '企业成员',
  admin: '管理员',
  legal: '法务',
  employee: '员工',
}

function handleCommand(command: string) {
  if (command === 'password') emit('changePassword')
  if (command === 'logout') emit('logout')
}
</script>

<template>
  <header class="app-header">
    <div class="app-header__context">
      <el-button
        v-glow
        class="floating-item sidebar-toggle"
        :aria-label="collapsed ? '展开侧栏' : '折叠侧栏'"
        @click="emit('toggle')"
      >
        <el-icon><component :is="collapsed ? Expand : Fold" /></el-icon>
      </el-button>
      <div v-glow class="floating-item app-header__title">
        <el-breadcrumb separator="/">
          <el-breadcrumb-item>衡契</el-breadcrumb-item>
          <el-breadcrumb-item>{{ breadcrumb }}</el-breadcrumb-item>
        </el-breadcrumb>
        <strong>{{ pageTitle }}</strong>
      </div>
    </div>

    <div class="app-header__actions">
      <div v-glow class="floating-item ai-runtime-status" title="模型可用性将在发起审查时由后端真实验证">
        <i></i>
        <span><strong>AI 服务</strong><small>随审查验证</small></span>
      </div>

      <el-button
        v-glow
        class="floating-item header-icon-button"
        :href="apiDocsUrl"
        tag="a"
        target="_self"
        aria-label="接口文档"
      >
        <el-icon><Link /></el-icon>
      </el-button>
      <el-badge class="header-notification" :value="unread" :hidden="!unread" :max="99">
        <el-button v-glow class="floating-item header-icon-button" aria-label="未读通知">
          <el-icon><Bell /></el-icon>
        </el-button>
      </el-badge>

      <el-dropdown
        trigger="click"
        placement="bottom-end"
        popper-class="harmony-account-dropdown"
        :offset="8"
        :show-timeout="80"
        :hide-timeout="100"
        @visible-change="accountMenuOpen = $event"
        @command="handleCommand"
      >
        <button
          v-glow
          class="floating-item user-menu"
          :class="{ 'is-open': accountMenuOpen }"
          type="button"
          :aria-expanded="accountMenuOpen"
          aria-haspopup="menu"
        >
          <span class="user-menu__avatar">{{ userName.slice(0, 1) || '用' }}</span>
          <span class="user-menu__copy"><strong>{{ userName || '当前用户' }}</strong><small>{{ roleNames[role] }}</small></span>
          <el-icon class="user-menu__arrow"><ArrowDown /></el-icon>
        </button>
        <template #dropdown>
          <el-dropdown-menu class="account-dropdown-menu">
            <el-dropdown-item command="password" :icon="Lock">修改密码</el-dropdown-item>
            <el-dropdown-item class="account-dropdown-menu__danger" command="logout" :icon="SwitchButton">退出登录</el-dropdown-item>
          </el-dropdown-menu>
        </template>
      </el-dropdown>
    </div>
  </header>
</template>
