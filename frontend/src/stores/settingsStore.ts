import { create } from 'zustand'
import { persist, createJSONStorage } from 'zustand/middleware'

type Theme = 'dark' | 'light'

interface SettingsState {
  theme: Theme
  sidebarCollapsed: boolean
  alertRefreshInterval: number // seconds
  setTheme: (t: Theme) => void
  toggleSidebar: () => void
  setAlertRefreshInterval: (s: number) => void
}

export const useSettingsStore = create<SettingsState>()(
  persist(
    (set) => ({
      theme: 'dark',
      sidebarCollapsed: false,
      alertRefreshInterval: 30,
      setTheme: (theme) => set({ theme }),
      toggleSidebar: () => set((s) => ({ sidebarCollapsed: !s.sidebarCollapsed })),
      setAlertRefreshInterval: (alertRefreshInterval) => set({ alertRefreshInterval }),
    }),
    {
      name: 'logitrack-settings',
      storage: createJSONStorage(() => localStorage),
    }
  )
)
