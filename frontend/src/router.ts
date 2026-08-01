import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from './stores/auth'
import AppLayout from './views/AppLayout.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/login', component: () => import('./views/LoginView.vue'), meta: { title: '用户登录' } },
    {
      path: '/', component: AppLayout, meta: { auth: true }, children: [
        { path: '', redirect: '/dashboard' },
        { path: 'dashboard', component: () => import('./views/DashboardView.vue'), meta: { title: '工作台', section: '业务中心' } },
        { path: 'contracts', component: () => import('./views/ContractsView.vue'), meta: { title: '合同中心', section: '业务中心' } },
        { path: 'contracts/:contractId', component: () => import('./views/ContractDetailView.vue'), meta: { title: '合同详情', section: '合同中心' } },
        { path: 'review', component: () => import('./views/ReviewView.vue'), meta: { title: '智能审查', section: '业务中心' } },
        { path: 'review-tasks', component: () => import('./views/ReviewTasksView.vue'), meta: { title: '审查任务', section: '业务中心' } },
        { path: 'reader/:reviewId', component: () => import('./views/ReaderView.vue'), meta: { title: '合同阅读器', section: '智能审查' } },
        { path: 'risks', component: () => import('./views/RisksView.vue'), meta: { title: '风险台账', section: '业务中心' } },
        { path: 'risks/:riskId', component: () => import('./views/RiskDetailView.vue'), meta: { title: '风险详情', section: '风险台账' } },
        { path: 'reports', component: () => import('./views/ReportCenterView.vue'), meta: { title: '报告中心', section: '业务中心' } },
        { path: 'rules', component: () => import('./views/RuleCenterView.vue'), meta: { title: '规则中心', section: '协同与配置', roles: ['admin', 'legal'] } },
        { path: 'knowledge', component: () => import('./views/KnowledgeCenterView.vue'), meta: { title: '知识库', section: '协同与配置', roles: ['admin', 'legal'] } },
        { path: 'legal-knowledge', component: () => import('./views/LegalKnowledgeView.vue'), meta: { title: '法律知识库', section: '协同与配置', roles: ['admin'] } },
        { path: 'users', component: () => import('./views/UsersView.vue'), meta: { title: '用户与权限', section: '协同与配置', roles: ['admin'] } },
        { path: 'version-compare', component: () => import('./views/VersionCompareView.vue'), meta: { title: '版本对比', section: '合同中心' } },
        { path: 'assistant', redirect: '/dashboard' },
        { path: 'workflows', component: () => import('./views/WorkflowsView.vue'), meta: { title: '审批流程', section: '协同工具' } },
        { path: 'legal-search', component: () => import('./views/LegalSearchView.vue'), meta: { title: '法律检索', section: '协同工具' } },
        { path: 'settings', component: () => import('./views/SettingsView.vue'), meta: { title: '系统设置', section: '系统管理', roles: ['admin'] } },
        { path: 'audit-logs', component: () => import('./views/AuditLogsView.vue'), meta: { title: '操作日志', section: '系统管理', roles: ['admin'] } },
        { path: '403', component: () => import('./views/AccessDeniedView.vue'), meta: { title: '无权访问', section: '系统提示' } },
      ],
    },
    { path: '/:pathMatch(.*)*', component: () => import('./views/NotFoundView.vue'), meta: { title: '页面不存在' } },
  ],
})
router.beforeEach((to) => {
  const auth = useAuthStore()
  if (to.meta.auth && !auth.loggedIn) return '/login'
  const roles = to.meta.roles as string[] | undefined
  if (roles && auth.user && !roles.includes(auth.user.role)) return { path: '/403', query: { from: to.fullPath } }
})
export default router
