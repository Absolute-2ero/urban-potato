import { useEffect, useState } from 'react'
import { Button, Popover, Select, Slider, Tag, Typography } from 'antd'
import { DownOutlined, EnvironmentOutlined } from '@ant-design/icons'
import { DIET_LABEL_META, PRIMARY_COLOR } from '@/constants'
import { useSearchStore } from '@/stores/searchStore'
import { LocationPickerModal } from '@/components/location/LocationPickerModal'
import { fetchCities } from '@/api/cities'
import { useLang } from '@/i18n/LanguageContext'
import type { City } from '@/api/cities'
import type { DietLabel } from '@/types'

const { Text } = Typography

// ── Static option lists ────────────────────────────────────────────────────

const PRICE_OPTIONS = [
  { value: '0-20', label: '$0–20', level: 1 },
  { value: '20-40', label: '$20–40', level: 2 },
  { value: '40-60', label: '$40–60', level: 3 },
  { value: '60+', label: '$60+', level: 4 },
]

const ALLERGY_DIET_LABELS: DietLabel[] = ['dairy-free', 'gluten-free', 'peanut-free', 'seafood-free', 'soy-free', 'no-spicy']

// ── Types ──────────────────────────────────────────────────────────────────

export interface FilterState {
  // URL-synced (sent to backend)
  dietLabels: DietLabel[]
  priceLevels: number[]
  sortMode: string
  // Local-only (UI state; backend extension needed)
  calorieRange: [number, number] | null
  nutritionLabels: string[]
  minRating: number | null
  maxDistanceKm: number | null
  extraDietRestrictions: string[]
  allergyRestrictions: string[]
  priceRange: [number, number] | null
}

export const EMPTY_FILTERS: FilterState = {
  dietLabels: [],
  priceLevels: [],
  sortMode: 'default',
  calorieRange: null,
  nutritionLabels: [],
  minRating: null,
  maxDistanceKm: null,
  extraDietRestrictions: [],
  allergyRestrictions: [],
  priceRange: null,
}

interface FilterBarProps {
  filters: FilterState
  onFilterChange: (updates: Partial<FilterState>) => void
  hideLocation?: boolean
}

// ── Helpers ────────────────────────────────────────────────────────────────

function calLabel([lo, hi]: [number, number]): string {
  if (lo === 0) return `≤${hi} kcal`
  if (hi >= 2000) return `≥${lo} kcal`
  return `${lo}–${hi} kcal`
}

function priceLabel([lo, hi]: [number, number]): string {
  if (lo === 0) return `≤HK$${hi}`
  if (hi >= 200) return `≥HK$${lo}`
  return `HK$${lo}–${hi}`
}

// ── Sub-component: group button with Popover ───────────────────────────────

function GroupBtn({
  emoji,
  label,
  activeCount,
  isOpen,
  onToggle,
  content,
  disabled,
}: {
  emoji: string
  label: string
  activeCount: number
  isOpen: boolean
  onToggle: (open: boolean) => void
  content: React.ReactNode
  disabled?: boolean
}) {
  const active = activeCount > 0
  return (
    <Popover
      trigger="click"
      open={isOpen}
      onOpenChange={disabled ? undefined : onToggle}
      content={content}
      arrow={false}
      overlayInnerStyle={{ padding: '14px 16px', borderRadius: 12, minWidth: 210, maxWidth: 310 }}
      placement="bottomLeft"
    >
      <button
        disabled={disabled}
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 4,
          padding: '6px 12px',
          borderRadius: 8,
          border: `1.5px solid ${active ? PRIMARY_COLOR : disabled ? '#E8E0D5' : '#E8E0D5'}`,
          background: active ? PRIMARY_COLOR + '12' : '#fff',
          color: active ? PRIMARY_COLOR : disabled ? '#C0BDB8' : '#6B7A7A',
          fontSize: 13,
          cursor: disabled ? 'not-allowed' : 'pointer',
          fontWeight: active ? 600 : 400,
          whiteSpace: 'nowrap' as const,
          outline: 'none',
          flexShrink: 0,
          transition: 'all 0.12s',
          opacity: disabled ? 0.5 : 1,
        }}
      >
        <span>{emoji}</span>
        <span>{label}{active ? ` · ${activeCount}` : ''}</span>
        <DownOutlined style={{ fontSize: 9, marginLeft: 1 }} />
      </button>
    </Popover>
  )
}

// ── Sort button — shows current sort mode inline, no chip ─────────────────

function SortBtn({ label, isOpen, onToggle, content }: {
  label: string
  isOpen: boolean
  onToggle: (open: boolean) => void
  content: React.ReactNode
}) {
  const { t } = useLang()
  const isDefault = label === t.filter_sort_best
  return (
    <Popover
      trigger="click"
      open={isOpen}
      onOpenChange={onToggle}
      content={content}
      arrow={false}
      overlayInnerStyle={{ padding: '14px 16px', borderRadius: 12, minWidth: 210, maxWidth: 310 }}
      placement="bottomLeft"
    >
      <button style={{
        display: 'flex', alignItems: 'center', gap: 5,
        padding: '6px 14px', borderRadius: 8,
        border: '1.5px solid #9E9E9E',
        background: '#F0F0F0',
        color: '#333',
        fontSize: 13, cursor: 'pointer', fontWeight: 500,
        whiteSpace: 'nowrap' as const, outline: 'none', flexShrink: 0,
        transition: 'all 0.12s',
      }}>
        <span>↕</span>
        <span>{t.filter_sort}: {label}</span>
        <DownOutlined style={{ fontSize: 9, marginLeft: 1 }} />
      </button>
    </Popover>
  )
}

// ── Sub-component: option chip grid ────────────────────────────────────────

function ChipGrid({
  options,
  onSelect,
}: {
  options: { value: string; label: string; emoji?: string }[]
  onSelect: (value: string) => void
}) {
  if (options.length === 0) {
    return <Text type="secondary" style={{ fontSize: 13 }}>{'✓'}</Text>
  }
  return (
    <div style={{ display: 'flex', flexWrap: 'wrap' as const, gap: 7 }}>
      {options.map((opt) => (
        <button
          key={opt.value}
          onClick={() => onSelect(opt.value)}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 5,
            padding: '5px 12px',
            borderRadius: 999,
            border: '1.5px solid #E8E0D5',
            background: '#FAFAF8',
            color: '#1E2A2A',
            fontSize: 13,
            cursor: 'pointer',
            outline: 'none',
          }}
        >
          {opt.emoji && <span>{opt.emoji}</span>}
          <span>{opt.label}</span>
        </button>
      ))}
    </div>
  )
}

// ── Sub-component: toggleable chip grid (stays open, highlights selected) ──

function ToggleChipGrid({
  options,
  selected,
  color,
  onToggle,
  onClear,
}: {
  options: { value: string; label: string; emoji?: string }[]
  selected: string[]
  color: string
  onToggle: (value: string) => void
  onClear: () => void
}) {
  return (
    <div>
      <div style={{ display: 'flex', flexWrap: 'wrap' as const, gap: 7, marginBottom: selected.length > 0 ? 10 : 0 }}>
        {options.map((opt) => {
          const active = selected.includes(opt.value)
          return (
            <button
              key={opt.value}
              onClick={() => onToggle(opt.value)}
              style={{
                display: 'flex', alignItems: 'center', gap: 5,
                padding: '5px 12px', borderRadius: 999,
                border: `1.5px solid ${active ? color : '#E8E0D5'}`,
                background: active ? color + '18' : '#FAFAF8',
                color: active ? color : '#1E2A2A',
                fontSize: 13, cursor: 'pointer', outline: 'none',
                fontWeight: active ? 600 : 400, transition: 'all 0.1s',
              }}
            >
              {opt.emoji && <span>{opt.emoji}</span>}
              <span>{opt.label}</span>
            </button>
          )
        })}
      </div>
      {selected.length > 0 && (
        <button
          onClick={onClear}
          style={{
            padding: '3px 10px', borderRadius: 6, border: '1.5px solid #E85454',
            background: '#FFF0F0', fontSize: 12, cursor: 'pointer', outline: 'none', color: '#E85454',
          }}
        >
          Clear
        </button>
      )}
    </div>
  )
}

// ── Active filter chip ─────────────────────────────────────────────────────

function ActiveChip({
  label,
  color,
  bg,
  onRemove,
}: {
  label: string
  color: string
  bg: string
  onRemove: () => void
}) {
  return (
    <Tag
      closable
      onClose={onRemove}
      style={{
        borderRadius: 999,
        padding: '3px 10px',
        border: `1.5px solid ${color}`,
        background: bg,
        color,
        fontSize: 12,
        fontWeight: 500,
        margin: 0,
      }}
    >
      {label}
    </Tag>
  )
}

// ── Main FilterBar ──────────────────────────────────────────────────────────

export function FilterBar({
  filters,
  onFilterChange,
  hideLocation = false,
}: FilterBarProps) {
  const { lat, lng, locationName, setLocation, setLocationName, doSearch } = useSearchStore()
  const { t, lang } = useLang()
  const [locModalOpen, setLocModalOpen] = useState(false)

  const NUTRITION_OPTIONS: { value: string; label: string; emoji: string; dietLabel: DietLabel }[] = [
    { value: 'low-fat',    label: t.nutrition_low_fat,    emoji: '💧', dietLabel: 'low-fat' },
    { value: 'low-sugar',  label: t.nutrition_low_sugar,  emoji: '🍬', dietLabel: 'low-sugar' },
    { value: 'low-sodium', label: t.nutrition_low_sodium, emoji: '🧂', dietLabel: 'low-sodium' },
    { value: 'low-oil',    label: t.nutrition_low_oil,    emoji: '🫙', dietLabel: 'low-oil' },
  ]
  const NUTRITION_DIET_LABELS: DietLabel[] = NUTRITION_OPTIONS.map(o => o.dietLabel)
  const SORT_OPTIONS = [
    { value: 'default',        label: t.filter_sort_best },
    { value: 'rating_first',   label: t.filter_sort_rating },
    { value: 'distance_first', label: t.filter_sort_nearest },
    { value: 'price_asc',      label: t.filter_sort_cheapest },
  ]
  const DIET_RESTRICTION_OPTIONS: { value: string; label: string; emoji: string; dietLabel?: DietLabel }[] = [
    { value: 'vegetarian',   label: t.diet_vegetarian,   emoji: '🥗', dietLabel: 'vegetarian' },
    { value: 'vegan',        label: t.diet_vegan,        emoji: '🌿', dietLabel: 'vegan' },
    { value: 'halal',        label: t.diet_halal,        emoji: '☪️',  dietLabel: 'halal' },
    { value: 'kosher',       label: t.diet_kosher,       emoji: '✡️',  dietLabel: 'kosher' },
    { value: 'keto',         label: t.diet_keto,         emoji: '🥑', dietLabel: 'keto' },
    { value: 'low-carb',     label: t.diet_low_carb,     emoji: '🥦', dietLabel: 'low-carb' },
    { value: 'high-protein', label: t.diet_high_protein, emoji: '💪', dietLabel: 'high-protein' },
  ]
  const ALLERGY_OPTIONS: { value: string; label: string; emoji: string; dietLabel: DietLabel }[] = [
    { value: 'peanut-free',  label: t.allergy_peanut_free,  emoji: '🥜', dietLabel: 'peanut-free' },
    { value: 'dairy-free',   label: t.allergy_dairy_free,   emoji: '🥛', dietLabel: 'dairy-free' },
    { value: 'gluten-free',  label: t.allergy_gluten_free,  emoji: '🌾', dietLabel: 'gluten-free' },
    { value: 'seafood-free', label: t.allergy_seafood_free, emoji: '🦐', dietLabel: 'seafood-free' },
    { value: 'soy-free',     label: t.allergy_soy_free,     emoji: '🫘', dietLabel: 'soy-free' },
    { value: 'no-spicy',     label: t.allergy_no_spicy,     emoji: '🌶️', dietLabel: 'no-spicy' },
  ]
  const ALLERGY_DIET_LABELS_ALL: DietLabel[] = ALLERGY_OPTIONS.map(o => o.dietLabel)
  const [cities, setCities] = useState<City[]>([])
  const [selectedCity, setSelectedCity] = useState<string | null>(null)

  useEffect(() => {
    fetchCities().then((list) => {
      setCities(list)
      if (list.length > 0 && !selectedCity) setSelectedCity(list[0].id)
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
  const [openGroup, setOpenGroup] = useState<string | null>(null)
  const [calSlider, setCalSlider] = useState<[number, number]>([0, 800])
  const [priceSlider, setPriceSlider] = useState<[number, number]>([0, 0])
  const [distSlider, setDistSlider] = useState<number>(5)
  const [ratingSlider, setRatingSlider] = useState<number>(4.0)

  useEffect(() => {
    if (filters.calorieRange === null) setCalSlider([0, 800])
    else setCalSlider(filters.calorieRange)
  }, [filters.calorieRange])

  useEffect(() => {
    if (filters.priceRange === null) setPriceSlider([0, 0])
    else setPriceSlider(filters.priceRange)
  }, [filters.priceRange])

  useEffect(() => {
    if (filters.maxDistanceKm === null) setDistSlider(5)
    else setDistSlider(filters.maxDistanceKm)
  }, [filters.maxDistanceKm])

  useEffect(() => {
    if (filters.minRating === null) setRatingSlider(4.0)
    else setRatingSlider(filters.minRating)
  }, [filters.minRating])

  const toggle = (key: string) => (open: boolean) => setOpenGroup(open ? key : null)
  const close = () => setOpenGroup(null)

  // ── Popover contents ───────────────────────────────────────────────────────

  const allergyContent = (
    <div>
      <Text style={{ fontSize: 11, color: '#AAB4B4', display: 'block', marginBottom: 10, fontWeight: 600, letterSpacing: 0.8 }}>
        {t.filter_section_allergens}
      </Text>
      <ToggleChipGrid
        options={ALLERGY_OPTIONS}
        selected={ALLERGY_OPTIONS.filter(o => filters.dietLabels.includes(o.dietLabel)).map(o => o.value)}
        color="#E85454"
        onToggle={(v) => {
          const opt = ALLERGY_OPTIONS.find(o => o.value === v)
          if (!opt) return
          const next = filters.dietLabels.includes(opt.dietLabel)
            ? filters.dietLabels.filter(d => d !== opt.dietLabel)
            : [...filters.dietLabels, opt.dietLabel]
          onFilterChange({ dietLabels: next })
        }}
        onClear={() => onFilterChange({
          dietLabels: filters.dietLabels.filter(d => !ALLERGY_DIET_LABELS.includes(d as DietLabel)),
        })}
      />
    </div>
  )

  const priceContent = (
    <div>
      <Text style={{ fontSize: 11, color: '#AAB4B4', display: 'block', marginBottom: 10, fontWeight: 600, letterSpacing: 0.8 }}>
        {t.filter_section_price}
      </Text>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
        <div style={{ position: 'relative' as const, flex: 1 }}>
          <span style={{ position: 'absolute' as const, left: 8, top: '50%', transform: 'translateY(-50%)', color: '#6B7A7A', fontSize: 11 }}>HK$</span>
          <input
            type="number"
            min={0}
            placeholder="Min"
            value={priceSlider[0] === 0 ? '' : priceSlider[0]}
            onChange={(e) => {
              const lo = Math.max(0, Number(e.target.value) || 0)
              const next: [number, number] = [lo, priceSlider[1]]
              setPriceSlider(next)
              onFilterChange({ priceRange: next[0] === 0 && next[1] === 0 ? null : next })
            }}
            style={{
              width: '100%', padding: '6px 8px 6px 36px', borderRadius: 8,
              border: '1.5px solid #E8E0D5', fontSize: 13, outline: 'none',
              boxSizing: 'border-box' as const,
            }}
          />
        </div>
        <Text type="secondary" style={{ fontSize: 13 }}>–</Text>
        <div style={{ position: 'relative' as const, flex: 1 }}>
          <span style={{ position: 'absolute' as const, left: 8, top: '50%', transform: 'translateY(-50%)', color: '#6B7A7A', fontSize: 11 }}>HK$</span>
          <input
            type="number"
            min={0}
            placeholder="Max"
            value={priceSlider[1] === 0 ? '' : priceSlider[1]}
            onChange={(e) => {
              const hi = Math.max(0, Number(e.target.value) || 0)
              const next: [number, number] = [priceSlider[0], hi]
              setPriceSlider(next)
              onFilterChange({ priceRange: next[0] === 0 && next[1] === 0 ? null : next })
            }}
            style={{
              width: '100%', padding: '6px 8px 6px 36px', borderRadius: 8,
              border: '1.5px solid #E8E0D5', fontSize: 13, outline: 'none',
              boxSizing: 'border-box' as const,
            }}
          />
        </div>
      </div>
      <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' as const }}>
        {([[0, 30], [0, 50], [0, 80], [0, 150]] as [number, number][]).map(([lo, hi]) => (
          <button
            key={hi}
            onClick={() => { const r: [number, number] = [lo, hi]; setPriceSlider(r); onFilterChange({ priceRange: r }) }}
            style={{
              padding: '3px 10px', borderRadius: 6, border: '1.5px solid #E8E0D5',
              background: '#fff', fontSize: 12, cursor: 'pointer', outline: 'none', color: '#6B7A7A',
            }}
          >
            ≤HK${hi}
          </button>
        ))}
        {filters.priceRange && (
          <button
            onClick={() => { setPriceSlider([0, 0]); onFilterChange({ priceRange: null }) }}
            style={{
              padding: '3px 10px', borderRadius: 6, border: '1.5px solid #E85454',
              background: '#FFF0F0', fontSize: 12, cursor: 'pointer', outline: 'none', color: '#E85454',
            }}
          >
            Clear
          </button>
        )}
      </div>
    </div>
  )

  const healthContent = (
    <div>
      <Text style={{ fontSize: 11, color: '#AAB4B4', display: 'block', marginBottom: 10, fontWeight: 600, letterSpacing: 0.8 }}>
        {t.filter_section_calorie}
      </Text>
      <div style={{ paddingRight: 6, marginBottom: 4 }}>
        <Slider
          range
          min={0}
          max={2000}
          step={50}
          value={calSlider}
          onChange={(v) => setCalSlider(v as [number, number])}
          onChangeComplete={(v) => onFilterChange({ calorieRange: v as [number, number] })}
          tooltip={{ formatter: (v) => `${v} kcal` }}
          styles={{
            track: { background: '#6A1B9A' },
            handle: { borderColor: '#6A1B9A' },
          }}
        />
        <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: -8, marginBottom: 8 }}>
          <Text type="secondary" style={{ fontSize: 11 }}>{calSlider[0]} kcal</Text>
          <Text type="secondary" style={{ fontSize: 11 }}>{calSlider[1]} kcal</Text>
        </div>
      </div>
      <div style={{ display: 'flex', gap: 6, marginBottom: 16, flexWrap: 'wrap' as const }}>
        {([[0, 300], [0, 500], [0, 800]] as [number, number][]).map(([lo, hi]) => (
          <button
            key={hi}
            onClick={() => { const r: [number, number] = [lo, hi]; setCalSlider(r); onFilterChange({ calorieRange: r }) }}
            style={{
              padding: '3px 10px', borderRadius: 999, border: '1.5px solid #E8E0D5',
              background: '#fff', fontSize: 12, cursor: 'pointer', outline: 'none', color: '#6B7A7A',
            }}
          >
            ≤{hi}
          </button>
        ))}
        {filters.calorieRange && (
          <button
            onClick={() => { setCalSlider([0, 800]); onFilterChange({ calorieRange: null }) }}
            style={{
              padding: '3px 10px', borderRadius: 999, border: '1.5px solid #E85454',
              background: '#FFF0F0', fontSize: 12, cursor: 'pointer', outline: 'none', color: '#E85454',
            }}
          >
            Clear
          </button>
        )}
      </div>
      <Text style={{ fontSize: 11, color: '#AAB4B4', display: 'block', marginBottom: 10, fontWeight: 600, letterSpacing: 0.8 }}>
        {t.filter_section_diet_labels}
      </Text>
      <ToggleChipGrid
        options={NUTRITION_OPTIONS}
        selected={NUTRITION_OPTIONS.filter(o => filters.dietLabels.includes(o.dietLabel)).map(o => o.value)}
        color="#6A1B9A"
        onToggle={(v) => {
          const opt = NUTRITION_OPTIONS.find(o => o.value === v)
          if (!opt) return
          const next = filters.dietLabels.includes(opt.dietLabel)
            ? filters.dietLabels.filter(d => d !== opt.dietLabel)
            : [...filters.dietLabels, opt.dietLabel]
          onFilterChange({ dietLabels: next })
        }}
        onClear={() => onFilterChange({ dietLabels: filters.dietLabels.filter(d => !NUTRITION_DIET_LABELS.includes(d as DietLabel)) })}
      />
    </div>
  )

  const ratingContent = (
    <div>
      <Text style={{ fontSize: 11, color: '#AAB4B4', display: 'block', marginBottom: 10, fontWeight: 600, letterSpacing: 0.8 }}>
        {t.filter_section_min_rating}
      </Text>
      <div style={{ paddingRight: 6, marginBottom: 4 }}>
        <Slider
          min={0}
          max={5}
          step={0.5}
          value={ratingSlider}
          onChange={(v) => setRatingSlider(v as number)}
          onChangeComplete={(v) => onFilterChange({ minRating: v as number })}
          tooltip={{ formatter: (v) => `${v} ⭐` }}
          styles={{ track: { background: 'transparent' }, handle: { borderColor: '#F57F17' } }}
        />
        <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: -8, marginBottom: 8 }}>
          <Text type="secondary" style={{ fontSize: 11 }}>0</Text>
          <Text type="secondary" style={{ fontSize: 11 }}>5 ⭐</Text>
        </div>
      </div>
      <div style={{ display: 'flex', gap: 6, marginBottom: 16, flexWrap: 'wrap' as const }}>
        {[3.5, 4.0, 4.5].map((v) => {
          const active = ratingSlider === v && filters.minRating !== null
          return (
            <button
              key={v}
              onClick={() => { setRatingSlider(v); onFilterChange({ minRating: v }) }}
              style={{
                padding: '3px 10px', borderRadius: 6,
                border: `1.5px solid ${active ? '#F57F17' : '#E8E0D5'}`,
                background: active ? '#FFF8E1' : '#fff',
                fontSize: 12, cursor: 'pointer', outline: 'none',
                color: active ? '#F57F17' : '#6B7A7A',
                fontWeight: active ? 600 : 400,
                transition: 'all 0.12s',
              }}
            >
              {v}+ ⭐
            </button>
          )
        })}
        {filters.minRating !== null && (
          <button
            onClick={() => { setRatingSlider(4.0); onFilterChange({ minRating: null }) }}
            style={{
              padding: '3px 10px', borderRadius: 6, border: '1.5px solid #E85454',
              background: '#FFF0F0', fontSize: 12, cursor: 'pointer', outline: 'none', color: '#E85454',
            }}
          >
            Clear
          </button>
        )}
      </div>
    </div>
  )

  const sortContent = (
    <div>
      <Text style={{ fontSize: 11, color: '#AAB4B4', display: 'block', marginBottom: 10, fontWeight: 600, letterSpacing: 0.8 }}>
        {t.filter_section_sort_by}
      </Text>
      <div style={{ display: 'flex', flexDirection: 'column' as const, gap: 6 }}>
        {SORT_OPTIONS.map((opt) => {
          const active = filters.sortMode === opt.value
          return (
            <button
              key={opt.value}
              onClick={() => { onFilterChange({ sortMode: opt.value }); close() }}
              style={{
                padding: '7px 12px', borderRadius: 8,
                border: `1.5px solid ${active ? PRIMARY_COLOR : '#E8E0D5'}`,
                background: active ? PRIMARY_COLOR + '10' : '#fff',
                color: active ? PRIMARY_COLOR : '#6B7A7A',
                fontSize: 13, cursor: 'pointer', outline: 'none',
                fontWeight: active ? 600 : 400, textAlign: 'left' as const,
              }}
            >
              {opt.label}
            </button>
          )
        })}
      </div>
    </div>
  )

  const distanceContent = (
    <div>
      {lat === null ? (
        <div style={{ textAlign: 'center' as const }}>
          <Text type="secondary" style={{ fontSize: 13, display: 'block', marginBottom: 10 }}>
            📍 {t.filter_no_location}
          </Text>
          <Button size="small" type="link" onClick={() => setLocModalOpen(true)}>
            {t.filter_set_location_btn}
          </Button>
        </div>
      ) : (
        <>
          <Text style={{ fontSize: 11, color: '#AAB4B4', display: 'block', marginBottom: 10, fontWeight: 600, letterSpacing: 0.8 }}>
            {t.filter_section_max_distance}
          </Text>
          <div style={{ paddingRight: 6, marginBottom: 4 }}>
            <Slider
              min={0.5}
              max={10}
              step={0.5}
              value={distSlider}
              onChange={(v) => setDistSlider(v as number)}
              onChangeComplete={(v) => onFilterChange({ maxDistanceKm: v as number })}
              tooltip={{ formatter: (v) => v! < 1 ? `${v! * 1000}m` : `${v}km` }}
              styles={{ track: { background: '#00838F' }, handle: { borderColor: '#00838F' } }}
            />
            <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: -8, marginBottom: 8 }}>
              <Text type="secondary" style={{ fontSize: 11 }}>500m</Text>
              <Text type="secondary" style={{ fontSize: 11 }}>10km</Text>
            </div>
          </div>
          <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' as const }}>
            {([0.5, 1, 3, 5] as number[]).map((km) => (
              <button
                key={km}
                onClick={() => { setDistSlider(km); onFilterChange({ maxDistanceKm: km }) }}
                style={{
                  padding: '3px 10px', borderRadius: 6, border: '1.5px solid #E8E0D5',
                  background: '#fff', fontSize: 12, cursor: 'pointer', outline: 'none', color: '#6B7A7A',
                }}
              >
                {km < 1 ? `${km * 1000}m` : `${km}km`}
              </button>
            ))}
            {filters.maxDistanceKm !== null && (
              <button
                onClick={() => { setDistSlider(5); onFilterChange({ maxDistanceKm: null }) }}
                style={{
                  padding: '3px 10px', borderRadius: 6, border: '1.5px solid #E85454',
                  background: '#FFF0F0', fontSize: 12, cursor: 'pointer', outline: 'none', color: '#E85454',
                }}
              >
                Clear
              </button>
            )}
          </div>
        </>
      )}
    </div>
  )

  const dietContent = (
    <div>
      <Text style={{ fontSize: 11, color: '#AAB4B4', display: 'block', marginBottom: 10, fontWeight: 600, letterSpacing: 0.8 }}>
        {t.filter_section_diet_restrictions}
      </Text>
      <ToggleChipGrid
        options={DIET_RESTRICTION_OPTIONS}
        selected={DIET_RESTRICTION_OPTIONS
          .filter((o) => (o.dietLabel ? filters.dietLabels.includes(o.dietLabel) : filters.extraDietRestrictions.includes(o.value)))
          .map((o) => o.value)}
        color="#2D9B5A"
        onToggle={(v) => {
          const opt = DIET_RESTRICTION_OPTIONS.find((o) => o.value === v)
          if (!opt) return
          if (opt.dietLabel) {
            const next = filters.dietLabels.includes(opt.dietLabel)
              ? filters.dietLabels.filter((d) => d !== opt.dietLabel)
              : [...filters.dietLabels, opt.dietLabel]
            onFilterChange({ dietLabels: next })
          } else {
            const next = filters.extraDietRestrictions.includes(v)
              ? filters.extraDietRestrictions.filter((r) => r !== v)
              : [...filters.extraDietRestrictions, v]
            onFilterChange({ extraDietRestrictions: next })
          }
        }}
        onClear={() => {
          const dietDietLabels = DIET_RESTRICTION_OPTIONS.filter((o) => o.dietLabel).map((o) => o.dietLabel as DietLabel)
          onFilterChange({
            dietLabels: filters.dietLabels.filter((d) => !dietDietLabels.includes(d)),
            extraDietRestrictions: [],
          })
        }}
      />
    </div>
  )

  // ── Active filter counts per group ─────────────────────────────────────────

  const priceCount = filters.priceRange ? 1 : 0
  const healthCount = (filters.calorieRange ? 1 : 0) + filters.dietLabels.filter(d => NUTRITION_DIET_LABELS.includes(d as DietLabel)).length
  const ratingCount = filters.minRating !== null ? 1 : 0
  const sortCount = 0 // sort shown inline in button, not as a chip
  const distanceCount = filters.maxDistanceKm !== null ? 1 : 0
  const allergyCount = filters.dietLabels.filter(d => ALLERGY_DIET_LABELS.includes(d as DietLabel)).length
  const dietCount = filters.dietLabels.filter(d => !ALLERGY_DIET_LABELS.includes(d as DietLabel) && !NUTRITION_DIET_LABELS.includes(d as DietLabel)).length + filters.extraDietRestrictions.length

  const hasActive =
    priceCount + healthCount + ratingCount + distanceCount + allergyCount + dietCount > 0

  // ── Render ──────────────────────────────────────────────────────────────────

  return (
    <div>
      {/* Row 1: Location (if shown) + Sort, Distance, Rating, Price */}
      <div
        style={{
          display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6,
          overflowX: 'auto' as const, scrollbarWidth: 'none' as any, msOverflowStyle: 'none' as any,
        }}
      >
        {!hideLocation && (
          <>
            <Select
              value={selectedCity}
              onChange={handleCityChange}
              style={{ width: 110, flexShrink: 0 }}
              size="middle"
              options={cities.map((c) => ({ value: c.id, label: (lang === 'zh' ? c.label_zh : null) || c.label }))}
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
            <div style={{ width: 1, height: 22, background: '#E8E0D5', flexShrink: 0, margin: '0 2px' }} />
          </>
        )}
        <SortBtn
          label={SORT_OPTIONS.find((s) => s.value === filters.sortMode)?.label ?? t.filter_sort_best}
          isOpen={openGroup === 'sort'}
          onToggle={toggle('sort')}
          content={sortContent}
        />
        <GroupBtn emoji="📍" label={t.filter_distance} activeCount={distanceCount} isOpen={openGroup === 'distance'} onToggle={toggle('distance')} content={distanceContent} disabled={lat === null} />
        <GroupBtn emoji="⭐" label={t.filter_rating} activeCount={ratingCount} isOpen={openGroup === 'rating'} onToggle={toggle('rating')} content={ratingContent} />
        <GroupBtn emoji="HK$" label={t.filter_price} activeCount={priceCount} isOpen={openGroup === 'price'} onToggle={toggle('price')} content={priceContent} />
      </div>

      {/* Row 2: Health, Diet, Allergies */}
      <div
        style={{
          display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6,
          overflowX: 'auto' as const, scrollbarWidth: 'none' as any, msOverflowStyle: 'none' as any,
        }}
      >
        <GroupBtn emoji="🥗" label={t.filter_health} activeCount={healthCount} isOpen={openGroup === 'health'} onToggle={toggle('health')} content={healthContent} />
        <GroupBtn emoji="🌿" label={t.filter_diet} activeCount={dietCount} isOpen={openGroup === 'diet'} onToggle={toggle('diet')} content={dietContent} />
        <GroupBtn emoji="⚠️" label={t.filter_allergies} activeCount={allergyCount} isOpen={openGroup === 'allergies'} onToggle={toggle('allergies')} content={allergyContent} />
      </div>

      {/* Active filter chips */}
      {hasActive && (
        <div style={{ display: 'flex', flexWrap: 'wrap' as const, gap: 6, marginTop: 10, alignItems: 'center' }}>
          {/* Health (purple) */}
          {filters.calorieRange && (
            <ActiveChip label={`🔥 ${calLabel(filters.calorieRange)}`} color="#6A1B9A" bg="#F3E5F5"
              onRemove={() => onFilterChange({ calorieRange: null })} />
          )}
          {filters.dietLabels.filter(d => NUTRITION_DIET_LABELS.includes(d as DietLabel)).map((label) => {
            const opt = NUTRITION_OPTIONS.find(o => o.dietLabel === label)
            if (!opt) return null
            return (
              <ActiveChip key={`nutrition-${label}`} label={`${opt.emoji} ${opt.label}`} color="#6A1B9A" bg="#F3E5F5"
                onRemove={() => onFilterChange({ dietLabels: filters.dietLabels.filter(d => d !== label) })} />
            )
          })}
          {/* Diet (green) */}
          {filters.dietLabels.filter(d => !ALLERGY_DIET_LABELS.includes(d as DietLabel) && !NUTRITION_DIET_LABELS.includes(d as DietLabel)).map((label) => {
            const opt = DIET_RESTRICTION_OPTIONS.find((o) => o.dietLabel === label)
            const emoji = opt?.emoji ?? '🌿'
            const labelText = opt?.label ?? label
            return (
              <ActiveChip key={`diet-${label}`} label={`${emoji} ${labelText}`} color="#2D9B5A" bg="#E8F5E920"
                onRemove={() => onFilterChange({ dietLabels: filters.dietLabels.filter((d) => d !== label) })} />
            )
          })}
          {filters.extraDietRestrictions.map((value) => {
            const opt = DIET_RESTRICTION_OPTIONS.find((o) => o.value === value)
            if (!opt) return null
            return (
              <ActiveChip key={`restriction-${value}`} label={`${opt.emoji} ${opt.label}`} color="#2D9B5A" bg="#E8F5E920"
                onRemove={() => onFilterChange({ extraDietRestrictions: filters.extraDietRestrictions.filter((r) => r !== value) })} />
            )
          })}
          {/* Allergies (red) */}
          {filters.dietLabels.filter(d => ALLERGY_DIET_LABELS.includes(d as DietLabel)).map((label) => {
            const opt = ALLERGY_OPTIONS.find(o => o.dietLabel === label)
            if (!opt) return null
            return (
              <ActiveChip key={`allergy-${label}`} label={`${opt.emoji} ${opt.label}`} color="#E85454" bg="#FFF0F0"
                onRemove={() => onFilterChange({ dietLabels: filters.dietLabels.filter(d => d !== label) })} />
            )
          })}
          {/* Sort is shown inline in the Sort button — no chip here */}
          {/* Distance (teal) */}
          {filters.maxDistanceKm !== null && (
            <ActiveChip label={`📍 ${filters.maxDistanceKm! < 1 ? `${filters.maxDistanceKm! * 1000}m` : `${filters.maxDistanceKm}km`}`} color="#00838F" bg="#E0F7FA"
              onRemove={() => onFilterChange({ maxDistanceKm: null })} />
          )}
          {/* Rating (amber) */}
          {filters.minRating !== null && (
            <ActiveChip label={`⭐ ${filters.minRating}+`} color="#F57F17" bg="#FFF8E1"
              onRemove={() => onFilterChange({ minRating: null })} />
          )}
          {/* Price (blue) */}
          {filters.priceRange && (
            <ActiveChip label={`${priceLabel(filters.priceRange)}`} color="#1565C0" bg="#E3F2FD"
              onRemove={() => onFilterChange({ priceRange: null })} />
          )}
          <Button
            size="small"
            type="text"
            style={{ color: '#AAB4B4', fontSize: 12 }}
            onClick={() =>
              onFilterChange({
                dietLabels: [], priceLevels: [], sortMode: 'default',
                calorieRange: null, nutritionLabels: [],
                minRating: null, maxDistanceKm: null, extraDietRestrictions: [],
                allergyRestrictions: [], priceRange: null, minPrice: null, maxPrice: null,
              })
            }
          >
            {t.filter_clear_all}
          </Button>
        </div>
      )}

      <LocationPickerModal
        open={locModalOpen}
        initialLat={lat ?? 22.3193}
        initialLng={lng ?? 114.1694}
        onConfirm={(lat, lng, name) => {
          setLocation(lat, lng)
          setLocationName(name)
          doSearch()
        }}
        onClose={() => setLocModalOpen(false)}
      />
    </div>
  )
}
