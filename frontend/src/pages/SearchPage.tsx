import { useEffect, useRef, useState } from 'react'
import { Alert, Button, Empty, Pagination, Select, Spin, Tooltip, Typography } from 'antd'
import { AimOutlined, EnvironmentOutlined, ReloadOutlined, RocketOutlined } from '@ant-design/icons'
import { PRIMARY_COLOR } from '@/constants'
import { SearchBar } from '@/components/search/SearchBar'
import { FilterBar, FilterState, EMPTY_FILTERS } from '@/components/search/FilterBar'
import { RestaurantGroupCard } from '@/components/restaurant/RestaurantGroupCard'
import { useSearchSync } from '@/hooks/useSearch'
import { useSearchStore } from '@/stores/searchStore'
import { useSearchParams } from 'react-router-dom'
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
    const nameMatch = q.length > 0 && item.name.toLowerCase().includes(q.toLowerCase())
    return labelMatch || nameMatch
  }).length
}

export default function SearchPage() {
  const { q, dietLabels, priceLevels, sortMode, offset, limit, push } = useSearchSync()
  const {
    results, total, facets, loading, error,
    spellSuggestion, detectedDietLabels, crawlTriggered,
    doSearch, setLocation, clearLocation, setRadiusKm,
  } = useSearchStore()
  const { user } = useAuthStore()

  const [cities, setCities] = useState<City[]>([])
  const [selectedCity, setSelectedCity] = useState<string | null>(null)
  const [locAvailable, setLocAvailable] = useState(true)
  const [locLoading, setLocLoading] = useState(false)
  const [countdown, setCountdown] = useState<number | null>(null)
  const countdownRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const lastRecordedRef = useRef('')

  const [urlParams] = useSearchParams()

  // Local-only filter state — maxDistanceKm 从 URL 初始化，其余本地管理
  const [localFilters, setLocalFilters] = useState<Omit<FilterState, 'dietLabels' | 'priceLevels' | 'sortMode'>>({
    cuisineTypes: [],
    foodTypes: [],
    calorieRange: null,
    nutritionLabels: [],
    minRating: null,
    maxDistanceKm: urlParams.get('radius_km') ? Number(urlParams.get('radius_km')) : null,
    extraDietRestrictions: [],
    allergyRestrictions: [],
    priceRange: null,
  })

  useEffect(() => {
    clearLocation()  // 不继承 HomePage 设置的坐标，避免搜索结果被意外 geo 过滤
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

  // allergyRestrictions 前端值 → 后端 allergens 字段名
  const ALLERGY_TO_ALLERGEN: Record<string, string> = {
    'peanut-free': 'peanut',
    'seafood-free': 'shellfish',
    'soy-free': 'soy',
    'dairy-free': 'dairy',
    'gluten-free': 'gluten',
  }

  // 前端 foodType/cuisine 枚举值 → 后端 cuisine_type 中文字段
  const FOOD_TYPE_TO_ZH: Record<string, string> = {
    fast_food: '快餐', street_food: '小吃', bbq: '烧烤', hotpot: '火锅',
    buffet: '自助餐', noodles: '面食', congee: '粥', dumplings: '饺子',
    korean_bbq: '烤肉',
  }
  const CUISINE_TO_ZH: Record<string, string> = {
    sichuan: '川菜', cantonese: '粤菜', hunan: '湘菜', shandong: '鲁菜',
    jiangsu: '苏菜', zhejiang: '浙菜', fujian: '闽菜', anhui: '徽菜',
  }
  // nutritionLabels → diet_labels
  const NUTRITION_TO_DIET: Record<string, string> = {
    low_fat: 'low-calorie', low_sugar: 'low-calorie',
    low_sodium: 'low-sodium', no_added_oil: 'low-calorie',
  }

  // 把当前所有本地 filters 转成后端参数，可传入增量 patch 覆盖
  const buildLocalOverrides = (
    patch: Partial<typeof localFilters> = {},
    overrideDietLabels?: DietLabel[],
  ) => {
    const next = { ...localFilters, ...patch }
    const base = overrideDietLabels ?? dietLabels
    const cuisineZh = [
      ...next.foodTypes.map((v) => FOOD_TYPE_TO_ZH[v]).filter(Boolean),
      ...next.cuisineTypes.map((v) => CUISINE_TO_ZH[v]).filter(Boolean),
    ]
    const extraDiet = next.nutritionLabels.map((v) => NUTRITION_TO_DIET[v]).filter(Boolean)
    const allergenFree = next.allergyRestrictions
      .map((v) => ALLERGY_TO_ALLERGEN[v])
      .filter(Boolean)
    return {
      ...(cuisineZh.length ? { cuisine_types: cuisineZh } : { cuisine_types: undefined }),
      ...((extraDiet.length || base.length) ? { diet_labels: [...base, ...extraDiet] } : {}),
      ...(allergenFree.length ? { allergen_free_required: allergenFree } : { allergen_free_required: undefined }),
      ...(next.minRating != null ? { min_rating: next.minRating } : { min_rating: undefined }),
      ...(next.maxDistanceKm != null ? { radius_km: next.maxDistanceKm } : {}),
    }
  }

  // useSearchSync 里 doSearch 不知道本地 filters，在这里补上
  // 每次 URL 变化（URL 同步的标签改变）后，重新搜索时合并本地 filters
  const localFiltersRef = useRef(localFilters)
  localFiltersRef.current = localFilters

  useEffect(() => {
    // URL 变化后 useSearchSync 已触发了一次 doSearch，但没带本地 filters
    // 用 setTimeout 0 让 useSearchSync 的 doSearch 先跑，再补一次带本地 filters 的调用
    const id = setTimeout(() => {
      const overrides = buildLocalOverrides({}, undefined)
      const hasLocal = (overrides.cuisine_types?.length ?? 0) > 0
        || (overrides.min_rating != null)
      if (hasLocal) doSearch(overrides)
    }, 0)
    return () => clearTimeout(id)
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [q, dietLabels.join(','), priceLevels.join(','), sortMode])

  const handleFilterChange = (updates: Partial<FilterState>) => {
    const urlPatch: Parameters<typeof push>[0] = {}
    const localPatch: Partial<typeof localFilters> = {}

    for (const [key, value] of Object.entries(updates)) {
      if (key === 'dietLabels') urlPatch.diet = value as DietLabel[]
      else if (key === 'priceLevels') urlPatch.price = value as number[]
      else if (key === 'sortMode') urlPatch.sort = value as string
      else (localPatch as any)[key] = value
    }

    if (Object.keys(urlPatch).length > 0) {
      // URL 变化会触发 useSearchSync → doSearch，上面的 useEffect 会补本地 filters
      push({ ...urlPatch, offset: 0 })
    }
    if (Object.keys(localPatch).length > 0) {
      const next = { ...localFilters, ...localPatch }
      setLocalFilters(next)
      if ('maxDistanceKm' in localPatch) setRadiusKm(localPatch.maxDistanceKm ?? null)
      // 本地 filter 变化立刻触发搜索，传入所有当前本地 filters + patch
      doSearch(buildLocalOverrides(localPatch))
    }
  }

  const handleCityChange = (id: string) => {
    const city = cities.find((c) => c.id === id)
    if (!city) return
    setSelectedCity(id)
    setLocation(city.center.lat, city.center.lng)
    push({ offset: 0 })
  }

  // Rerank by matching dish count when filters are active
  const rankedResults =
    dietLabels.length > 0 || q
      ? [...results].sort(
          (a, b) => countMatchingDishes(b, dietLabels, q) - countMatchingDishes(a, dietLabels, q)
        )
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
              onChange={(val) => push({ q: val })}
              onSearch={(val) => push({ q: val, offset: 0 })}
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

        {/* 有已有结果时不用 Spin 遮罩，避免重新搜索时内容闪黑 */}
        <Spin spinning={loading && rankedResults.length === 0}>
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
