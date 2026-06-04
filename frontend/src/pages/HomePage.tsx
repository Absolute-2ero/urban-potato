import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Button, Select, Typography, message } from 'antd'
import { EnvironmentOutlined } from '@ant-design/icons'
import { SearchBar } from '@/components/search/SearchBar'
import { FilterBar, FilterState, EMPTY_FILTERS } from '@/components/search/FilterBar'
import { LocationPickerModal, reverseGeocode } from '@/components/location/LocationPickerModal'
import { fetchCities } from '@/api/cities'
import { parseQuery } from '@/api/search'
import { useSearchStore } from '@/stores/searchStore'
import { useAuthStore } from '@/stores/authStore'
import { loadPrefs, prefsToDietLabels, hasPrefs } from '@/utils/prefs'
import { PRIMARY_COLOR } from '@/constants'
import { useLang } from '@/i18n/LanguageContext'
import type { City } from '@/api/cities'
import type { DietLabel } from '@/types'

const { Title, Text } = Typography

const HK_CENTRE = { lat: 22.3193, lng: 114.1694 }

// ── Easter egg ────────────────────────────────────────────────────────────────
const _VEGGIES = ['🥕','🥦','🧅','🍅','🌽','🥑','🫑','🌶️','🍆','🧄','🥬','🫛','🥒','🧆']

if (typeof document !== 'undefined' && !document.getElementById('veggie-burst-css')) {
  const s = document.createElement('style')
  s.id = 'veggie-burst-css'
  s.textContent = `
    @keyframes veggie-burst {
      0%   { transform: translate(0,0) scale(1.4) rotate(0deg); opacity: 1; }
      65%  { opacity: 1; }
      100% { transform: translate(var(--vx),var(--vy)) scale(0) rotate(var(--vr)); opacity: 0; }
    }
  `
  document.head.appendChild(s)
}

interface _VegParticle { id: number; emoji: string; x: number; y: number; vx: string; vy: string; vr: string; delay: number }

export default function HomePage() {
  const navigate = useNavigate()
  const { lat, lng, locationName, setLocation, setLocationName, setCity, city: storeCity, searchMode, setSearchMode } = useSearchStore()
  const { t } = useLang()
  const { user } = useAuthStore()
  const [q, setQ] = useState('')
  const [filters, setFilters] = useState<FilterState>(EMPTY_FILTERS)
  const saladRef = useRef<HTMLDivElement>(null)
  const [vegParticles, setVegParticles] = useState<_VegParticle[]>([])

  const burstVeggies = () => {
    if (vegParticles.length) return
    const rect = saladRef.current?.getBoundingClientRect()
    const cx = rect ? rect.left + rect.width / 2 - 12 : window.innerWidth / 2
    const cy = rect ? rect.top + rect.height / 2 - 12 : 120
    const particles: _VegParticle[] = Array.from({ length: 14 }, (_, i) => {
      const angle = (i / 14) * Math.PI * 2 + (Math.random() - 0.5) * 0.7
      const dist = 90 + Math.random() * 110
      return {
        id: i,
        emoji: _VEGGIES[i % _VEGGIES.length],
        x: cx, y: cy,
        vx: `${(Math.cos(angle) * dist).toFixed(1)}px`,
        vy: `${(Math.sin(angle) * dist - 30).toFixed(1)}px`,
        vr: `${((Math.random() - 0.5) * 700).toFixed(1)}deg`,
        delay: Math.floor(Math.random() * 80),
      }
    })
    setVegParticles(particles)
    setTimeout(() => setVegParticles([]), 980)
  }
  const [prefsSet, setPrefsSet] = useState(false)
  const [locModalOpen, setLocModalOpen] = useState(false)
  const [cities, setCities] = useState<City[]>([])
  const [selectedCity, setSelectedCity] = useState<string | null>(storeCity || null)
  const [parsing, setParsing] = useState(false)

  useEffect(() => {
    fetchCities().then((list) => {
      setCities(list)
      if (list.length === 0) return
      const activeId = storeCity || list[0].id
      const active = list.find((c) => c.id === activeId) ?? list[0]
      setSelectedCity(active.id)
      setCity(active.id)
    }).catch(() => {})
  }, [])

  const handleCityChange = (id: string) => {
    const city = cities.find((c) => c.id === id)
    if (!city) return
    setSelectedCity(id)
    setCity(id)
    setLocation(city.center.lat, city.center.lng)
    setLocationName(city.label)
  }

  const handleFilterChange = (updates: Partial<FilterState>) => {
    setFilters((prev) => ({ ...prev, ...updates }))
  }

  // Apply saved preferences as default filters
  useEffect(() => {
    if (!user) { setPrefsSet(false); return }
    const prefs = loadPrefs(user.id)
    const defaultLabels = prefsToDietLabels(prefs) as DietLabel[]
    setPrefsSet(hasPrefs(user.id))
    if (defaultLabels.length > 0) {
      setFilters((prev) => ({ ...prev, dietLabels: defaultLabels }))
    }
  }, [user?.id])

  // On first load: try GPS, fall back to HK centre
  useEffect(() => {
    if (lat !== null) return
    if (!('geolocation' in navigator)) {
      setLocation(HK_CENTRE.lat, HK_CENTRE.lng)
      return
    }
    navigator.geolocation.getCurrentPosition(
      async (pos) => {
        setLocation(pos.coords.latitude, pos.coords.longitude)
        const name = await reverseGeocode(pos.coords.latitude, pos.coords.longitude)
        setLocationName(name)
      },
      () => {
        setLocation(HK_CENTRE.lat, HK_CENTRE.lng)
        setLocationName('Hong Kong')
        message.info(t.home_no_location)
      },
      { timeout: 5000 },
    )
  }, [])

  const goSearch = async (query: string) => {
    const trimmed = query.trim()
    const params = new URLSearchParams()
    if (selectedCity) params.set('city', selectedCity)
    filters.dietLabels.forEach((d) => params.append('diet', d))
    filters.priceLevels.forEach((p) => params.append('price', String(p)))
    if (filters.sortMode !== 'default') params.set('sort', filters.sortMode)
    if (filters.maxDistanceKm != null) params.set('radius_km', String(filters.maxDistanceKm))

    if (searchMode === 'semantic') {
      params.set('q', trimmed)
      params.set('semantic', 'true')
      navigate(`/search?${params.toString()}`)
      return
    }

    if (trimmed.length > 5) {
      setParsing(true)
      try {
        const parsed = await parseQuery(trimmed, selectedCity ?? undefined)
        if (parsed?.has_extracted_params) {
          params.set('q', parsed.q || trimmed)
          parsed.diet_labels.forEach((d) => params.append('diet', d))
          parsed.price_levels.forEach((p) => params.append('price', String(p)))
          if (parsed.sort_mode !== 'default') params.set('sort', parsed.sort_mode)
          if (parsed.radius_km != null) params.set('radius_km', String(parsed.radius_km))
          if (parsed.location_lat != null && parsed.location_lng != null) {
            params.set('lat', String(parsed.location_lat))
            params.set('lng', String(parsed.location_lng))
          }
          navigate(`/search?${params.toString()}`)
          return
        }
      } catch { /* fallback to plain search */ } finally {
        setParsing(false)
      }
    }

    if (trimmed) params.set('q', trimmed)
    navigate(`/search?${params.toString()}`)
  }

  return (
    <div style={{ background: '#F7F3EE', minHeight: 'calc(100vh - 52px)' }}>
      <div style={{
        background: 'linear-gradient(150deg, #edfff4 0%, #F7F3EE 65%)',
        padding: '48px 24px 32px', textAlign: 'center',
      }}>
        <div
          ref={saladRef}
          onClick={burstVeggies}
          style={{ fontSize: 52, marginBottom: 8, cursor: 'pointer', display: 'inline-block', userSelect: 'none' }}
          title="🤫"
        >🥗</div>
        {vegParticles.map((p) => (
          <span key={p.id} style={{
            position: 'fixed', left: p.x, top: p.y,
            fontSize: 26, pointerEvents: 'none', zIndex: 9999, userSelect: 'none',
            animation: `veggie-burst 0.88s ease-out ${p.delay}ms forwards`,
            '--vx': p.vx, '--vy': p.vy, '--vr': p.vr,
          } as React.CSSProperties}>{p.emoji}</span>
        ))}
        <Title level={1} style={{ margin: '0 0 6px', color: PRIMARY_COLOR, fontSize: 38, fontWeight: 800, letterSpacing: -1 }}>
          MacroBite
        </Title>
        <Text style={{ fontSize: 15, color: '#A0AFAF', display: 'block', marginBottom: 4 }}>
          列位诸公，今天吃什么？
        </Text>
        <Text style={{ fontSize: 17, color: '#6B7A7A', display: 'block', marginBottom: 32 }}>
          {t.home_tagline}
        </Text>

        <div style={{ maxWidth: 680, margin: '0 auto' }}>
          {/* Location row */}
          <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 10 }}>
            <Select
              value={selectedCity}
              onChange={handleCityChange}
              style={{ width: 120 }}
              size="middle"
              options={cities.map((c) => ({ value: c.id, label: (t.nav_lang_toggle === 'English' ? c.label_zh : null) || c.label }))}
              suffixIcon={<EnvironmentOutlined style={{ fontSize: 12 }} />}
              placeholder="City"
            />
            <button
              onClick={() => setLocModalOpen(true)}
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
          </div>

          {/* Search bar */}
          <div style={{ marginBottom: 12 }}>
            <SearchBar
              value={q}
              onChange={setQ}
              onSearch={goSearch}
              placeholder={t.home_placeholder}
              loading={parsing}
              searchMode={searchMode}
              onSearchModeChange={setSearchMode}
            />
          </div>

          {/* Filter bar */}
          <FilterBar filters={filters} onFilterChange={handleFilterChange} hideLocation />
        </div>
      </div>

      {/* Diet profile nudge */}
      {user && !prefsSet && (
        <div style={{ maxWidth: 680, margin: '16px auto 0', padding: '0 24px' }}>
          <div style={{
            background: '#E8F5E9', border: '1px solid #2D9B5A30', borderRadius: 10,
            padding: '10px 16px', display: 'flex', justifyContent: 'space-between', alignItems: 'center',
          }}>
            <Text style={{ color: '#2D9B5A', fontSize: 13 }}>
              ✨ {t.home_diet_nudge}
            </Text>
            <Button size="small" type="link" style={{ color: PRIMARY_COLOR, padding: 0 }} onClick={() => navigate('/onboarding')}>
              {t.home_diet_nudge_btn}
            </Button>
          </div>
        </div>
      )}

      <LocationPickerModal
        open={locModalOpen}
        initialLat={lat ?? HK_CENTRE.lat}
        initialLng={lng ?? HK_CENTRE.lng}
        onConfirm={(lat, lng, name) => { setLocation(lat, lng); setLocationName(name) }}
        onClose={() => setLocModalOpen(false)}
      />
    </div>
  )
}
