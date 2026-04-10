import axios, { AxiosError, InternalAxiosRequestConfig } from 'axios'
import { useAuthStore } from '@/stores/authStore'

const BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

export const apiClient = axios.create({
  baseURL: BASE_URL,
  headers: { 'Content-Type': 'application/json' },
  timeout: 30_000,
})

// ── Request interceptor: attach Bearer token ──────────────────────────
apiClient.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    const token = useAuthStore.getState().access_token
    if (token) config.headers.Authorization = `Bearer ${token}`
    if (import.meta.env.DEV) {
      ;(config as any)._startTime = Date.now()
    }
    return config
  },
  (err) => Promise.reject(err)
)

// ── Response interceptor: refresh on 401 ─────────────────────────────
let isRefreshing = false
let pendingQueue: Array<{ resolve: (v: string) => void; reject: (e: unknown) => void }> = []

const processQueue = (err: unknown, token: string | null) => {
  pendingQueue.forEach((p) => (err ? p.reject(err) : p.resolve(token!)))
  pendingQueue = []
}

apiClient.interceptors.response.use(
  (response) => {
    if (import.meta.env.DEV && (response.config as any)._startTime) {
      const ms = Date.now() - (response.config as any)._startTime
      console.debug(`[API] ${response.config.method?.toUpperCase()} ${response.config.url} → ${response.status} (${ms}ms)`)
    }
    return response
  },
  async (error: AxiosError) => {
    const original = error.config as InternalAxiosRequestConfig & { _retry?: boolean }
    if (error.response?.status === 401 && !original._retry) {
      original._retry = true
      const { refresh_token, logout, setTokens } = useAuthStore.getState()

      if (!refresh_token) {
        logout()
        window.location.href = '/login'
        return Promise.reject(error)
      }

      if (isRefreshing) {
        return new Promise<string>((resolve, reject) => {
          pendingQueue.push({ resolve, reject })
        }).then((token) => {
          original.headers.Authorization = `Bearer ${token}`
          return apiClient(original)
        })
      }

      isRefreshing = true
      try {
        const { data } = await axios.post(`${BASE_URL}/auth/refresh`, {
          refresh_token,
        })
        setTokens(data.access_token, data.refresh_token)
        processQueue(null, data.access_token)
        original.headers.Authorization = `Bearer ${data.access_token}`
        return apiClient(original)
      } catch (refreshErr) {
        processQueue(refreshErr, null)
        logout()
        window.location.href = '/login'
        return Promise.reject(refreshErr)
      } finally {
        isRefreshing = false
      }
    }
    return Promise.reject(error)
  }
)

export default apiClient
