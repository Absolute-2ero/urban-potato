import { useEffect, useRef, useState } from 'react'
import { Button, Input, Modal, Spin, Typography } from 'antd'
import { AimOutlined, SearchOutlined } from '@ant-design/icons'
import { MapContainer, TileLayer, Marker, useMap, useMapEvents } from 'react-leaflet'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import { PRIMARY_COLOR } from '@/constants'
import { useLang } from '@/i18n/LanguageContext'

const { Text } = Typography

// SVG pin icon — avoids Leaflet's image import issues with bundlers
const PIN_ICON = L.divIcon({
  html: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 28 42" width="28" height="42">
    <path fill="${PRIMARY_COLOR}" stroke="white" stroke-width="1.5"
      d="M14 1C8.48 1 4 5.48 4 11c0 7.5 10 20 10 20s10-12.5 10-20c0-5.52-4.48-10-10-10z"/>
    <circle cx="14" cy="11" r="4" fill="white"/>
  </svg>`,
  className: '',
  iconSize: [28, 42],
  iconAnchor: [14, 42],
})

const HK_CENTRE: [number, number] = [22.3193, 114.1694]

const HK_DISTRICTS = [
  { name: 'Central',        lat: 22.2820, lng: 114.1588 },
  { name: 'Wan Chai',       lat: 22.2793, lng: 114.1722 },
  { name: 'Causeway Bay',   lat: 22.2800, lng: 114.1840 },
  { name: 'Tsim Sha Tsui',  lat: 22.2988, lng: 114.1722 },
  { name: 'Mong Kok',       lat: 22.3182, lng: 114.1693 },
  { name: 'Sha Tin',        lat: 22.3820, lng: 114.1884 },
  { name: 'Tuen Mun',       lat: 22.3910, lng: 113.9760 },
  { name: 'Kwun Tong',      lat: 22.3127, lng: 114.2262 },
  { name: 'Tseung Kwan O',  lat: 22.3073, lng: 114.2600 },
  { name: 'Yuen Long',      lat: 22.4445, lng: 114.0225 },
  { name: 'Tung Chung',     lat: 22.2889, lng: 113.9415 },
]

type NominatimResult = { display_name: string; lat: string; lon: string }

export async function reverseGeocode(lat: number, lng: number): Promise<string> {
  try {
    const res = await fetch(
      `https://nominatim.openstreetmap.org/reverse?lat=${lat}&lon=${lng}&format=json&zoom=14`,
      { headers: { 'Accept-Language': 'en' } },
    )
    const data = await res.json()
    const a = data.address || {}
    return (
      a.suburb || a.neighbourhood || a.city_district ||
      a.quarter || a.town || a.city || 'Hong Kong'
    )
  } catch {
    return 'Hong Kong'
  }
}

async function searchPlaces(query: string): Promise<NominatimResult[]> {
  try {
    const res = await fetch(
      `https://nominatim.openstreetmap.org/search?q=${encodeURIComponent(query)}&format=json&limit=5&countrycodes=hk`,
      { headers: { 'Accept-Language': 'en' } },
    )
    return await res.json()
  } catch {
    return []
  }
}

// Imperatively re-centre the map when `center` changes
function MapController({ center }: { center: [number, number] }) {
  const map = useMap()
  useEffect(() => { map.setView(center, 15, { animate: true }) }, [center[0], center[1]])
  return null
}

// Forward map clicks to parent
function ClickHandler({ onMapClick }: { onMapClick: (lat: number, lng: number) => void }) {
  useMapEvents({ click: (e) => onMapClick(e.latlng.lat, e.latlng.lng) })
  return null
}

interface Props {
  open: boolean
  initialLat: number
  initialLng: number
  onConfirm: (lat: number, lng: number, name: string) => void
  onClose: () => void
}

export function LocationPickerModal({ open, initialLat, initialLng, onConfirm, onClose }: Props) {
  const { t } = useLang()
  const [pos, setPos]               = useState<[number, number]>([initialLat, initialLng])
  const [mapCenter, setMapCenter]   = useState<[number, number]>([initialLat, initialLng])
  const [locationName, setName]     = useState('Hong Kong')
  const [query, setQuery]           = useState('')
  const [results, setResults]       = useState<NominatimResult[]>([])
  const [searching, setSearching]   = useState(false)
  const [gpsLoading, setGpsLoading] = useState(false)
  const searchTimer                 = useRef<ReturnType<typeof setTimeout> | null>(null)
  const markerRef                   = useRef<L.Marker | null>(null)

  // Reset state when modal opens
  useEffect(() => {
    if (!open) return
    const p: [number, number] = [initialLat, initialLng]
    setPos(p)
    setMapCenter(p)
    setQuery('')
    setResults([])
    reverseGeocode(initialLat, initialLng).then(setName)
  }, [open])

  const moveTo = async (lat: number, lng: number) => {
    setPos([lat, lng])
    setMapCenter([lat, lng])
    const name = await reverseGeocode(lat, lng)
    setName(name)
  }

  const handleSearch = (q: string) => {
    setQuery(q)
    setResults([])
    if (searchTimer.current) clearTimeout(searchTimer.current)
    if (!q.trim()) { setSearching(false); return }
    setSearching(true)
    searchTimer.current = setTimeout(async () => {
      const res = await searchPlaces(q)
      setResults(res)
      setSearching(false)
    }, 400)
  }

  const selectResult = (r: NominatimResult) => {
    const lat = parseFloat(r.lat)
    const lng = parseFloat(r.lon)
    moveTo(lat, lng)
    setName(r.display_name.split(',')[0].trim())
    setQuery('')
    setResults([])
  }

  const handleGPS = () => {
    setGpsLoading(true)
    navigator.geolocation.getCurrentPosition(
      (p) => { moveTo(p.coords.latitude, p.coords.longitude); setGpsLoading(false) },
      ()  => setGpsLoading(false),
      { timeout: 8000 },
    )
  }

  return (
    <Modal
      open={open}
      onCancel={onClose}
      title={t.loc_title}
      footer={null}
      width={480}
      styles={{ body: { padding: 0 } }}
      destroyOnClose
    >
      {/* Search input */}
      <div style={{ padding: '12px 16px 8px', position: 'relative' as const, zIndex: 500 }}>
        <Input
          prefix={searching ? <Spin size="small" /> : <SearchOutlined style={{ color: '#AAB4B4' }} />}
          placeholder={t.loc_placeholder}
          value={query}
          onChange={(e) => handleSearch(e.target.value)}
          allowClear
          onClear={() => { setQuery(''); setResults([]) }}
        />
        {results.length > 0 && (
          <div style={{
            position: 'absolute' as const, top: '100%', left: 16, right: 16,
            background: '#fff', border: '1px solid #E8E0D5', borderRadius: 8,
            boxShadow: '0 4px 16px rgba(0,0,0,0.12)', overflow: 'hidden', zIndex: 9999,
          }}>
            {results.map((r, i) => (
              <div
                key={i}
                onClick={() => selectResult(r)}
                style={{
                  padding: '10px 14px', cursor: 'pointer', fontSize: 13, color: '#1E2A2A',
                  borderBottom: i < results.length - 1 ? '1px solid #F0EAE0' : 'none',
                  transition: 'background 0.1s',
                }}
                onMouseEnter={(e) => (e.currentTarget.style.background = '#F7F3EE')}
                onMouseLeave={(e) => (e.currentTarget.style.background = '#fff')}
              >
                📍 {r.display_name}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Map */}
      <div style={{ height: 280, position: 'relative' as const }}>
        <MapContainer
          center={pos}
          zoom={15}
          style={{ height: '100%', width: '100%' }}
          zoomControl
        >
          <TileLayer
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
          />
          <MapController center={mapCenter} />
          <ClickHandler onMapClick={(lat, lng) => moveTo(lat, lng)} />
          <Marker
            position={pos}
            icon={PIN_ICON}
            draggable
            ref={markerRef}
            eventHandlers={{
              dragend: () => {
                const ll = markerRef.current?.getLatLng()
                if (ll) moveTo(ll.lat, ll.lng)
              },
            }}
          />
        </MapContainer>

        {/* Location name pill overlaid on map */}
        <div style={{
          position: 'absolute' as const, bottom: 10, left: '50%', transform: 'translateX(-50%)',
          background: 'rgba(255,255,255,0.95)', borderRadius: 20, padding: '4px 14px',
          fontSize: 12, fontWeight: 600, color: '#1E2A2A', zIndex: 1000,
          boxShadow: '0 2px 8px rgba(0,0,0,0.15)', whiteSpace: 'nowrap' as const,
          pointerEvents: 'none' as const,
        }}>
          📍 {locationName}
        </div>

        {/* Hint */}
        <div style={{
          position: 'absolute' as const, top: 8, right: 8,
          background: 'rgba(255,255,255,0.85)', borderRadius: 8, padding: '3px 8px',
          fontSize: 11, color: '#6B7A7A', zIndex: 1000, pointerEvents: 'none' as const,
        }}>
          {t.loc_hint}
        </div>
      </div>

      {/* HK district quick-picks */}
      <div style={{ padding: '12px 16px 8px' }}>
        <Text style={{ fontSize: 11, color: '#AAB4B4', fontWeight: 600, letterSpacing: 0.8, display: 'block', marginBottom: 8 }}>
          {t.loc_quick_pick}
        </Text>
        <div style={{ display: 'flex', flexWrap: 'wrap' as const, gap: 6 }}>
          {HK_DISTRICTS.map((d) => (
            <button
              key={d.name}
              onClick={() => { moveTo(d.lat, d.lng); setName(d.name) }}
              style={{
                padding: '4px 12px', borderRadius: 999,
                border: `1.5px solid ${locationName === d.name ? PRIMARY_COLOR : '#E8E0D5'}`,
                background: locationName === d.name ? PRIMARY_COLOR + '12' : '#FAFAF8',
                color: locationName === d.name ? PRIMARY_COLOR : '#1E2A2A',
                fontSize: 12, cursor: 'pointer', outline: 'none',
                fontWeight: locationName === d.name ? 600 : 400,
                transition: 'all 0.1s',
              }}
            >
              {d.name}
            </button>
          ))}
        </div>
      </div>

      {/* Footer actions */}
      <div style={{
        padding: '12px 16px', display: 'flex', justifyContent: 'space-between',
        alignItems: 'center', borderTop: '1px solid #F0EAE0',
      }}>
        <Button icon={<AimOutlined />} onClick={handleGPS} loading={gpsLoading}>
          {t.loc_gps}
        </Button>
        <Button
          type="primary"
          style={{ background: PRIMARY_COLOR, borderColor: PRIMARY_COLOR }}
          onClick={() => { onConfirm(pos[0], pos[1], locationName); onClose() }}
        >
          {t.loc_confirm}
        </Button>
      </div>
    </Modal>
  )
}
