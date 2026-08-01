<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import {
  DataAnalysis,
  Document,
  Files,
  Reading,
  Setting,
  Tickets,
  User,
} from '@element-plus/icons-vue'

type UserRole = 'admin' | 'legal' | 'employee'

interface NavigationItem {
  label: string
  path?: string
  icon: unknown
  roles?: UserRole[]
  planned?: boolean
}

const props = defineProps<{
  collapsed: boolean
  role: UserRole
}>()

const emit = defineEmits<{ navigate: [] }>()
const route = useRoute()

const primaryItems: NavigationItem[] = [
  { label: '工作台', path: '/dashboard', icon: DataAnalysis },
  { label: '合同管理', path: '/contracts', icon: Files },
  { label: '智能审查', path: '/review', icon: Document },
  { label: '报告中心', path: '/reports', icon: Tickets },
  { label: '法律知识库', path: '/legal-knowledge', icon: Reading, roles: ['admin'] },
  { label: '法律知识库', path: '/legal-search', icon: Reading, roles: ['legal', 'employee'] },
  { label: '团队与权限', path: '/users', icon: User, roles: ['admin'] },
  { label: '系统管理', path: '/settings', icon: Setting, roles: ['admin'] },
]

function visible(items: NavigationItem[]) {
  return items.filter((item) => !item.roles || item.roles.includes(props.role))
}

const visiblePrimary = computed(() => visible(primaryItems))

function isActive(path?: string) {
  return Boolean(path && route.path.startsWith(path))
}
</script>

<template>
  <aside class="app-sidebar" :class="{ 'is-collapsed': collapsed }" aria-label="主导航">
    <router-link class="app-brand" to="/" aria-label="衡契合同审查平台" @click="emit('navigate')">
      <span class="app-brand__mark"><el-icon><Document /></el-icon></span>
      <span v-if="!collapsed" class="app-brand__copy">
        <strong>衡契</strong>
        <small>合同审查与合规管理</small>
      </span>
    </router-link>

    <nav class="app-nav">
      <section>
        <p v-if="!collapsed" class="app-nav__group">核心业务</p>
        <template v-for="item in visiblePrimary" :key="item.label">
          <router-link
            v-if="item.path"
            :to="item.path"
            class="app-nav__item"
            :class="{ 'is-active': isActive(item.path) }"
            :title="collapsed ? item.label : undefined"
            @click="emit('navigate')"
          >
            <el-icon><component :is="item.icon" /></el-icon>
            <span v-if="!collapsed">{{ item.label }}</span>
          </router-link>
          <button
            v-else
            class="app-nav__item is-planned"
            type="button"
            disabled
            :title="collapsed ? `${item.label}（规划中）` : undefined"
          >
            <el-icon><component :is="item.icon" /></el-icon>
            <span v-if="!collapsed">{{ item.label }}</span>
            <small v-if="!collapsed">规划中</small>
          </button>
        </template>
      </section>

    </nav>

    <div class="app-sidebar__footer" :title="collapsed ? 'AI 辅助审查，不构成正式法律意见' : undefined">
      <span class="app-sidebar__shield">审</span>
      <p v-if="!collapsed"><strong>AI 辅助审查</strong><small>重要合同须经专业法务复核</small></p>
    </div>
  </aside>
</template>
