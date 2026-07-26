import axios from 'axios'

export const api = axios.create({ baseURL: '/api/v1', timeout: 120000 })
let refreshInFlight: Promise<string> | null = null
type DesktopRuntime = { apiOrigin: string; startupToken: string }
let desktopRuntime: Promise<DesktopRuntime | null> | null = null

async function getDesktopRuntime(): Promise<DesktopRuntime | null> {
  if (!('__TAURI_INTERNALS__' in window)) return null
  desktopRuntime ??= import('@tauri-apps/api/core')
    .then(({ invoke }) => invoke<DesktopRuntime>('get_runtime_config'))
  return desktopRuntime
}

async function restartDesktopRuntime(): Promise<DesktopRuntime | null> {
  if (!('__TAURI_INTERNALS__' in window)) return null
  const { invoke } = await import('@tauri-apps/api/core')
  const runtime = await invoke<DesktopRuntime>('restart_backend')
  desktopRuntime = Promise.resolve(runtime)
  return runtime
}

export function clearStoredSession(reason?: 'expired') {
  localStorage.removeItem('access_token')
  localStorage.removeItem('refresh_token')
  localStorage.removeItem('user')
  window.dispatchEvent(new CustomEvent('auth:cleared'))
  if (reason === 'expired' && window.location.pathname !== '/login') {
    window.location.assign('/login?reason=session-expired')
  }
}

api.interceptors.request.use(async (config) => {
  const runtime = await getDesktopRuntime()
  if (runtime) {
    config.baseURL = `${runtime.apiOrigin}/api/v1`
    config.headers['X-Desktop-Startup-Token'] = runtime.startupToken
  }
  const token = localStorage.getItem('access_token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const original = error.config
    if (error.code === 'ERR_NETWORK' && original && !original._backendRetried) {
      original._backendRetried = true
      try {
        const runtime = await restartDesktopRuntime()
        if (runtime) {
          original.baseURL = `${runtime.apiOrigin}/api/v1`
          original.headers['X-Desktop-Startup-Token'] = runtime.startupToken
          return api(original)
        }
      } catch {
        // Preserve the original network error for the page-level recovery message.
      }
    }
    if (error.response?.status === 401 && !original?._retried) {
      const refreshToken = localStorage.getItem('refresh_token')
      if (refreshToken) {
        original._retried = true
        try {
          if (!refreshInFlight) {
            refreshInFlight = getDesktopRuntime()
              .then((runtime) => axios.post(
                runtime ? `${runtime.apiOrigin}/api/v1/auth/refresh` : '/api/v1/auth/refresh',
                { refresh_token: refreshToken },
                runtime ? { headers: { 'X-Desktop-Startup-Token': runtime.startupToken } } : {},
              ))
              .then((response) => {
                localStorage.setItem('access_token', response.data.data.access_token)
                localStorage.setItem('refresh_token', response.data.data.refresh_token)
                return response.data.data.access_token as string
              })
              .finally(() => {
                refreshInFlight = null
              })
          }
          const accessToken = await refreshInFlight
          original.headers.Authorization = `Bearer ${accessToken}`
          return api(original)
        } catch {
          clearStoredSession('expired')
        }
      } else {
        clearStoredSession('expired')
      }
    }
    return Promise.reject(error)
  },
)
