import client from './client'
import type { Restaurant } from '@/types'

export const getRestaurant = (id: string) =>
  client.get<Restaurant>(`/api/restaurants/${id}`).then((r) => r.data)

export const submitFeedback = (data: {
  query: string
  restaurant_id?: string
  is_relevant: boolean
  comment?: string
}) => client.post('/api/feedback', data).then((r) => r.data)
