import client from './client'
import type { SearchParams, SearchResponse } from '@/types'

export const search = (params: SearchParams) =>
  client.get<SearchResponse>('/api/search', { params }).then((r) => r.data)

export const autocomplete = (prefix: string, city?: string) =>
  client
    .get<string[]>('/api/search/autocomplete', { params: { prefix, ...(city ? { city } : {}) } })
    .then((r) => r.data)

export const triggerCrawl = (q: string, lat?: number, lng?: number) =>
  client
    .post<{ triggered: boolean; message: string }>('/api/search/trigger-crawl', null, {
      params: { q, lat, lng },
    })
    .then((r) => r.data)
