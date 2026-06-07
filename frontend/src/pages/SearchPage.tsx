import { useEffect, useRef, useState } from 'react'
import { Alert, Button, Empty, Pagination, Select, Spin, Tag, Typography } from 'antd'
import { EnvironmentOutlined, LoadingOutlined } from '@ant-design/icons'
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
import { parseQuery } from '@/api/search'
import type { DietLabel, ParsedQuery, Restaurant } from '@/types'

const { Text } = Typography

function countMatchingDishes(r: Restaurant, dietLabels: DietLabel[], q: string): number {
  if (!r.menu_items?.length) return 0
  return r.menu_items.filter((item) => {
    const labelMatch = dietLabels.length > 0 && item.diet_labels?.some((d) => dietLabels.includes(d))
    const nameMatch = q.length > 0 && item.name?.toLowerCase().includes(q.toLowerCase())
    return labelMatch || nameMatch
  }).length
}

function LocationRow() {
  const { lat, lng, locationName, setLocation, setLocationName, setCity, doSearch, city: storeCity } = useSearchStore()
  const { t } = useLang()
  const [cities, setCities] = useState<City[]>([])
  const [selectedCity, setSelectedCity] = useState<string | null>(storeCity || null)
  const [open, setOpen] = useState(false)

  useEffect(() => {
    fetchCities().then((list) => {
      setCities(list)
      if (list.length === 0) return
      const activeId = storeCity || list[0].id
      const active = list.find((c) => c.id === activeId) ?? list[0]
      setSelectedCity(active.id)
      setCity(active.id)
      if (lat === null) {
        setLocation(active.center.lat, active.center.lng)
        setLocationName(active.label)
      }
    }).catch(() => {})
  }, [])

  const handleCityChange = (id: string) => {
    const city = cities.find((c) => c.id === id)
    if (!city) return
    setSelectedCity(id)
    setCity(id)
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
        initialLat={lat ?? 40.0038}
        initialLng={lng ?? 116.3225}
        onConfirm={(lat, lng, name) => { setLocation(lat, lng); setLocationName(name); doSearch() }}
        onClose={() => setOpen(false)}
      />
    </div>
  )
}

export default function SearchPage() {
  const { q, dietLabels, priceLevels, sortMode, offset, limit, push } = useSearchSync()

  useEffect(() => {
    const search = window.location.search
    if (search) sessionStorage.setItem('lastSearchUrl', '/search' + search)
  }, [q, dietLabels, priceLevels, sortMode])

  const {
    results, total, facets, loading, error,
    spellSuggestion, detectedDietLabels, crawlTriggered,
    doSearch, setLocation, setLocationName, setLocalFilters: setStoreFilters, setSortMode,
    city: currentCity, searchMode, setSearchMode,
  } = useSearchStore()
  const { user } = useAuthStore()
  const { t } = useLang()

  const lastRecordedRef = useRef('')

  // LLM query parsing state
  const [parsing, setParsing] = useState(false)
  const [parsedInfo, setParsedInfo] = useState<ParsedQuery | null>(null)

  const [localFilters, setLocalFilters] = useState<Omit<FilterState, 'dietLabels' | 'priceLevels' | 'sortMode'>>({
    calorieRange: null,
    nutritionLabels: [],
    minRating: null,
    maxDistanceKm: null,
    extraDietRestrictions: [],
    allergyRestrictions: [],
    priceRange: null,
  })

  useEffect(() => {
    if (!user) return
    if (new URLSearchParams(window.location.search).has('diet')) return
    const prefs = loadPrefs(user.id)
    const defaultLabels = prefsToDietLabels(prefs) as DietLabel[]
    if (defaultLabels.length > 0) push({ diet: defaultLabels })
  }, [user?.id])

  useEffect(() => {
    if (loading || (!q && dietLabels.length === 0)) return
    const key = `${q}|${[...dietLabels].sort().join(',')}`
    if (key === lastRecordedRef.current) return
    lastRecordedRef.current = key
    addSearchRecord(
      { id: (crypto.randomUUID?.() ?? Math.random().toString(36).slice(2)), query: q, dietLabels, timestamp: Date.now(), resultCount: total },
      user?.id,
    )
  }, [loading, q, dietLabels])

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
    if (Object.keys(storePatch).length > 0) { setStoreFilters(storePatch); doSearch() }
  }

  const handleSmartSearch = async (rawQuery: string) => {
    const trimmed = rawQuery.trim()
    if (!trimmed) return

    // ── Semantic mode: put semantic=true in URL → useSearchSync handles search ─
    if (searchMode === 'semantic') {
      setParsedInfo(null)
      push({ q: trimmed, semantic: true, offset: 0 })
      return
    }

    // ── Smart mode: LLM extraction ───────────────────────────────────────────
    if (trimmed.length <= 5) {
      setParsedInfo(null)
      push({ q: trimmed, offset: 0 })
      return
    }

    setParsing(true)
    setParsedInfo(null)

    let parsed: ParsedQuery | null = null
    try { parsed = await parseQuery(trimmed, currentCity ?? undefined) } catch { /* fallback */ }
    setParsing(false)

    if (!parsed || !parsed.has_extracted_params) {
      push({ q: trimmed, offset: 0 })
      return
    }

    setParsedInfo(parsed)

    if (parsed.location_lat != null && parsed.location_lng != null) {
      setLocation(parsed.location_lat, parsed.location_lng)
      if (parsed.location) setLocationName(parsed.location)
    }

    const nextLocalFilters = {
      ...localFilters,
      maxDistanceKm: parsed.radius_km,
      minRating: parsed.min_rating ?? null,
      allergyRestrictions: parsed.allergen_free_required.map((a) => `${a}-free`),
    }
    setLocalFilters(nextLocalFilters)
    setStoreFilters({
      radiusKm: parsed.radius_km ?? 5.0,
      minRating: parsed.min_rating ?? null,
    })

    doSearch({
      q: parsed.q || trimmed,
      diet_labels: parsed.diet_labels.length ? parsed.diet_labels : undefined,
      price_levels: parsed.price_levels.length ? parsed.price_levels : undefined,
      sort_mode: parsed.sort_mode,
      offset: 0,
      ...(parsed.cuisine_types.length ? { cuisine_types: parsed.cuisine_types } : {}),
      ...(parsed.min_rating != null ? { min_rating: parsed.min_rating } : {}),
      ...(parsed.radius_km != null ? { radius_km: parsed.radius_km } : {}),
      ...(parsed.allergen_free_required.length ? { allergen_free_required: parsed.allergen_free_required } : {}),
      ...(parsed.location_lat != null && parsed.location_lng != null
        ? { lat: parsed.location_lat, lng: parsed.location_lng }
        : {}),
    })

    push({
      q: parsed.q || trimmed,
      diet: parsed.diet_labels as DietLabel[],
      price: parsed.price_levels,
      sort: parsed.sort_mode,
      semantic: false,
      offset: 0,
    })
  }

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
          <LocationRow />
          <div style={{ marginBottom: 10 }}>
            <SearchBar
              value={q}
              onChange={() => { setParsedInfo(null) }}
              onSearch={handleSmartSearch}
              loading={parsing}
              searchMode={searchMode}
              onSearchModeChange={(mode) => {
                setSearchMode(mode)
                if (mode === 'smart') push({ semantic: false })
              }}
            />
          </div>
          <FilterBar filters={filters} onFilterChange={handleFilterChange} hideLocation />
        </div>
      </div>

      {/* Alerts */}
      <div style={{ maxWidth: 1100, margin: '0 auto', padding: '12px 24px 0' }}>
        {parsing && (
          <Alert
            type="info"
            icon={<LoadingOutlined />}
            showIcon
            message={searchMode === 'semantic' ? 'Semantic search…' : '正在理解你的搜索意图…'}
            style={{ marginBottom: 8 }}
          />
        )}
        {!parsing && searchMode === 'semantic' && q && (
          <Alert
            type="info"
            showIcon
            closable
            style={{ marginBottom: 8 }}
            message={<span style={{ fontSize: 13 }}>✨ <strong>Semantic</strong> — results ranked by meaning similarity to "{q}"</span>}
          />
        )}
        {!parsing && parsedInfo?.has_extracted_params && (
          <Alert
            type="success"
            showIcon
            closable
            onClose={() => setParsedInfo(null)}
            style={{ marginBottom: 8 }}
            message={
              <span style={{ display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
                <span style={{ color: '#555', marginRight: 4 }}>已理解：</span>
                {parsedInfo.q && <Tag color="blue">"{parsedInfo.q}"</Tag>}
                {parsedInfo.location && (
                  <Tag
                    icon={<EnvironmentOutlined />}
                    color={parsedInfo.location_lat != null ? 'purple' : 'default'}
                    title={parsedInfo.location_lat != null ? `${parsedInfo.location_lat.toFixed(4)}, ${parsedInfo.location_lng?.toFixed(4)}` : '位置未能定位'}
                  >
                    {parsedInfo.location}{parsedInfo.location_lat != null ? ' 📍' : ' ⚠️'}
                  </Tag>
                )}
                {parsedInfo.radius_km != null && <Tag color="cyan">{parsedInfo.radius_km < 1 ? `${parsedInfo.radius_km * 1000}m` : `${parsedInfo.radius_km}km`} 内</Tag>}
                {parsedInfo.cuisine_types.map((c) => <Tag key={c} color="orange">{c}</Tag>)}
                {parsedInfo.diet_labels.map((d) => <Tag key={d} color="green">{d}</Tag>)}
                {parsedInfo.allergen_free_required.map((a) => <Tag key={a} color="red">无{a}</Tag>)}
                {parsedInfo.price_levels.length > 0 && <Tag color="gold">{'¥'.repeat(Math.min(...parsedInfo.price_levels))}</Tag>}
                {parsedInfo.min_rating != null && <Tag color="volcano">⭐ ≥{parsedInfo.min_rating}</Tag>}
                {parsedInfo.sort_mode === 'distance' && <Tag>按距离</Tag>}
                {parsedInfo.sort_mode === 'rating' && <Tag>按评分</Tag>}
              </span>
            }
          />
        )}
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
      </div>

      {/* Results */}
      <div style={{ maxWidth: 1100, margin: '0 auto', padding: '16px 24px 32px' }}>
        {!loading && !error && total > 0 && (
          <Text type="secondary" style={{ display: 'block', marginBottom: 12, fontSize: 13 }}>
            {t.search_found(total)}
          </Text>
        )}

        {error && <Alert type="error" message={`Search failed: ${error}`} style={{ marginBottom: 16 }} />}

        {/* 有已有结果时不用 Spin 遮罩，避免重新搜索时内容闪黑 */}
        <Spin spinning={loading && rankedResults.length === 0}>
          {rankedResults.length === 0 && !loading ? (
            <Empty style={{ marginTop: 48 }} description={t.search_no_results} />
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
