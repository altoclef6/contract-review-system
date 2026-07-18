import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { api, clearStoredSession } from '../api'

export interface User { id: string; email: string; full_name: string; role: 'admin' | 'legal' | 'employee' }

function readStoredUser(): User | null {
  try {
    return JSON.parse(localStorage.getItem('user') || 'null') as User | null
  } catch {
    clearStoredSession()
    return null
  }
}

export const useAuthStore = defineStore('auth', () => {
  const user = ref<User | null>(readStoredUser())
  window.addEventListener('auth:cleared', () => { user.value = null })
  const loggedIn = computed(() => Boolean(user.value && localStorage.getItem('access_token')))
  async function login(email: string, password: string) {
    const { data } = await api.post('/auth/login', { email, password })
    localStorage.setItem('access_token', data.data.access_token)
    localStorage.setItem('refresh_token', data.data.refresh_token)
    localStorage.setItem('user', JSON.stringify(data.data.user))
    user.value = data.data.user
  }
  async function logout() {
    const refreshToken = localStorage.getItem('refresh_token')
    if (refreshToken) {
      try { await api.post('/auth/logout', { refresh_token: refreshToken }) } catch { /* local cleanup still applies */ }
    }
    clearStoredSession()
    user.value = null
  }
  return { user, loggedIn, login, logout }
})
