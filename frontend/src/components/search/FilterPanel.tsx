import { Checkbox, Collapse, Select, Slider, Typography } from 'antd'
import { ALL_DIET_LABELS, DIET_LABEL_META, PRICE_LEVEL_META, SORT_MODES } from '@/constants'
import { DietBadge } from '@/components/common/DietBadge'
import type { DietLabel } from '@/types'

const { Text } = Typography

interface Props {
  dietLabels: DietLabel[]
  priceLevels: number[]
  sortMode: string
  facets?: {
    diet_labels: Record<string, number>
    price_level: Record<string, number>
  }
  onDietChange: (labels: DietLabel[]) => void
  onPriceChange: (levels: number[]) => void
  onSortChange: (mode: string) => void
}

export function FilterPanel({
  dietLabels,
  priceLevels,
  sortMode,
  facets,
  onDietChange,
  onPriceChange,
  onSortChange,
}: Props) {
  const toggleDiet = (label: DietLabel) => {
    const next = dietLabels.includes(label)
      ? dietLabels.filter((l) => l !== label)
      : [...dietLabels, label]
    onDietChange(next)
  }

  const togglePrice = (level: number) => {
    const next = priceLevels.includes(level)
      ? priceLevels.filter((p) => p !== level)
      : [...priceLevels, level]
    onPriceChange(next)
  }

  return (
    <div style={{ background: '#fff', borderRadius: 8, padding: 16 }}>
      {/* 排序 */}
      <div style={{ marginBottom: 16 }}>
        <Text strong>排序方式</Text>
        <Select
          value={sortMode}
          onChange={onSortChange}
          style={{ width: '100%', marginTop: 8 }}
          options={SORT_MODES}
        />
      </div>

      <Collapse
        ghost
        defaultActiveKey={['diet', 'price']}
        items={[
          {
            key: 'diet',
            label: <Text strong>饮食标签</Text>,
            children: (
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
                {ALL_DIET_LABELS.map((label) => {
                  const count = facets?.diet_labels[label]
                  return (
                    <div
                      key={label}
                      onClick={() => toggleDiet(label)}
                      style={{
                        cursor: 'pointer',
                        opacity: count === 0 ? 0.4 : 1,
                      }}
                    >
                      <DietBadge
                        label={label}
                        size="small"
                      />
                      {count !== undefined && (
                        <Text type="secondary" style={{ fontSize: 11 }}>
                          {' '}({count})
                        </Text>
                      )}
                      {dietLabels.includes(label) && (
                        <span style={{ color: '#2D9B5A', fontSize: 11, marginLeft: 2 }}>✓</span>
                      )}
                    </div>
                  )
                })}
              </div>
            ),
          },
          {
            key: 'price',
            label: <Text strong>价格区间</Text>,
            children: (
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
                {[1, 2, 3, 4].map((level) => {
                  const meta = PRICE_LEVEL_META[level]
                  const count = facets?.price_level[String(level)]
                  const active = priceLevels.includes(level)
                  return (
                    <Checkbox
                      key={level}
                      checked={active}
                      onChange={() => togglePrice(level)}
                      style={{ fontSize: 13 }}
                    >
                      {meta.label}
                      {count !== undefined && (
                        <Text type="secondary" style={{ fontSize: 11 }}>
                          {' '}({count})
                        </Text>
                      )}
                    </Checkbox>
                  )
                })}
              </div>
            ),
          },
        ]}
      />
    </div>
  )
}
