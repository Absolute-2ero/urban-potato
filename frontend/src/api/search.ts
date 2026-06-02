import client from './client'
import type { ParsedQuery, SearchParams, SearchResponse } from '@/types'

export const search = (params: SearchParams) =>
  client.get<SearchResponse>('/api/search', { params }).then((r) => r.data)

export const autocomplete = (prefix: string) =>
  client
    .get<string[]>('/api/search/autocomplete', { params: { prefix } })
    .then((r) => r.data)

export const triggerCrawl = (q: string, lat?: number, lng?: number) =>
  client
    .post<{ triggered: boolean; message: string }>('/api/search/trigger-crawl', null, {
      params: { q, lat, lng },
    })
    .then((r) => r.data)

export const parseQuery = (q: string) =>
  client
    .get<ParsedQuery>('/api/search/parse', { params: { q } })
    .then((r) => r.data)
