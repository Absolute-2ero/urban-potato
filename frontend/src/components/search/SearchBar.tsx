import { useEffect, useRef, useState } from 'react'
import { AutoComplete, Button, Input } from 'antd'
import { LoadingOutlined, SearchOutlined, ThunderboltOutlined, AimOutlined } from '@ant-design/icons'
import { autocomplete } from '@/api/search'
import { PRIMARY_COLOR } from '@/constants'

interface Props {
  value: string
  onSearch: (val: string) => void
  onChange?: (val: string) => void
  placeholder?: string
  city?: string
  loading?: boolean
  searchMode?: 'smart' | 'semantic'
  onSearchModeChange?: (mode: 'smart' | 'semantic') => void
}

const MODE_CONFIG = {
  smart: {
    label: 'Smart',
    icon: <ThunderboltOutlined />,
    tip: 'AI extracts intent, location, filters',
    loadingLabel: 'Parsing…',
    color: PRIMARY_COLOR,
  },
  semantic: {
    label: 'Semantic',
    icon: <AimOutlined />,
    tip: 'Meaning-based vector search',
    loadingLabel: 'Searching…',
    color: '#7C3AED',
  },
}

export function SearchBar({
  value,
  onSearch,
  onChange,
  placeholder,
  city,
  loading,
  searchMode = 'smart',
  onSearchModeChange,
}: Props) {
  const [inputVal, setInputVal] = useState(value)
  const [options, setOptions] = useState<{ value: string }[]>([])
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  useEffect(() => { setInputVal(value) }, [value])

  const fetchSuggestions = (text: string) => {
    if (debounceRef.current) clearTimeout(debounceRef.current)
    if (text.length < 1) { setOptions([]); return }
    debounceRef.current = setTimeout(async () => {
      try {
        const suggestions = await autocomplete(text, city)
        setOptions(suggestions.map((s) => ({ value: s })))
      } catch {
        setOptions([])
      }
    }, 200)
  }

  const mode = MODE_CONFIG[searchMode]
  const activeColor = mode.color

  return (
    <div>
      <AutoComplete
        value={inputVal}
        options={options}
        onChange={(text) => { setInputVal(text); onChange?.(text); fetchSuggestions(text) }}
        onSelect={(val) => { setInputVal(val); onSearch(val) }}
        style={{ width: '100%' }}
      >
        <Input.Search
          size="large"
          placeholder={placeholder ?? 'Search restaurants, cuisine, dietary preferences…'}
          enterButton={
            <Button
              type="primary"
              icon={loading ? <LoadingOutlined /> : <SearchOutlined />}
              loading={loading}
              style={{ backgroundColor: activeColor, borderColor: activeColor }}
            >
              {loading ? mode.loadingLabel : 'Search'}
            </Button>
          }
          onSearch={() => onSearch(inputVal)}
        />
      </AutoComplete>

      {/* Mode toggle */}
      {onSearchModeChange && (
        <div style={{ display: 'flex', gap: 6, marginTop: 6, alignItems: 'center' }}>
          {(['smart', 'semantic'] as const).map((m) => {
            const cfg = MODE_CONFIG[m]
            const isActive = searchMode === m
            return (
              <button
                key={m}
                onClick={() => onSearchModeChange(m)}
                title={cfg.tip}
                style={{
                  display: 'flex', alignItems: 'center', gap: 4,
                  padding: '2px 10px', borderRadius: 12, fontSize: 12,
                  border: `1.5px solid ${isActive ? cfg.color : '#E8E0D5'}`,
                  background: isActive ? cfg.color + '15' : 'transparent',
                  color: isActive ? cfg.color : '#9BA8A8',
                  cursor: 'pointer', outline: 'none', fontWeight: isActive ? 600 : 400,
                  transition: 'all 0.15s',
                }}
              >
                {cfg.icon}
                {cfg.label}
              </button>
            )
          })}
          <span style={{ fontSize: 11, color: '#B0BABA', marginLeft: 2 }}>{mode.tip}</span>
        </div>
      )}
    </div>
  )
}
