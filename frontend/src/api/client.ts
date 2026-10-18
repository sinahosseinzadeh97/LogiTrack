import axios, { AxiosError, type InternalAxiosRequestConfig } from 'axios'
import { useAuthStore } from '@/stores/authStore'

// Same origin by default: Vite proxies /api and /auth in dev, nginx does in Docker.
const BASE_URL = import.meta.env.VITE_API_URL ?? ''

export const apiClient = axios.create({ baseURL: BASE_URL, timeout: 30_000 })

apiClient.interceptors.request.use((config) => {
  const token = useAuthStore.getState().access_token
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

// One in-flight refresh shared by every request that hit a 401 at the same time.
let refreshing: Promise<string> | null = null

async function refreshAccessToken(): Promise<string> {
  const { refresh_token, setTokens } = useAuthStore.getState()
  if (!refresh_token) throw new Error('No refresh token')
  const { data } = await axios.post(`${BASE_URL}/auth/refresh`, { refresh_token })
  setTokens(data.access_token, data.refresh_token)
  return data.access_token
}

apiClient.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const original = error.config as (InternalAxiosRequestConfig & { _retry?: boolean }) | undefined
    const isAuthCall = original?.url?.startsWith('/auth/')
    if (error.response?.status !== 401 || !original || original._retry || isAuthCall) {
      throw error
    }
    original._retry = true
    try {
      refreshing ??= refreshAccessToken().finally(() => { refreshing = null })
      original.headers.Authorization = `Bearer ${await refreshing}`
      return apiClient(original)
    } catch {
      useAuthStore.getState().clear()
      window.location.assign('/login')
      throw error
    }
  },
)

export function errorMessage(error: unknown): string {
  if (error instanceof AxiosError) {
    const detail = (error.response?.data as { detail?: unknown } | undefined)?.detail
    if (typeof detail === 'string') return detail
    if (error.response?.status === 503) return 'The model has not been trained yet.'
    return error.message
  }
  return 'Something went wrong.'
}

export default apiClient
