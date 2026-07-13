import axios from 'axios'

export const api = axios.create({ baseURL: '/api/v1', timeout: 120000 })

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const original = error.config
    if (error.response?.status === 401 && !original?._retried) {
      const refreshToken = localStorage.getItem('refresh_token')
      if (refreshToken) {
        original._retried = true
        try {
          const response = await axios.post('/api/v1/auth/refresh', { refresh_token: refreshToken })
          localStorage.setItem('access_token', response.data.data.access_token)
          return api(original)
        } catch {
          localStorage.removeItem('access_token')
          localStorage.removeItem('refresh_token')
          localStorage.removeItem('user')
        }
      }
    }
    return Promise.reject(error)
  },
)
