import { useEffect, useRef, useState } from 'react'
import { Alert, Button, Empty, Pagination, Select, Spin, Typography } from 'antd'
import { EnvironmentOutlined, ReloadOutlined, RocketOutlined } from '@ant-design/icons'
import { LocationPickerModal } from '@/components/location/LocationPickerModal'
import { fetchCities } from '@/api/cities'
import type { City } from '@/api/cities'
import { PRIMARY_COLOR } from '@/constants'
import { SearchBar } from '@/components/search/SearchBar'
import { FilterBar, FilterState, EMPTY_FILTERS } from '@/components/search/FilterBar'
import { RestaurantGroupCard } from '@/components/restaurant/RestaurantGroupCard'
import { useSearchSync } from '@/hooks/useSearch'
import { useSearchStore } from '@/stores/searchStore'
import { useAuthStore } from '@/stores/authStore'
import { addSearchRecord } from '@/utils/history'
import { loadPrefs, prefsToDietLabels } from '@/utils/prefs'
import { useLang } from '@/i18n/LanguageContext'
import type { DietLabel, Restaurant } from '@/types'

const { Text } = Typography
const CRAWL_REFRESH_DELAY = 10_000

function countMatchingDishes(r: Restaurant, dietLabels: DietLabel[], q: string): number {
  if (!r.menu_items?.length) return 0
  return r.menu_items.filter((item) => {
    const labelMatch = dietLabels.length > 0 && item.diet_labels?.some((d) => dietLabels.includes(d))
    const nameMatch = q.length > 0 && item.name?.toLowerCase().includes(q.toLowerCase())
    return labelMatch || nameMatch
  }).length
}

function LocationRow() {
  const { lat, lng, locationName, setLocation, setLocationName, doSearch } = useSearchStore()
  const { t } = useLang()
  const [cities, setCities] = useState<City[]>([])
  const [selectedCity, setSelectedCity] = useState<string | null>(null)
  const [open, setOpen] = useState(false)

  useEffect(() => {
    fetchCities().then((list) => {
      setCities(list)
      if (list.length > 0 && !selectedCity) {
        const first = list[0]
        setSelectedCity(first.id)
        if (lat === null) {
          setLocation(first.center.lat, first.center.lng)
          setLocationName(first.label)
        }
      }
    }).catch(() => {})
  }, [])

  const handleCityChange = (id: string) => {
    const city = cities.find((c) => c.id === id)
    if (!city) return
    setSelectedCity(id)
    setLocation(city.center.lat, city.center.lng)
    setLocationName(city.label)
    doSearch()
  }

  return (
    <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 10 }}>
      <Select
        value={selectedCity}
        onChange={handleCityChange}
        style={{ width: 120, flexShrink: 0 }}
        size="middle"
        options={cities.map((c) => ({ value: c.id, label: (t.nav_lang_toggle === 'English' ? c.label_zh : null) || c.label }))}
        suffixIcon={<EnvironmentOutlined style={{ fontSize: 12 }} />}
        placeholder="City"
      />
      <button
        onClick={() => setOpen(true)}
        title={locationName}
        style={{
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          width: 36, height: 36, borderRadius: 8, flexShrink: 0,
          border: `1.5px solid ${lat !== null ? PRIMARY_COLOR : '#E8E0D5'}`,
          background: lat !== null ? PRIMARY_COLOR + '10' : '#fff',
          color: lat !== null ? PRIMARY_COLOR : '#6B7A7A',
          cursor: 'pointer', outline: 'none',
        }}
      >
        <EnvironmentOutlined style={{ fontSize: 15 }} />
      </button>
      <LocationPickerModal
        open={open}
        initialLat={lat ?? 22.3193}
        initialLng={lng ?? 114.1694}
        onConfirm={(lat, lng, name) => { setLocation(lat, lng); setLocationName(name); doSearch() }}
        onClose={() => setOpen(false)}
      />
    </div>
  )
}

export default function SearchPage() {
  const { q, dietLabels, priceLevels, sortMode, offset, limit, push } = useSearchSync()

  // Remember last search URL so Discover tab can return here.
  // Only save when there are actual search params to avoid overwriting with a bare '/search'.
  useEffect(() => {
    const search = window.location.search
    if (search) {
      sessionStorage.setItem('lastSearchUrl', '/search' + search)
    }
  }, [q, dietLabels, priceLevels, sortMode])
  const {
    results, total, facets, loading, error,
    spellSuggestion, detectedDietLabels, crawlTriggered,
    doSearch, setLocation, setLocalFilters: setStoreFilters, setSortMode,
  } = useSearchStore()
  const { user } = useAuthStore()
  const { t } = useLang()

  const [countdown, setCountdown] = useState<number | null>(null)
  const countdownRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const lastRecordedRef = useRef('')

  // Local-only filter state (not URL-synced; backend extension needed)
  const [localFilters, setLocalFilters] = useState<Omit<FilterState, 'dietLabels' | 'priceLevels' | 'sortMode'>>({
    calorieRange: null,
    nutritionLabels: [],
    minRating: null,
    maxDistanceKm: null,
    extraDietRestrictions: [],
    allergyRestrictions: [],
    priceRange: null,
  })

  // Apply saved user preferences as default diet labels (only when no URL diet params exist)
  useEffect(() => {
    if (!user) return
    if (new URLSearchParams(window.location.search).has('diet')) return
    const prefs = loadPrefs(user.id)
    const defaultLabels = prefsToDietLabels(prefs) as DietLabel[]
    if (defaultLabels.length > 0) {
      push({ diet: defaultLabels })
    }
  }, [user?.id])


  useEffect(() => {
    if (!crawlTriggered) return
    setCountdown(Math.round(CRAWL_REFRESH_DELAY / 1000))
    countdownRef.current = setInterval(() => {
      setCountdown((prev) => {
        if (prev === null || prev <= 1) {
          clearInterval(countdownRef.current!)
          doSearch()
          return null
        }
        return prev - 1
      })
    }, 1000)
    return () => { if (countdownRef.current) clearInterval(countdownRef.current) }
  }, [crawlTriggered])

  // Record search history when a search completes with a query or diet filters
  useEffect(() => {
    if (loading || (!q && dietLabels.length === 0)) return
    const key = `${q}|${[...dietLabels].sort().join(',')}`
    if (key === lastRecordedRef.current) return
    lastRecordedRef.current = key
    addSearchRecord(
      { id: crypto.randomUUID(), query: q, dietLabels, timestamp: Date.now(), resultCount: total },
      user?.id,
    )
  }, [loading, q, dietLabels])

  // Combined filter state (URL-synced + local)
  const filters: FilterState = { dietLabels, priceLevels, sortMode, ...localFilters }

  const handleFilterChange = (updates: Partial<FilterState>) => {
    const urlPatch: Parameters<typeof push>[0] = {}
    const localPatch: Partial<typeof localFilters> = {}
    const storePatch: Record<string, any> = {}

    for (const [key, value] of Object.entries(updates)) {
      if (key === 'dietLabels') urlPatch.diet = value as DietLabel[]
      else if (key === 'priceLevels') urlPatch.price = value as number[]
      else if (key === 'sortMode') { urlPatch.sort = value as string; setSortMode(value as string) }
      else {
        (localPatch as any)[key] = value
        // Sync backend-relevant local filters to store
        if (key === 'maxDistanceKm') storePatch.radiusKm = (value as number | null) ?? 5.0
        if (key === 'minRating') storePatch.minRating = value
        if (key === 'priceRange') {
          storePatch.minPrice = (value as [number,number] | null)?.[0] ?? null
          storePatch.maxPrice = (value as [number,number] | null)?.[1] ?? null
        }
        if (key === 'calorieRange') {
          storePatch.minCalories = (value as [number,number] | null)?.[0] ?? null
          storePatch.maxCalories = (value as [number,number] | null)?.[1] ?? null
        }
      }
    }

    if (Object.keys(urlPatch).length > 0) push({ ...urlPatch, offset: 0 })
    if (Object.keys(localPatch).length > 0) setLocalFilters(prev => ({ ...prev, ...localPatch }))
    if (Object.keys(storePatch).length > 0) {
      setStoreFilters(storePatch)
      doSearch()
    }
  }

  // Rerank by matching dish count when filters are active
  // Use server-side matched_dishes count when available (ES inner_hits already ranked
  // by dish relevance). Fall back to client-side scoring for diet-only filters.
  const matchCount = (r: Restaurant) =>
    r.matched_dishes?.length ?? countMatchingDishes(r, dietLabels, q)

  const rankedResults =
    dietLabels.length > 0 || q
      ? [...results].sort((a, b) => matchCount(b) - matchCount(a))
      : results

  return (
    <div style={{ background: '#F7F3EE', minHeight: 'calc(100vh - 52px)' }}>
      {/* Sticky search + filter bar */}
      <div
        style={{
          background: '#fff',
          borderBottom: '1px solid #E8E0D5',
          padding: '12px 24px 14px',
          position: 'sticky',
          top: 52,
          zIndex: 90,
          boxShadow: '0 2px 8px rgba(30,42,42,0.04)',
        }}
      >
        <div style={{ maxWidth: 1100, margin: '0 auto' }}>
          {/* Location + search bar row */}
          <LocationRow />
          <div style={{ marginBottom: 10 }}>
            <SearchBar
              value={q}
              onSearch={(val) => push({ q: val, offset: 0 })}
            />
          </div>
          <FilterBar filters={filters} onFilterChange={handleFilterChange} hideLocation />
        </div>
      </div>

      {/* Alerts */}
      {(spellSuggestion || detectedDietLabels.length > 0 || crawlTriggered) && (
        <div style={{ maxWidth: 1100, margin: '0 auto', padding: '12px 24px 0' }}>
          {spellSuggestion && (
            <Alert type="info" showIcon closable
              message={<span>{t.search_did_you_mean} <a onClick={() => push({ q: spellSuggestion, offset: 0 })}><strong>{spellSuggestion}</strong></a>?</span>}
              style={{ marginBottom: 8 }} />
          )}
          {detectedDietLabels.length > 0 && (
            <Alert type="success" showIcon closable
              message={`${t.search_detected_diet} ${detectedDietLabels.join(', ')}`}
              style={{ marginBottom: 8 }} />
          )}
          {crawlTriggered && (
            <Alert type="warning" showIcon icon={<RocketOutlined />} closable
              message={<span>{t.search_fetching_more}{countdown !== null ? `, refreshing in ${countdown}s…` : ''}</span>}
              action={<Button size="small" icon={<ReloadOutlined />} onClick={() => doSearch()}>{t.search_refresh}</Button>}
              style={{ marginBottom: 8 }} />
          )}
        </div>
      )}

      {/* Results */}
      <div style={{ maxWidth: 1100, margin: '0 auto', padding: '16px 24px 32px' }}>
        {!loading && !error && total > 0 && (
          <Text type="secondary" style={{ display: 'block', marginBottom: 12, fontSize: 13 }}>
            {t.search_found(total)}
          </Text>
        )}

        {error && <Alert type="error" message={`Search failed: ${error}`} style={{ marginBottom: 16 }} />}

        <Spin spinning={loading}>
          {rankedResults.length === 0 && !loading ? (
            <Empty
              style={{ marginTop: 48 }}
              description={crawlTriggered ? t.search_crawling : t.search_no_results}
            />
          ) : (
            rankedResults.map((r) => (
              <RestaurantGroupCard
                key={r.restaurant_id}
                restaurant={r}
                activeDietLabels={dietLabels}
                query={q}
                onDietClick={(label) => {
                  if (!dietLabels.includes(label)) push({ diet: [...dietLabels, label], offset: 0 })
                }}
              />
            ))
          )}
        </Spin>

        {total > limit && (
          <div style={{ textAlign: 'center', marginTop: 24 }}>
            <Pagination
              current={Math.floor(offset / limit) + 1}
              pageSize={limit}
              total={total}
              onChange={(page) => push({ offset: (page - 1) * limit })}
              showSizeChanger={false}
            />
          </div>
        )}
      </div>
    </div>
  )
}
