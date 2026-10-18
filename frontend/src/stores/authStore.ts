import { create } from 'zustand'
import { persist, createJSONStorage } from 'zustand/middleware'
import apiClient from '@/api/client'

export type UserRole = 'viewer' | 'analyst' | 'admin'

const ROLE_RANK: Record<UserRole, number> = { viewer: 0, analyst: 1, admin: 2 }

export interface AuthUser {
  id: number
  email: string
  full_name: string
  role: UserRole
}

interface AuthState {
  user: AuthUser | null
  access_token: string | null
  refresh_token: string | null
  login: (email: string, password: string) => Promise<void>
  logout: () => void
  clear: () => void
  setTokens: (access: string, refresh: string) => void
}

// sessionStorage: tokens survive a reload but not closing the tab.
export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      user: null,
      access_token: null,
      refresh_token: null,

      login: async (email, password) => {
        const { data } = await apiClient.post('/auth/login', { email, password })
        set({ access_token: data.access_token, refresh_token: data.refresh_token })
        const { data: user } = await apiClient.get<AuthUser>('/auth/me')
        set({ user })
      },

      logout: () => {
        const refresh_token = get().refresh_token
        if (refresh_token) apiClient.post('/auth/logout', { refresh_token }).catch(() => undefined)
        get().clear()
      },

      clear: () => set({ user: null, access_token: null, refresh_token: null }),

      setTokens: (access_token, refresh_token) => set({ access_token, refresh_token }),
    }),
    { name: 'logitrack-auth', storage: createJSONStorage(() => sessionStorage) },
  ),
)

export const isAuthenticated = (): boolean => !!useAuthStore.getState().access_token

export function hasRole(user: AuthUser | null, minimum: UserRole): boolean {
  return !!user && ROLE_RANK[user.role] >= ROLE_RANK[minimum]
}
