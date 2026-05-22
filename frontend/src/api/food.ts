import client from './client'
import type { FoodItem, FoodSearchResult } from '@/types'

export const searchFood = (q: string, limit = 10) =>
  client
    .get<FoodSearchResult>('/api/food/search', { params: { q, limit } })
    .then((r) => r.data)

export const confirmFood = (item: FoodItem) =>
  client.post<FoodItem>('/api/food/confirm', { item }).then((r) => r.data)

export const getFood = (id: number) =>
  client.get<FoodItem>(`/api/food/${id}`).then((r) => r.data)
