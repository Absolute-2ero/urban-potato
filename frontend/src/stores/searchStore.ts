import { create } from 'zustand'
import { search as apiSearch } from '@/api/search'
import type { DietLabel, Facets, Restaurant, SearchParams } from '@/types'

interface SearchState {
  // 搜索参数（与 URL 同步）
  city: string
  q: string
  dietLabels: DietLabel[]
  priceLevels: number[]
  sortMode: string
  offset: number
  limit: number
  lat: number | null
  lng: number | null
  locationName: string
  // local filters passed directly to search (not URL-synced)
  radiusKm: number
  minRating: number | null
  minPrice: number | null
  maxPrice: number | null
  minCalories: number | null
  maxCalories: number | null

  // 结果
  results: Restaurant[]
  total: number
  facets: Facets | null
  spellSuggestion: string | null
  detectedDietLabels: DietLabel[]
  crawlTriggered: boolean
  loading: boolean
  error: string | null

  // 搜索模式
  searchMode: 'smart' | 'semantic'

  // 动作
  setSearchMode: (mode: 'smart' | 'semantic') => void
  setCity: (city: string) => void
  setQ: (q: string) => void
  setDietLabels: (labels: DietLabel[]) => void
  setPriceLevels: (levels: number[]) => void
  setSortMode: (mode: string) => void
  setOffset: (offset: number) => void
  setLocation: (lat: number, lng: number) => void
  setLocationName: (name: string) => void
  setLocalFilters: (f: { radiusKm?: number; minRating?: number | null; minPrice?: number | null; maxPrice?: number | null; minCalories?: number | null; maxCalories?: number | null }) => void
  doSearch: (params?: Partial<SearchParams>) => Promise<void>
  reset: () => void
}

const defaultFacets: Facets = { diet_labels: {}, price_level: {}, cuisine_type: {} }

export const useSearchStore = create<SearchState>((set, get) => ({
  city: 'beijing',
  searchMode: (localStorage.getItem('search_mode') as 'smart' | 'semantic') || 'smart',
  q: '',
  dietLabels: [],
  priceLevels: [],
  sortMode: 'default',
  offset: 0,
  limit: 20,
  lat: null,
  lng: null,
  locationName: '清华大学',
  radiusKm: 30.0,
  minRating: null,
  minPrice: null,
  maxPrice: null,
  minCalories: null,
  maxCalories: null,

  results: [],
  total: 0,
  facets: null,
  spellSuggestion: null,
  detectedDietLabels: [],
  crawlTriggered: false,
  loading: false,
  error: null,

  setSearchMode: (mode) => { localStorage.setItem('search_mode', mode); set({ searchMode: mode }) },
  setCity: (city) => set({ city, offset: 0, results: [], total: 0 }),
  setQ: (q) => set({ q }),
  setDietLabels: (dietLabels) => set({ dietLabels, offset: 0 }),
  setPriceLevels: (priceLevels) => set({ priceLevels, offset: 0 }),
  setSortMode: (sortMode) => set({ sortMode, offset: 0 }),
  setOffset: (offset) => set({ offset }),
  setLocation: (lat, lng) => set({ lat, lng }),
  setLocationName: (locationName) => set({ locationName }),
  setLocalFilters: (f) => set(f as any),

  doSearch: async (overrides = {}) => {
    const { city, q, dietLabels, priceLevels, sortMode, offset, limit, lat, lng,
            radiusKm, minRating, minPrice, maxPrice, minCalories, maxCalories } = get()
    const params: SearchParams = {
      city,
      q,
      diet_labels: dietLabels.length ? dietLabels : undefined,
      price_levels: priceLevels.length ? priceLevels : undefined,
      sort_mode: sortMode,
      offset,
      limit,
      ...(lat != null && lng != null ? { lat, lng, radius_km: radiusKm } : {}),
      ...(minRating != null ? { min_rating: minRating } : {}),
      ...(minPrice != null ? { min_price: minPrice } : {}),
      ...(maxPrice != null ? { max_price: maxPrice } : {}),
      ...(minCalories != null ? { min_calories: minCalories } : {}),
      ...(maxCalories != null ? { max_calories: maxCalories } : {}),
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
      offset: 0, lat: null, lng: null, results: [], total: 0, facets: null,
      spellSuggestion: null, detectedDietLabels: [], crawlTriggered: false,
      loading: false, error: null,
    }),
}))
