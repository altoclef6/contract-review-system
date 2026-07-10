import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from './stores/auth'
import AppLayout from './views/AppLayout.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/login', component: () => import('./views/LoginView.vue') },
    {
      path: '/', component: AppLayout, meta: { auth: true }, children: [
        { path: '', redirect: '/dashboard' },
        { path: 'dashboard', component: () => import('./views/DashboardView.vue') },
        { path: 'contracts', component: () => import('./views/ContractsView.vue') },
        { path: 'review', component: () => import('./views/ReviewView.vue') },
        { path: 'reader/:reviewId', component: () => import('./views/ReaderView.vue') },
        { path: 'assistant', component: () => import('./views/AssistantView.vue') },
        { path: 'workflows', component: () => import('./views/WorkflowsView.vue') },
        { path: 'settings', component: () => import('./views/SettingsView.vue'), meta: { roles: ['admin', 'legal'] } },
      ],
    },
  ],
})
router.beforeEach((to) => {
  const auth = useAuthStore()
  if (to.meta.auth && !auth.loggedIn) return '/login'
  const roles = to.meta.roles as string[] | undefined
  if (roles && auth.user && !roles.includes(auth.user.role)) return '/dashboard'
})
export default router
