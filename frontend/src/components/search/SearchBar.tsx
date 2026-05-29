import { useEffect, useRef, useState } from 'react'
import { AutoComplete, Button, Input } from 'antd'
import { SearchOutlined } from '@ant-design/icons'
import { autocomplete } from '@/api/search'
import { PRIMARY_COLOR } from '@/constants'

interface Props {
  value: string
  onSearch: (val: string) => void
  onChange?: (val: string) => void  // optional: called on every keystroke for local state
  placeholder?: string
  city?: string
}

export function SearchBar({ value, onSearch, onChange, placeholder, city }: Props) {
  const [inputVal, setInputVal] = useState(value)
  const [options, setOptions] = useState<{ value: string }[]>([])
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  // Sync when external value changes (e.g. back/forward navigation)
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

  return (
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
            icon={<SearchOutlined />}
            style={{ backgroundColor: PRIMARY_COLOR, borderColor: PRIMARY_COLOR }}
          >
            Search
          </Button>
        }
        onSearch={() => onSearch(inputVal)}
      />
    </AutoComplete>
  )
}
