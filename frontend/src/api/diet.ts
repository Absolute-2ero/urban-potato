import client from './client'
import type { DietLogDay, DietProfile, DietProfileUpdate, FoodLogCreate, FoodLogEntry } from '@/types'

export const getProfile = () =>
  client.get<DietProfile>('/api/diet/profile').then((r) => r.data)

export const updateProfile = (data: DietProfileUpdate) =>
  client.put<DietProfile>('/api/diet/profile', data).then((r) => r.data)

export const getLogs = (log_date: string) =>
  client
    .get<[DietLogDay]>('/api/diet/log', { params: { log_date } })
    .then((r) => r.data[0])

export const addLog = (data: FoodLogCreate) =>
  client.post<FoodLogEntry>('/api/diet/log', data).then((r) => r.data)

export const deleteLog = (id: number) =>
  client.delete(`/api/diet/log/${id}`)

export const getDailyTotals = (log_date: string) =>
  client.get<Record<string, number>>('/api/diet/totals', { params: { log_date } }).then((r) => r.data)

export const getSavedRestaurants = () =>
  client.get<string[]>('/api/diet/saved-restaurants').then((r) => r.data)

export const saveRestaurant = (id: string) =>
  client.post(`/api/diet/saved-restaurants/${id}`)

export const unsaveRestaurant = (id: string) =>
  client.delete(`/api/diet/saved-restaurants/${id}`)

export const exportLogs = (fromDate: string, toDate: string) =>
  client.get('/api/diet/log/export', {
    params: { from_date: fromDate, to_date: toDate },
    responseType: 'blob',
  }).then((r) => r.data as Blob)
