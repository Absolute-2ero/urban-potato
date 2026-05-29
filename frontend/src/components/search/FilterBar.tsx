import { useEffect, useState } from 'react'
import { Button, Popover, Select, Slider, Tag, Tooltip, Typography } from 'antd'
import { AimOutlined, DownOutlined, EnvironmentOutlined } from '@ant-design/icons'
import { DIET_LABEL_META, PRIMARY_COLOR } from '@/constants'
import type { DietLabel } from '@/types'
import type { City } from '@/api/cities'

const { Text } = Typography

// ── Static option lists ────────────────────────────────────────────────────

const CUISINE_OPTIONS = [
  { value: 'sichuan',   label: 'Sichuan',   emoji: '🌶️' },
  { value: 'cantonese', label: 'Cantonese', emoji: '🍵' },
  { value: 'hunan',     label: 'Hunan',     emoji: '🥘' },
  { value: 'shandong',  label: 'Shandong',  emoji: '🦞' },
  { value: 'jiangsu',   label: 'Jiangsu',   emoji: '🍤' },
  { value: 'zhejiang',  label: 'Zhejiang',  emoji: '🐟' },
  { value: 'fujian',    label: 'Fujian',    emoji: '🍲' },
  { value: 'anhui',     label: 'Anhui',     emoji: '🍄' },
]

const FOOD_TYPE_OPTIONS = [
  { value: 'fast_food',   label: 'Fast food',   emoji: '🍔' },
  { value: 'street_food', label: 'Street food', emoji: '🥡' },
  { value: 'bbq',         label: 'BBQ',         emoji: '🔥' },
  { value: 'hotpot',      label: 'Hot pot',     emoji: '🍲' },
  { value: 'buffet',      label: 'Buffet',      emoji: '🍽️' },
  { value: 'noodles',     label: 'Noodles',     emoji: '🍜' },
  { value: 'congee',      label: 'Congee',      emoji: '🥣' },
  { value: 'dumplings',   label: 'Dumplings',   emoji: '🥟' },
  { value: 'korean_bbq',  label: 'Korean BBQ',  emoji: '🥩' },
]

const PRICE_OPTIONS = [
  { value: '0-20', label: '$0–20', level: 1 },
  { value: '20-40', label: '$20–40', level: 2 },
  { value: '40-60', label: '$40–60', level: 3 },
  { value: '60+', label: '$60+', level: 4 },
]

const NUTRITION_OPTIONS = [
  { value: 'low_fat', label: 'Low-fat', emoji: '💧' },
  { value: 'low_sugar', label: 'Low-sugar', emoji: '🍬' },
  { value: 'low_sodium', label: 'Low-sodium', emoji: '🧂' },
  { value: 'no_added_oil', label: 'Low oil', emoji: '🫙' },
]

const RATING_OPTIONS = [
  { value: 4.5, label: '4.5+ ⭐' },
  { value: 4.0, label: '4.0+ ⭐' },
  { value: 3.5, label: '3.5+ ⭐' },
]

const SORT_OPTIONS = [
  { value: 'default', label: 'Best match' },
  { value: 'rating_first', label: 'Highest rated' },
  { value: 'distance_first', label: 'Nearest first' },
  { value: 'price_asc', label: 'Cheapest first' },
]

const DISTANCE_OPTIONS = [
  { value: 0.5, label: '< 500m' },
  { value: 1, label: '< 1 km' },
  { value: 3, label: '< 3 km' },
  { value: 5, label: '< 5 km' },
]

const DIET_RESTRICTION_OPTIONS: {
  value: string
  label: string
  emoji: string
  dietLabel?: DietLabel
}[] = [
  { value: 'vegetarian', label: 'Vegetarian', emoji: '🥗', dietLabel: 'vegetarian' },
  { value: 'vegan', label: 'Vegan', emoji: '🌿', dietLabel: 'vegan' },
  { value: 'halal', label: 'Halal', emoji: '☪️', dietLabel: 'halal' },
  { value: 'kosher', label: 'Kosher', emoji: '✡️', dietLabel: 'kosher' },
  { value: 'keto', label: 'Keto', emoji: '🥑', dietLabel: 'keto' },
  { value: 'low-carb', label: 'Low-carb', emoji: '🥦', dietLabel: 'low-carb' },
  { value: 'high-protein', label: 'High-protein', emoji: '💪', dietLabel: 'high-protein' },
]

const ALLERGY_OPTIONS: {
  value: string
  label: string
  emoji: string
  dietLabel?: DietLabel
}[] = [
  { value: 'peanut-free', label: 'Peanut-free', emoji: '🥜' },
  { value: 'dairy-free', label: 'Dairy-free', emoji: '🥛', dietLabel: 'dairy-free' },
  { value: 'gluten-free', label: 'Gluten-free', emoji: '🌾', dietLabel: 'gluten-free' },
  { value: 'seafood-free', label: 'Seafood-free', emoji: '🦐' },
  { value: 'soy-free', label: 'Soy-free', emoji: '🫘' },
  { value: 'no_spicy', label: 'No spicy', emoji: '🌶️' },
]

const ALLERGY_DIET_LABELS: DietLabel[] = ['dairy-free', 'gluten-free']

// ── Types ──────────────────────────────────────────────────────────────────

export interface FilterState {
  // URL-synced (sent to backend)
  dietLabels: DietLabel[]
  priceLevels: number[]
  sortMode: string
  // Local-only (UI state; backend extension needed)
  cuisineTypes: string[]
  foodTypes: string[]
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
  cuisineTypes: [],
  foodTypes: [],
  calorieRange: null,
  nutritionLabels: [],
  minRating: null,
  maxDistanceKm: null,
  extraDietRestrictions: [],
  allergyRestrictions: [],
  priceRange: null,
}

interface FilterBarProps {
  cities: City[]
  selectedCity: string | null
  onCityChange: (id: string) => void
  locAvailable: boolean
  locLoading: boolean
  onGetLocation: () => void
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
  if (lo === 0) return `≤$${hi}`
  if (hi >= 200) return `≥$${lo}`
  return `$${lo}–${hi}`
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
  const isDefault = label === 'Best match'
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
        <span>Sort: {label}</span>
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
    return <Text type="secondary" style={{ fontSize: 13 }}>All options selected ✓</Text>
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
  cities,
  selectedCity,
  onCityChange,
  locAvailable,
  locLoading,
  onGetLocation,
  filters,
  onFilterChange,
  hideLocation = false,
}: FilterBarProps) {
  const [openGroup, setOpenGroup] = useState<string | null>(null)
  const [calSlider, setCalSlider] = useState<[number, number]>([0, 800])
  const [priceSlider, setPriceSlider] = useState<[number, number]>([0, 100])
  const [distSlider, setDistSlider] = useState<number>(5)
  const [ratingSlider, setRatingSlider] = useState<number>(4.0)

  useEffect(() => {
    if (filters.calorieRange === null) setCalSlider([0, 800])
    else setCalSlider(filters.calorieRange)
  }, [filters.calorieRange])

  useEffect(() => {
    if (filters.priceRange === null) setPriceSlider([0, 100])
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

  const cuisineContent = (
    <div>
      <Text style={{ fontSize: 11, color: '#AAB4B4', display: 'block', marginBottom: 10, fontWeight: 600, letterSpacing: 0.8 }}>
        REGIONAL CUISINE
      </Text>
      <ToggleChipGrid
        options={CUISINE_OPTIONS}
        selected={filters.cuisineTypes}
        color="#E65100"
        onToggle={(v) => {
          const next = filters.cuisineTypes.includes(v)
            ? filters.cuisineTypes.filter((c) => c !== v)
            : [...filters.cuisineTypes, v]
          onFilterChange({ cuisineTypes: next })
        }}
        onClear={() => onFilterChange({ cuisineTypes: [] })}
      />
    </div>
  )

  const foodTypeContent = (
    <div>
      <Text style={{ fontSize: 11, color: '#AAB4B4', display: 'block', marginBottom: 10, fontWeight: 600, letterSpacing: 0.8 }}>
        FOOD TYPE
      </Text>
      <ToggleChipGrid
        options={FOOD_TYPE_OPTIONS}
        selected={filters.foodTypes}
        color="#F06292"
        onToggle={(v) => {
          const next = filters.foodTypes.includes(v)
            ? filters.foodTypes.filter((f) => f !== v)
            : [...filters.foodTypes, v]
          onFilterChange({ foodTypes: next })
        }}
        onClear={() => onFilterChange({ foodTypes: [] })}
      />
    </div>
  )

  const allergyContent = (
    <div>
      <Text style={{ fontSize: 11, color: '#AAB4B4', display: 'block', marginBottom: 10, fontWeight: 600, letterSpacing: 0.8 }}>
        ALLERGENS / AVOIDANCES
      </Text>
      <ToggleChipGrid
        options={ALLERGY_OPTIONS}
        selected={ALLERGY_OPTIONS
          .filter((o) => (o.dietLabel ? filters.dietLabels.includes(o.dietLabel) : filters.allergyRestrictions.includes(o.value)))
          .map((o) => o.value)}
        color="#E85454"
        onToggle={(v) => {
          const opt = ALLERGY_OPTIONS.find((o) => o.value === v)
          if (!opt) return
          if (opt.dietLabel) {
            const next = filters.dietLabels.includes(opt.dietLabel)
              ? filters.dietLabels.filter((d) => d !== opt.dietLabel)
              : [...filters.dietLabels, opt.dietLabel]
            onFilterChange({ dietLabels: next })
          } else {
            const next = filters.allergyRestrictions.includes(v)
              ? filters.allergyRestrictions.filter((r) => r !== v)
              : [...filters.allergyRestrictions, v]
            onFilterChange({ allergyRestrictions: next })
          }
        }}
        onClear={() => onFilterChange({
          dietLabels: filters.dietLabels.filter((d) => !ALLERGY_DIET_LABELS.includes(d)),
          allergyRestrictions: [],
        })}
      />
    </div>
  )

  const priceContent = (
    <div>
      <Text style={{ fontSize: 11, color: '#AAB4B4', display: 'block', marginBottom: 10, fontWeight: 600, letterSpacing: 0.8 }}>
        PRICE RANGE
      </Text>
      <div style={{ paddingRight: 6, marginBottom: 4 }}>
        <Slider
          range
          min={0}
          max={200}
          step={5}
          value={priceSlider}
          onChange={(v) => setPriceSlider(v as [number, number])}
          onChangeComplete={(v) => onFilterChange({ priceRange: v as [number, number] })}
          tooltip={{ formatter: (v) => `$${v}` }}
          styles={{
            track: { background: '#1565C0' },
            handle: { borderColor: '#1565C0' },
          }}
        />
        <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: -8, marginBottom: 8 }}>
          <Text type="secondary" style={{ fontSize: 11 }}>${priceSlider[0]}</Text>
          <Text type="secondary" style={{ fontSize: 11 }}>${priceSlider[1]}</Text>
        </div>
      </div>
      <div style={{ display: 'flex', gap: 6, marginBottom: 16, flexWrap: 'wrap' as const }}>
        {([[0, 30], [0, 50], [0, 80]] as [number, number][]).map(([lo, hi]) => (
          <button
            key={hi}
            onClick={() => { const r: [number, number] = [lo, hi]; setPriceSlider(r); onFilterChange({ priceRange: r }) }}
            style={{
              padding: '3px 10px', borderRadius: 6, border: '1.5px solid #E8E0D5',
              background: '#fff', fontSize: 12, cursor: 'pointer', outline: 'none', color: '#6B7A7A',
            }}
          >
            ≤${hi}
          </button>
        ))}
        {filters.priceRange && (
          <button
            onClick={() => { setPriceSlider([0, 100]); onFilterChange({ priceRange: null }) }}
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
        CALORIE RANGE
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
        DIETARY LABELS
      </Text>
      <ToggleChipGrid
        options={NUTRITION_OPTIONS}
        selected={filters.nutritionLabels}
        color="#6A1B9A"
        onToggle={(v) => {
          const next = filters.nutritionLabels.includes(v)
            ? filters.nutritionLabels.filter((n) => n !== v)
            : [...filters.nutritionLabels, v]
          onFilterChange({ nutritionLabels: next })
        }}
        onClear={() => onFilterChange({ nutritionLabels: [] })}
      />
    </div>
  )

  const ratingContent = (
    <div>
      <Text style={{ fontSize: 11, color: '#AAB4B4', display: 'block', marginBottom: 10, fontWeight: 600, letterSpacing: 0.8 }}>
        MINIMUM RATING
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
        {[3.5, 4.0, 4.5].map((v) => (
          <button
            key={v}
            onClick={() => { setRatingSlider(v); onFilterChange({ minRating: v }) }}
            style={{
              padding: '3px 10px', borderRadius: 6, border: '1.5px solid #E8E0D5',
              background: '#fff', fontSize: 12, cursor: 'pointer', outline: 'none', color: '#6B7A7A',
            }}
          >
            {v}+ ⭐
          </button>
        ))}
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
        SORT BY
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
      {!locAvailable ? (
        <div style={{ textAlign: 'center' as const }}>
          <Text type="secondary" style={{ fontSize: 13, display: 'block', marginBottom: 10 }}>
            📍 Allow location to filter by distance
          </Text>
          <Button size="small" type="link" onClick={onGetLocation}>
            Enable location →
          </Button>
        </div>
      ) : (
        <>
          <Text style={{ fontSize: 11, color: '#AAB4B4', display: 'block', marginBottom: 10, fontWeight: 600, letterSpacing: 0.8 }}>
            MAXIMUM DISTANCE
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
        DIETARY RESTRICTIONS
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

  const cuisineCount = filters.cuisineTypes.length
  const foodTypeCount = filters.foodTypes.length
  const priceCount = filters.priceRange ? 1 : 0
  const healthCount = (filters.calorieRange ? 1 : 0) + filters.nutritionLabels.length
  const ratingCount = filters.minRating !== null ? 1 : 0
  const sortCount = 0 // sort shown inline in button, not as a chip
  const distanceCount = filters.maxDistanceKm !== null ? 1 : 0
  const allergyCount = filters.allergyRestrictions.length + filters.dietLabels.filter((d) => ALLERGY_DIET_LABELS.includes(d)).length
  const dietCount = filters.dietLabels.filter((d) => !ALLERGY_DIET_LABELS.includes(d)).length + filters.extraDietRestrictions.length

  const hasActive =
    cuisineCount + foodTypeCount + priceCount + healthCount + ratingCount + sortCount + distanceCount + allergyCount + dietCount > 0

  // ── Render ──────────────────────────────────────────────────────────────────

  return (
    <div>
      {/* Row 1: Location (if shown) + Health, Diet, Allergies, Food Type, Cuisine */}
      <div
        style={{
          display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6,
          overflowX: 'auto' as const, scrollbarWidth: 'none' as any, msOverflowStyle: 'none' as any,
        }}
      >
        {!hideLocation && (
          <>
            <div style={{ display: 'flex', gap: 6, alignItems: 'center', flexShrink: 0 }}>
              <Select
                value={selectedCity}
                onChange={onCityChange}
                style={{ width: 96 }}
                size="middle"
                options={cities.map((c) => ({ value: c.id, label: c.label }))}
                suffixIcon={<EnvironmentOutlined style={{ fontSize: 12 }} />}
                placeholder="City"
              />
              <Tooltip title={locAvailable ? 'Use my current location' : 'Location access denied — check browser settings'}>
                <Button
                  icon={<AimOutlined />}
                  size="middle"
                  onClick={onGetLocation}
                  loading={locLoading}
                  disabled={!locAvailable}
                  style={{ borderColor: locAvailable ? PRIMARY_COLOR : '#E8E0D5', color: locAvailable ? PRIMARY_COLOR : '#C0BDB8', fontWeight: 400 }}
                >
                  Near me
                </Button>
              </Tooltip>
            </div>
            <div style={{ width: 1, height: 22, background: '#E8E0D5', flexShrink: 0, margin: '0 2px' }} />
          </>
        )}
        <GroupBtn emoji="🥗" label="Health" activeCount={healthCount} isOpen={openGroup === 'health'} onToggle={toggle('health')} content={healthContent} />
        <GroupBtn emoji="🌿" label="Diet" activeCount={dietCount} isOpen={openGroup === 'diet'} onToggle={toggle('diet')} content={dietContent} />
        <GroupBtn emoji="⚠️" label="Allergies" activeCount={allergyCount} isOpen={openGroup === 'allergies'} onToggle={toggle('allergies')} content={allergyContent} />
        <GroupBtn emoji="🍽️" label="Food Type" activeCount={foodTypeCount} isOpen={openGroup === 'foodtype'} onToggle={toggle('foodtype')} content={foodTypeContent} />
        <GroupBtn emoji="🥢" label="Cuisine" activeCount={cuisineCount} isOpen={openGroup === 'cuisine'} onToggle={toggle('cuisine')} content={cuisineContent} />
      </div>

      {/* Row 2: Sort By, Distance, Rating, Price */}
      <div
        style={{
          display: 'flex', alignItems: 'center', gap: 8,
          overflowX: 'auto' as const, scrollbarWidth: 'none' as any, msOverflowStyle: 'none' as any,
        }}
      >
        <SortBtn
          label={SORT_OPTIONS.find((s) => s.value === filters.sortMode)?.label ?? 'Best match'}
          isOpen={openGroup === 'sort'}
          onToggle={toggle('sort')}
          content={sortContent}
        />
        <GroupBtn emoji="📍" label="Distance" activeCount={distanceCount} isOpen={openGroup === 'distance'} onToggle={toggle('distance')} content={distanceContent} disabled={!locAvailable} />
        <GroupBtn emoji="⭐" label="Rating" activeCount={ratingCount} isOpen={openGroup === 'rating'} onToggle={toggle('rating')} content={ratingContent} />
        <GroupBtn emoji="$" label="Price" activeCount={priceCount} isOpen={openGroup === 'price'} onToggle={toggle('price')} content={priceContent} />
      </div>

      {/* Active filter chips */}
      {hasActive && (
        <div style={{ display: 'flex', flexWrap: 'wrap' as const, gap: 6, marginTop: 10, alignItems: 'center' }}>
          {/* Health (purple) */}
          {filters.calorieRange && (
            <ActiveChip label={`🔥 ${calLabel(filters.calorieRange)}`} color="#6A1B9A" bg="#F3E5F5"
              onRemove={() => onFilterChange({ calorieRange: null })} />
          )}
          {filters.nutritionLabels.map((value) => {
            const opt = NUTRITION_OPTIONS.find((n) => n.value === value)
            if (!opt) return null
            return (
              <ActiveChip key={`nutrition-${value}`} label={`${opt.emoji} ${opt.label}`} color="#6A1B9A" bg="#F3E5F5"
                onRemove={() => onFilterChange({ nutritionLabels: filters.nutritionLabels.filter((n) => n !== value) })} />
            )
          })}
          {/* Diet (green) */}
          {filters.dietLabels.filter((d) => !ALLERGY_DIET_LABELS.includes(d)).map((label) => {
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
          {filters.dietLabels.filter((d) => ALLERGY_DIET_LABELS.includes(d)).map((label) => {
            const opt = ALLERGY_OPTIONS.find((o) => o.value === label)
            if (!opt) return null
            return (
              <ActiveChip key={`allergy-dl-${label}`} label={`${opt.emoji} ${opt.label}`} color="#E85454" bg="#FFF0F0"
                onRemove={() => onFilterChange({ dietLabels: filters.dietLabels.filter((d) => d !== label) })} />
            )
          })}
          {filters.allergyRestrictions.map((value) => {
            const opt = ALLERGY_OPTIONS.find((o) => o.value === value)
            if (!opt) return null
            return (
              <ActiveChip key={`allergy-${value}`} label={`${opt.emoji} ${opt.label}`} color="#E85454" bg="#FFF0F0"
                onRemove={() => onFilterChange({ allergyRestrictions: filters.allergyRestrictions.filter((r) => r !== value) })} />
            )
          })}
          {/* Food Type (pink) */}
          {filters.foodTypes.map((value) => {
            const opt = FOOD_TYPE_OPTIONS.find((f) => f.value === value)
            if (!opt) return null
            return (
              <ActiveChip key={`foodtype-${value}`} label={`${opt.emoji} ${opt.label}`} color="#F06292" bg="#FCE4EC"
                onRemove={() => onFilterChange({ foodTypes: filters.foodTypes.filter((f) => f !== value) })} />
            )
          })}
          {/* Cuisine (orange) */}
          {filters.cuisineTypes.map((value) => {
            const opt = CUISINE_OPTIONS.find((c) => c.value === value)
            if (!opt) return null
            return (
              <ActiveChip key={`cuisine-${value}`} label={`${opt.emoji} ${opt.label}`} color="#E65100" bg="#FFF3E0"
                onRemove={() => onFilterChange({ cuisineTypes: filters.cuisineTypes.filter((c) => c !== value) })} />
            )
          })}
          {/* Sort is shown inline in the Sort button — no chip here */}
          {/* Distance (teal) */}
          {filters.maxDistanceKm !== null && (
            <ActiveChip label={`📍 ${DISTANCE_OPTIONS.find((d) => d.value === filters.maxDistanceKm)?.label}`} color="#00838F" bg="#E0F7FA"
              onRemove={() => onFilterChange({ maxDistanceKm: null })} />
          )}
          {/* Rating (amber) */}
          {filters.minRating !== null && (
            <ActiveChip label={`⭐ ${filters.minRating}+`} color="#F57F17" bg="#FFF8E1"
              onRemove={() => onFilterChange({ minRating: null })} />
          )}
          {/* Price (blue) */}
          {filters.priceRange && (
            <ActiveChip label={`$ ${priceLabel(filters.priceRange)}`} color="#1565C0" bg="#E3F2FD"
              onRemove={() => onFilterChange({ priceRange: null })} />
          )}
          <Button
            size="small"
            type="text"
            style={{ color: '#AAB4B4', fontSize: 12 }}
            onClick={() =>
              onFilterChange({
                dietLabels: [], priceLevels: [], sortMode: 'default',
                cuisineTypes: [], foodTypes: [], calorieRange: null, nutritionLabels: [],
                minRating: null, maxDistanceKm: null, extraDietRestrictions: [],
                allergyRestrictions: [], priceRange: null,
              })
            }
          >
            Clear all
          </Button>
        </div>
      )}
    </div>
  )
}
