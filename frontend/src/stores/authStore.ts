import { create } from 'zustand'
import { getMe, login, logout, register } from '@/api/auth'
import type { User, UserCreate, UserLogin } from '@/types'

interface AuthState {
  user: User | null
  loading: boolean
  init: () => Promise<void>
  login: (data: UserLogin) => Promise<void>
  register: (data: UserCreate) => Promise<void>
  logout: () => Promise<void>
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  loading: true,

  init: async () => {
    try {
      const user = await getMe()
      set({ user, loading: false })
    } catch {
      set({ user: null, loading: false })
    }
  },

  login: async (data) => {
    const user = await login(data)
    set({ user })
  },

  register: async (data) => {
    const user = await register(data)
    set({ user })
  },

  logout: async () => {
    await logout()
    set({ user: null })
  },
}))
