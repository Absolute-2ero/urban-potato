import { useNavigate } from 'react-router-dom'
import { DIET_LABEL_META } from '@/constants'
import type { DietLabel } from '@/types'

const FEATURED: DietLabel[] = [
  'vegan', 'vegetarian', 'halal', 'gluten-free', 'keto',
  'high-protein', 'dairy-free', 'low-calorie', 'organic',
]

interface Props {
  active?: DietLabel[]
  onToggle?: (label: DietLabel) => void
  navigateOnClick?: boolean
}

export function QuickFilterChips({ active = [], onToggle, navigateOnClick = false }: Props) {
  const navigate = useNavigate()

  const handleClick = (label: DietLabel) => {
    if (navigateOnClick) {
      const params = new URLSearchParams()
      params.append('diet', label)
      navigate(`/search?${params.toString()}`)
    } else {
      onToggle?.(label)
    }
  }

  return (
    <div
      style={{
        display: 'flex',
        gap: 8,
        overflowX: 'auto',
        paddingBottom: 2,
        scrollbarWidth: 'none',
        msOverflowStyle: 'none',
      }}
    >
      {FEATURED.map((label) => {
        const meta = DIET_LABEL_META[label]
        const isActive = active.includes(label)
        return (
          <button
            key={label}
            onClick={() => handleClick(label)}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 5,
              padding: '6px 14px',
              borderRadius: 999,
              border: `1.5px solid ${isActive ? meta.color : '#E8E0D5'}`,
              background: isActive ? meta.color + '22' : '#fff',
              color: isActive ? meta.color : '#6B7A7A',
              fontSize: 13,
              fontWeight: isActive ? 600 : 400,
              cursor: 'pointer',
              whiteSpace: 'nowrap',
              transition: 'all 0.15s',
              flexShrink: 0,
              outline: 'none',
            }}
          >
            <span>{meta.emoji}</span>
            <span>{meta.label}</span>
          </button>
        )
      })}
    </div>
  )
}
