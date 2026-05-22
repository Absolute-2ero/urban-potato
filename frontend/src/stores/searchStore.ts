import { create } from 'zustand'
import { search as apiSearch } from '@/api/search'
import type { DietLabel, Facets, Restaurant, SearchParams } from '@/types'

interface SearchState {
  // 搜索参数（与 URL 同步）
  q: string
  dietLabels: DietLabel[]
  priceLevels: number[]
  sortMode: string
  offset: number
  limit: number

  // 结果
  results: Restaurant[]
  total: number
  facets: Facets | null
  spellSuggestion: string | null
  detectedDietLabels: DietLabel[]
  crawlTriggered: boolean
  loading: boolean
  error: string | null

  // 动作
  setQ: (q: string) => void
  setDietLabels: (labels: DietLabel[]) => void
  setPriceLevels: (levels: number[]) => void
  setSortMode: (mode: string) => void
  setOffset: (offset: number) => void
  doSearch: (params?: Partial<SearchParams>) => Promise<void>
  reset: () => void
}

const defaultFacets: Facets = { diet_labels: {}, price_level: {}, cuisine_type: {} }

export const useSearchStore = create<SearchState>((set, get) => ({
  q: '',
  dietLabels: [],
  priceLevels: [],
  sortMode: 'default',
  offset: 0,
  limit: 20,

  results: [],
  total: 0,
  facets: null,
  spellSuggestion: null,
  detectedDietLabels: [],
  crawlTriggered: false,
  loading: false,
  error: null,

  setQ: (q) => set({ q }),
  setDietLabels: (dietLabels) => set({ dietLabels, offset: 0 }),
  setPriceLevels: (priceLevels) => set({ priceLevels, offset: 0 }),
  setSortMode: (sortMode) => set({ sortMode, offset: 0 }),
  setOffset: (offset) => set({ offset }),

  doSearch: async (overrides = {}) => {
    const { q, dietLabels, priceLevels, sortMode, offset, limit } = get()
    const params: SearchParams = {
      q,
      diet_labels: dietLabels.length ? dietLabels : undefined,
      price_levels: priceLevels.length ? priceLevels : undefined,
      sort_mode: sortMode,
      offset,
      limit,
      ...overrides,
    }
    set({ loading: true, error: null })
    try {
      const resp = await apiSearch(params)
      set({
        results: resp.hits as Restaurant[],
        total: resp.total,
        facets: resp.facets ?? defaultFacets,
        spellSuggestion: resp.spell_suggestion ?? null,
        detectedDietLabels: resp.detected_diet_labels,
        crawlTriggered: resp.crawl_triggered ?? false,
        loading: false,
      })
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err)
      set({ loading: false, error: msg })
    }
  },

  reset: () =>
    set({
      q: '', dietLabels: [], priceLevels: [], sortMode: 'default',
      offset: 0, results: [], total: 0, facets: null,
      spellSuggestion: null, detectedDietLabels: [], crawlTriggered: false,
      loading: false, error: null,
    }),
}))
