import { useRef, useState } from 'react'
import { AutoComplete, Button, Input, Space } from 'antd'
import { SearchOutlined } from '@ant-design/icons'
import { autocomplete } from '@/api/search'
import { PRIMARY_COLOR } from '@/constants'

interface Props {
  value: string
  onChange: (val: string) => void
  onSearch: (val: string) => void
  placeholder?: string
}

export function SearchBar({ value, onChange, onSearch, placeholder }: Props) {
  const [options, setOptions] = useState<{ value: string }[]>([])
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const handleSearch = async (text: string) => {
    onChange(text)
    if (debounceRef.current) clearTimeout(debounceRef.current)
    if (text.length < 1) {
      setOptions([])
      return
    }
    debounceRef.current = setTimeout(async () => {
      try {
        const suggestions = await autocomplete(text)
        setOptions(suggestions.map((s) => ({ value: s })))
      } catch {
        setOptions([])
      }
    }, 200)
  }

  return (
    <AutoComplete
      value={value}
      options={options}
      onSearch={handleSearch}
      onSelect={(val) => { onChange(val); onSearch(val) }}
      style={{ width: '100%' }}
    >
      <Input.Search
        size="large"
        placeholder={placeholder ?? '搜索餐厅、菜系、饮食偏好…'}
        enterButton={
          <Button
            type="primary"
            icon={<SearchOutlined />}
            style={{ backgroundColor: PRIMARY_COLOR, borderColor: PRIMARY_COLOR }}
          >
            搜索
          </Button>
        }
        onSearch={onSearch}
      />
    </AutoComplete>
  )
}
