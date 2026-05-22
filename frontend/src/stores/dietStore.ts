import { create } from 'zustand'
import dayjs from 'dayjs'
import { getProfile, getLogs, updateProfile } from '@/api/diet'
import type { DietLogDay, DietProfile, DietProfileUpdate } from '@/types'

interface DietState {
  profile: DietProfile | null
  logDay: DietLogDay | null
  currentDate: string          // YYYY-MM-DD
  loading: boolean
  loadProfile: () => Promise<void>
  saveProfile: (data: DietProfileUpdate) => Promise<void>
  loadLogs: (date?: string) => Promise<void>
  setCurrentDate: (date: string) => void
}

export const useDietStore = create<DietState>((set, get) => ({
  profile: null,
  logDay: null,
  currentDate: dayjs().format('YYYY-MM-DD'),
  loading: false,

  loadProfile: async () => {
    set({ loading: true })
    try {
      const profile = await getProfile()
      set({ profile, loading: false })
    } catch {
      set({ loading: false })
    }
  },

  saveProfile: async (data) => {
    const profile = await updateProfile(data)
    set({ profile })
  },

  loadLogs: async (date) => {
    const d = date ?? get().currentDate
    set({ loading: true })
    try {
      const logDay = await getLogs(d)
      set({ logDay, loading: false })
    } catch {
      set({ loading: false })
    }
  },

  setCurrentDate: (date) => {
    set({ currentDate: date })
    get().loadLogs(date)
  },
}))
