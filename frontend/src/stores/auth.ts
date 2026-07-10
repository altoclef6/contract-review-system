import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { api } from '../api'

export interface User { id: string; email: string; full_name: string; role: 'admin' | 'legal' | 'employee' }

export const useAuthStore = defineStore('auth', () => {
  const user = ref<User | null>(JSON.parse(localStorage.getItem('user') || 'null'))
  const loggedIn = computed(() => Boolean(user.value && localStorage.getItem('access_token')))
  async function login(email: string, password: string) {
    const { data } = await api.post('/auth/login', { email, password })
    localStorage.setItem('access_token', data.data.access_token)
    localStorage.setItem('refresh_token', data.data.refresh_token)
    localStorage.setItem('user', JSON.stringify(data.data.user))
    user.value = data.data.user
  }
  function logout() { localStorage.clear(); user.value = null }
  return { user, loggedIn, login, logout }
})
