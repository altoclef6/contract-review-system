<script setup lang="ts">
import AppHeader from './AppHeader.vue'
import AppSidebar from './AppSidebar.vue'

type UserRole = 'admin' | 'legal' | 'employee'

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
  profile: []
  navigate: []
}>()
</script>

<template>
  <div class="app-shell" :class="{ 'is-collapsed': collapsed }">
    <AppSidebar :collapsed="collapsed" :role="role" @navigate="emit('navigate')" />
    <div v-if="!collapsed" class="sidebar-backdrop" aria-hidden="true" @click="emit('toggle')"></div>
    <section class="app-workspace">
      <AppHeader
        :collapsed="collapsed"
        :page-title="pageTitle"
        :breadcrumb="breadcrumb"
        :unread="unread"
        :user-name="userName"
        :role="role"
        :api-docs-url="apiDocsUrl"
        @toggle="emit('toggle')"
        @logout="emit('logout')"
        @change-password="emit('changePassword')"
        @profile="emit('profile')"
      />
      <main class="app-main"><slot /></main>
    </section>
  </div>
</template>
