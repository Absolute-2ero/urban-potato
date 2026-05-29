import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Button, Select, Tooltip, Typography, message } from 'antd'
import { AimOutlined, EnvironmentOutlined } from '@ant-design/icons'
import { SearchBar } from '@/components/search/SearchBar'
import { FilterBar, FilterState, EMPTY_FILTERS } from '@/components/search/FilterBar'
import { fetchCities } from '@/api/cities'
import { useSearchStore } from '@/stores/searchStore'
import { useAuthStore } from '@/stores/authStore'
import { loadPrefs } from '@/utils/prefs'
import { PRIMARY_COLOR } from '@/constants'
import type { City } from '@/api/cities'
import type { DietLabel } from '@/types'

const { Title, Text } = Typography

const FALLBACK_CITY: City = {
  id: 'hongkong',
  label: 'Hong Kong',
  center: { lat: 22.3193, lng: 114.1694 },
}


export default function HomePage() {
  const navigate = useNavigate()
  const { setLocation } = useSearchStore()
  const { user } = useAuthStore()
  const [q, setQ] = useState('')
  const [cities, setCities] = useState<City[]>([FALLBACK_CITY])
  const [selectedCity, setSelectedCity] = useState<string>(FALLBACK_CITY.id)
  const [locLoading, setLocLoading] = useState(false)
  const [locAvailable, setLocAvailable] = useState(true)
  const [filters, setFilters] = useState<FilterState>(EMPTY_FILTERS)
  const [prefsSet, setPrefsSet] = useState(false)

  const handleFilterChange = (updates: Partial<FilterState>) => {
    setFilters((prev) => ({ ...prev, ...updates }))
  }

  // Apply saved preferences as default filters whenever the logged-in user changes
  useEffect(() => {
    if (!user) { setPrefsSet(false); return }
    const prefs = loadPrefs(user.id)
    const hasAny = prefs.nutritionLabels.length > 0 || prefs.dietLabels.length > 0 || prefs.allergyRestrictions.length > 0
    setPrefsSet(hasAny)
    if (hasAny) {
      setFilters((prev) => ({
        ...prev,
        dietLabels: prefs.dietLabels as DietLabel[],
        nutritionLabels: prefs.nutritionLabels,
        allergyRestrictions: prefs.allergyRestrictions,
      }))
    }
  }, [user?.id])

  useEffect(() => {
    setLocation(FALLBACK_CITY.center.lat, FALLBACK_CITY.center.lng)
    setLocAvailable('geolocation' in navigator)
    fetchCities()
      .then((list) => {
        if (list.length > 0) {
          setCities(list)
          setSelectedCity(list[0].id)
          setLocation(list[0].center.lat, list[0].center.lng)
        }
      })
      .catch(() => {})
  }, [])

  const handleCityChange = (id: string) => {
    const city = cities.find((c) => c.id === id)
    if (city) { setSelectedCity(id); setLocation(city.center.lat, city.center.lng) }
  }

  const handleGetLocation = () => {
    if (!locAvailable) return
    setLocLoading(true)
    navigator.geolocation.getCurrentPosition(
      (pos) => { setLocation(pos.coords.latitude, pos.coords.longitude); setLocLoading(false); message.success('Using your current location') },
      () => { setLocLoading(false); setLocAvailable(false); message.warning('Location access denied — using city centre') },
      { timeout: 8000 }
    )
  }

  const goSearch = (query: string) => {
    const params = new URLSearchParams()
    if (query) params.set('q', query)
    filters.dietLabels.forEach((d) => params.append('diet', d))
    filters.priceLevels.forEach((p) => params.append('price', String(p)))
    if (filters.sortMode !== 'default') params.set('sort', filters.sortMode)
    navigate(`/search?${params.toString()}`)
  }

  return (
    <div style={{ background: '#F7F3EE', minHeight: 'calc(100vh - 52px)' }}>
      {/* Hero */}
      <div
        style={{
          background: 'linear-gradient(150deg, #edfff4 0%, #F7F3EE 65%)',
          padding: '48px 24px 32px',
          textAlign: 'center',
        }}
      >
        <div style={{ fontSize: 52, marginBottom: 8 }}>🥗</div>
        <Title
          level={1}
          style={{ margin: '0 0 6px', color: PRIMARY_COLOR, fontSize: 38, fontWeight: 800, letterSpacing: -1 }}
        >
          MacroBite
        </Title>
        <Text style={{ fontSize: 17, color: '#6B7A7A', display: 'block', marginBottom: 32 }}>
          Find the right macros for every bite
        </Text>

        <div style={{ maxWidth: 680, margin: '0 auto' }}>
          {/* Location row — above search bar */}
          <div style={{ display: 'flex', gap: 6, alignItems: 'center', marginBottom: 10 }}>
            <Select
              value={selectedCity}
              onChange={handleCityChange}
              style={{ width: 96 }}
              size="middle"
              options={cities.map((c) => ({ value: c.id, label: c.label }))}
              suffixIcon={<EnvironmentOutlined style={{ fontSize: 12 }} />}
            />
            <Tooltip title={locAvailable ? 'Use my current location' : 'Location access unavailable'}>
              <Button
                icon={<AimOutlined />}
                size="middle"
                onClick={handleGetLocation}
                loading={locLoading}
                disabled={!locAvailable}
                style={{
                  borderColor: locAvailable ? PRIMARY_COLOR : '#E8E0D5',
                  color: locAvailable ? PRIMARY_COLOR : '#C0BDB8',
                }}
              >
                Near me
              </Button>
            </Tooltip>
          </div>

          {/* Search bar */}
          <div style={{ marginBottom: 12 }}>
            <SearchBar
              value={q}
              onChange={setQ}
              onSearch={(v) => goSearch(v)}
              placeholder="Search restaurants, cuisines, diet preferences…"
            />
          </div>

          {/* 6 filter groups below search bar */}
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

      {/* Diet profile nudge — only shown to logged-in users who haven't set preferences yet */}
      {user && !prefsSet && (
        <div style={{ maxWidth: 680, margin: '16px auto 0', padding: '0 24px' }}>
          <div
            style={{
              background: '#E8F5E9', border: '1px solid #2D9B5A30', borderRadius: 10,
              padding: '10px 16px', display: 'flex', justifyContent: 'space-between', alignItems: 'center',
            }}
          >
            <Text style={{ color: '#2D9B5A', fontSize: 13 }}>
              ✨ Set up your diet profile for personalised results
            </Text>
            <Button size="small" type="link" style={{ color: PRIMARY_COLOR, padding: 0 }} onClick={() => navigate('/onboarding')}>
              Set up →
            </Button>
          </div>
        </div>
      )}

    </div>
  )
}
