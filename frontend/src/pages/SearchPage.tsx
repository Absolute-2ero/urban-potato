import { useEffect, useRef, useState } from 'react'
import { Alert, Button, Empty, Pagination, Select, Spin, Tooltip, Typography } from 'antd'
import { AimOutlined, EnvironmentOutlined, ReloadOutlined, RocketOutlined } from '@ant-design/icons'
import { PRIMARY_COLOR } from '@/constants'
import { SearchBar } from '@/components/search/SearchBar'
import { FilterBar, FilterState, EMPTY_FILTERS } from '@/components/search/FilterBar'
import { RestaurantGroupCard } from '@/components/restaurant/RestaurantGroupCard'
import { useSearchSync } from '@/hooks/useSearch'
import { useSearchStore } from '@/stores/searchStore'
import { useAuthStore } from '@/stores/authStore'
import { addSearchRecord } from '@/utils/history'
import { fetchCities } from '@/api/cities'
import type { City } from '@/api/cities'
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
    doSearch, setLocation,
  } = useSearchStore()
  const { user } = useAuthStore()

  const [cities, setCities] = useState<City[]>([])
  const [selectedCity, setSelectedCity] = useState<string | null>(null)
  const [locAvailable, setLocAvailable] = useState(true)
  const [locLoading, setLocLoading] = useState(false)
  const [countdown, setCountdown] = useState<number | null>(null)
  const countdownRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const lastRecordedRef = useRef('')

  // Local-only filter state (not URL-synced; backend extension needed)
  const [localFilters, setLocalFilters] = useState<Omit<FilterState, 'dietLabels' | 'priceLevels' | 'sortMode'>>({
    cuisineTypes: [],
    foodTypes: [],
    calorieRange: null,
    nutritionLabels: [],
    minRating: null,
    maxDistanceKm: null,
    extraDietRestrictions: [],
    allergyRestrictions: [],
    priceRange: null,
  })

  useEffect(() => {
    setLocAvailable('geolocation' in navigator)
    fetchCities()
      .then((list) => {
        setCities(list)
        if (list.length > 0 && !selectedCity) {
          setSelectedCity(list[0].id)
          setLocation(list[0].center.lat, list[0].center.lng)
        }
      })
      .catch(() => {})
  }, [])

  const handleGetLocation = () => {
    if (!locAvailable) return
    setLocLoading(true)
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setLocation(pos.coords.latitude, pos.coords.longitude)
        setLocLoading(false)
        doSearch()
      },
      () => { setLocLoading(false); setLocAvailable(false) },
      { timeout: 8000 }
    )
  }

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

    for (const [key, value] of Object.entries(updates)) {
      if (key === 'dietLabels') urlPatch.diet = value as DietLabel[]
      else if (key === 'priceLevels') urlPatch.price = value as number[]
      else if (key === 'sortMode') urlPatch.sort = value as string
      else (localPatch as any)[key] = value
    }

    if (Object.keys(urlPatch).length > 0) push({ ...urlPatch, offset: 0 })
    if (Object.keys(localPatch).length > 0) setLocalFilters((prev) => ({ ...prev, ...localPatch }))
  }

  const handleCityChange = (id: string) => {
    const city = cities.find((c) => c.id === id)
    if (!city) return
    setSelectedCity(id)
    setLocation(city.center.lat, city.center.lng)
    push({ offset: 0 })
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
          {/* Location row — above search bar */}
          <div style={{ display: 'flex', gap: 6, alignItems: 'center', marginBottom: 8 }}>
            <Select
              value={selectedCity}
              onChange={handleCityChange}
              style={{ width: 96 }}
              size="middle"
              options={cities.map((c) => ({ value: c.id, label: c.label }))}
              suffixIcon={<EnvironmentOutlined style={{ fontSize: 12 }} />}
              placeholder="City"
            />
            <Tooltip
              title={
                locAvailable
                  ? 'Use my current location'
                  : 'Location access denied — check browser settings'
              }
            >
              <Button
                icon={<AimOutlined />}
                size="middle"
                onClick={handleGetLocation}
                loading={locLoading}
                disabled={!locAvailable}
                style={{
                  borderColor: locAvailable ? PRIMARY_COLOR : '#E8E0D5',
                  color: locAvailable ? PRIMARY_COLOR : '#C0BDB8',
                  fontWeight: 400,
                }}
              >
                Near me
              </Button>
            </Tooltip>
          </div>
          {/* Search bar */}
          <div style={{ marginBottom: 10 }}>
            <SearchBar
              value={q}
              onSearch={(val) => push({ q: val, offset: 0 })}
              city={selectedCity ?? undefined}
            />
          </div>
          {/* 6 filter groups (no location) */}
          <FilterBar
            cities={cities}
            selectedCity={selectedCity}
            onCityChange={handleCityChange}
            locAvailable={locAvailable}
            locLoading={locLoading}
            onGetLocation={handleGetLocation}
            filters={filters}
            onFilterChange={handleFilterChange}
            hideLocation
          />
        </div>
      </div>

      {/* Alerts */}
      {(spellSuggestion || detectedDietLabels.length > 0 || crawlTriggered) && (
        <div style={{ maxWidth: 1100, margin: '0 auto', padding: '12px 24px 0' }}>
          {spellSuggestion && (
            <Alert type="info" showIcon closable
              message={<span>Did you mean: <a onClick={() => push({ q: spellSuggestion, offset: 0 })}><strong>{spellSuggestion}</strong></a>?</span>}
              style={{ marginBottom: 8 }} />
          )}
          {detectedDietLabels.length > 0 && (
            <Alert type="success" showIcon closable
              message={`Detected dietary preferences: ${detectedDietLabels.join(', ')}`}
              style={{ marginBottom: 8 }} />
          )}
          {crawlTriggered && (
            <Alert type="warning" showIcon icon={<RocketOutlined />} closable
              message={<span>Fetching more results from the web{countdown !== null ? `, refreshing in ${countdown}s…` : ''}</span>}
              action={<Button size="small" icon={<ReloadOutlined />} onClick={() => doSearch()}>Refresh</Button>}
              style={{ marginBottom: 8 }} />
          )}
        </div>
      )}

      {/* Results */}
      <div style={{ maxWidth: 1100, margin: '0 auto', padding: '16px 24px 32px' }}>
        {!loading && !error && total > 0 && (
          <Text type="secondary" style={{ display: 'block', marginBottom: 12, fontSize: 13 }}>
            {total} restaurant{total !== 1 ? 's' : ''} found
            {(dietLabels.length > 0 || q) && ' · sorted by dish matches'}
          </Text>
        )}

        {error && <Alert type="error" message={`Search failed: ${error}`} style={{ marginBottom: 16 }} />}

        <Spin spinning={loading}>
          {rankedResults.length === 0 && !loading ? (
            <Empty
              style={{ marginTop: 48 }}
              description={
                crawlTriggered
                  ? 'Fetching data from the web, please wait…'
                  : 'No restaurants matched — try adjusting your filters'
              }
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
