import { create } from 'zustand'
import { persist, createJSONStorage } from 'zustand/middleware'
import apiClient from '@/api/client'

export type UserRole = 'viewer' | 'analyst' | 'admin'

export interface AuthUser {
  id: string
  email: string
  full_name: string
  role: UserRole
}

interface AuthState {
  user: AuthUser | null
  access_token: string | null
  refresh_token: string | null
  is_authenticated: boolean
  // Actions
  login: (email: string, password: string) => Promise<void>
  logout: () => void
  setTokens: (access: string, refresh: string) => void
  fetchMe: () => Promise<void>
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      user: null,
      access_token: null,
      refresh_token: null,
      is_authenticated: false,

      login: async (email, password) => {
        const { data } = await apiClient.post('/auth/login', { email, password })
        set({
          access_token: data.access_token,
          refresh_token: data.refresh_token,
          is_authenticated: true,
        })
        await get().fetchMe()
      },

      logout: () => {
        const rt = get().refresh_token
        if (rt) {
          apiClient.post('/auth/logout', { refresh_token: rt }).catch(() => {})
        }
        set({ user: null, access_token: null, refresh_token: null, is_authenticated: false })
      },

      setTokens: (access, refresh) => {
        set({ access_token: access, refresh_token: refresh, is_authenticated: true })
      },

      fetchMe: async () => {
        const { data } = await apiClient.get('/auth/me')
        set({ user: data })
      },
    }),
    {
      name: 'logitrack-auth',
      storage: createJSONStorage(() => sessionStorage),
      partialize: (state) => ({
        user: state.user,
        access_token: state.access_token,
        refresh_token: state.refresh_token,
        is_authenticated: state.is_authenticated,
      }),
    }
  )
)
