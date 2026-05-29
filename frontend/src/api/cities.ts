import client from './client'

export interface City {
  id: string
  label: string
  center: { lat: number; lng: number }
}

export async function fetchCities(): Promise<City[]> {
  const res = await client.get<City[]>('/api/cities')
  return res.data
}
