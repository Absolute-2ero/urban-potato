import { useEffect, useRef, useState } from 'react'
import { Alert, Button, Empty, Pagination, Select, Spin, Tag, Tooltip, Typography } from 'antd'
import { AimOutlined, EnvironmentOutlined, LoadingOutlined, ReloadOutlined, RocketOutlined } from '@ant-design/icons'
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
import { parseQuery } from '@/api/search'
import type { City } from '@/api/cities'
import type { DietLabel, ParsedQuery, Restaurant } from '@/types'

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
  const [parsing, setParsing] = useState(false)
  const [parsedInfo, setParsedInfo] = useState<ParsedQuery | null>(null)

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

  // 智能搜索：query 超过 5 个字时尝试 LLM 解析，提取结构化参数
  const handleSmartSearch = async (rawQuery: string) => {
    const trimmed = rawQuery.trim()
    if (!trimmed) return

    // 短 query 直接搜索，不走 LLM
    if (trimmed.length <= 5) {
      setParsedInfo(null)
      push({ q: trimmed, offset: 0 })
      return
    }

    setParsing(true)
    setParsedInfo(null)

    let parsed: ParsedQuery | null = null
    try {
      parsed = await parseQuery(trimmed)
    } catch {
      // 解析失败，降级为普通搜索
    }
    setParsing(false)

    if (!parsed || !parsed.has_extracted_params) {
      push({ q: trimmed, offset: 0 })
      return
    }

    setParsedInfo(parsed)

    // 更新 local filter 状态
    const nextLocalFilters = {
      ...localFilters,
      cuisineTypes: parsed.cuisine_types,
      maxDistanceKm: parsed.radius_km,
      minRating: parsed.min_rating ?? null,
      allergyRestrictions: parsed.allergen_free_required.map((a) => `${a}-free`),
    }
    setLocalFilters(nextLocalFilters)
    setRadiusKm(parsed.radius_km)

    // 一次性触发包含所有解析参数的搜索
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
    })

    // 更新 URL（供分享/书签，会再触发一次 doSearch，但参数相同）
    push({
      q: parsed.q || trimmed,
      diet: parsed.diet_labels as DietLabel[],
      price: parsed.price_levels,
      sort: parsed.sort_mode,
      offset: 0,
    })
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
              onChange={(val) => { push({ q: val }); setParsedInfo(null) }}
              onSearch={handleSmartSearch}
              loading={parsing}
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
      <div style={{ maxWidth: 1100, margin: '0 auto', padding: '12px 24px 0' }}>
        {/* LLM 解析结果 banner */}
        {parsing && (
          <Alert
            type="info"
            icon={<LoadingOutlined />}
            showIcon
            message="正在理解你的搜索意图…"
            style={{ marginBottom: 8 }}
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
                {parsedInfo.location && <Tag icon={<EnvironmentOutlined />} color="purple">{parsedInfo.location}</Tag>}
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
