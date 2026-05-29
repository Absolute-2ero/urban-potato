import { useState } from 'react'
import { Space, Tag, Typography } from 'antd'
import { DownOutlined, EnvironmentOutlined, UpOutlined } from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'
import { AllergenWarning } from '@/components/common/AllergenWarning'
import { DietBadgeGroup } from '@/components/common/DietBadge'
import { DIET_LABEL_META, PRICE_LEVEL_META } from '@/constants'
import type { DietLabel, MenuItem, Restaurant } from '@/types'

const { Text, Title } = Typography

interface Props {
  restaurant: Restaurant
  activeDietLabels?: DietLabel[]
  query?: string
  onDietClick?: (label: DietLabel) => void
}

function formatDistance(m?: number) {
  if (m === undefined) return ''
  return m < 1000 ? `${m}m` : `${(m / 1000).toFixed(1)}km`
}

function dishMatchScore(item: MenuItem, dietLabels: DietLabel[], q: string): number {
  let score = 0
  if (dietLabels.length > 0 && item.diet_labels) {
    score += item.diet_labels.filter((d) => dietLabels.includes(d)).length * 3
  }
  if (q && item.name.toLowerCase().includes(q.toLowerCase())) {
    score += 2
  }
  return score
}

const INITIAL_SHOW = 3

export function RestaurantGroupCard({ restaurant: r, activeDietLabels = [], query = '', onDietClick }: Props) {
  const navigate = useNavigate()
  const [expanded, setExpanded] = useState(false)

  const sortedItems = [...(r.menu_items ?? [])].sort(
    (a, b) => dishMatchScore(b, activeDietLabels, query) - dishMatchScore(a, activeDietLabels, query)
  )
  const visibleItems = expanded ? sortedItems : sortedItems.slice(0, INITIAL_SHOW)
  const hasMore = sortedItems.length > INITIAL_SHOW

  return (
    <article
      aria-label={r.name}
      style={{
        background: '#fff',
        borderRadius: 12,
        border: '1px solid #E8E0D5',
        boxShadow: '0 2px 8px rgba(30,42,42,0.06)',
        marginBottom: 16,
        overflow: 'hidden',
      }}
    >
      {/* Restaurant header */}
      <div
        onClick={() => navigate(`/restaurants/${r.restaurant_id}`)}
        style={{ padding: '14px 16px 12px', cursor: 'pointer' }}
      >
        <AllergenWarning allergens={r._allergen_warning ?? []} />

        <div style={{ display: 'flex', gap: 12 }}>
          {r.images?.[0] && (
            <img
              src={r.images[0]}
              alt={r.name}
              style={{
                width: 72,
                height: 72,
                objectFit: 'cover',
                borderRadius: 8,
                flexShrink: 0,
              }}
              onError={(e) => { (e.currentTarget as HTMLImageElement).style.display = 'none' }}
            />
          )}

          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
              <Title
                level={5}
                style={{ margin: 0, color: '#1E2A2A', fontSize: 15, lineHeight: 1.3 }}
                ellipsis
              >
                {r.name}
              </Title>
              <Space size={8} style={{ flexShrink: 0, marginLeft: 8 }}>
                {r.rating && (
                  <Text style={{ fontSize: 13, color: '#F5A623', fontWeight: 600 }}>
                    ★ {r.rating.toFixed(1)}
                  </Text>
                )}
                {r._distance_m !== undefined && (
                  <Text type="secondary" style={{ fontSize: 12 }}>
                    <EnvironmentOutlined style={{ marginRight: 2 }} />
                    {formatDistance(r._distance_m)}
                  </Text>
                )}
              </Space>
            </div>

            <Space size={4} style={{ marginTop: 4, flexWrap: 'wrap' as const }}>
              {r.cuisine_type && (
                <Tag style={{ fontSize: 11, borderRadius: 6, margin: 0 }}>{r.cuisine_type}</Tag>
              )}
              {r.price_level && (
                <Tag color="geekblue" style={{ fontSize: 11, borderRadius: 6, margin: 0 }}>
                  {PRICE_LEVEL_META[r.price_level]?.icon}
                </Tag>
              )}
            </Space>

            {r.diet_labels.length > 0 && (
              <div style={{ marginTop: 6 }}>
                <DietBadgeGroup labels={r.diet_labels} maxVisible={4} onLabelClick={onDietClick} />
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Dish list */}
      {sortedItems.length > 0 && (
        <>
          <div style={{ borderTop: '1px solid #F0EAE0' }}>
            {visibleItems.map((item, i) => {
              const score = dishMatchScore(item, activeDietLabels, query)
              return (
                <div
                  key={item.item_id ?? i}
                  style={{
                    padding: '10px 16px',
                    background: i % 2 === 0 ? '#FDFAF7' : '#F7F3EE',
                    borderBottom: i < visibleItems.length - 1 ? '1px solid #EDE5D8' : 'none',
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    gap: 8,
                  }}
                >
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap' as const }}>
                      <Text
                        style={{
                          fontSize: 14,
                          color: '#1E2A2A',
                          fontWeight: score > 0 ? 500 : 400,
                        }}
                      >
                        {item.name}
                      </Text>
                      {score > 0 && (
                        <span
                          style={{
                            fontSize: 10,
                            color: '#2D9B5A',
                            background: '#E8F5E9',
                            padding: '1px 7px',
                            borderRadius: 8,
                            fontWeight: 600,
                          }}
                        >
                          ✓ match
                        </span>
                      )}
                    </div>
                    {item.diet_labels && item.diet_labels.length > 0 && (
                      <div style={{ marginTop: 3 }}>
                        {item.diet_labels.slice(0, 3).map((l) => {
                          const m = DIET_LABEL_META[l]
                          return m ? (
                            <span
                              key={l}
                              style={{
                                fontSize: 11,
                                color: m.color,
                                background: m.color + '18',
                                padding: '1px 7px',
                                borderRadius: 8,
                                marginRight: 4,
                              }}
                            >
                              {m.emoji} {m.label}
                            </span>
                          ) : null
                        })}
                      </div>
                    )}
                  </div>

                  <div style={{ flexShrink: 0, textAlign: 'right' as const }}>
                    {item.calories !== undefined && (
                      <Text type="secondary" style={{ fontSize: 11, display: 'block' }}>
                        {item.calories} kcal
                      </Text>
                    )}
                    {item.price !== undefined && (
                      <Text style={{ fontSize: 13, color: '#1E2A2A', fontWeight: 500 }}>
                        ¥{item.price}
                      </Text>
                    )}
                  </div>
                </div>
              )
            })}
          </div>

          {hasMore && (
            <button
              onClick={(e) => { e.stopPropagation(); setExpanded(!expanded) }}
              style={{
                width: '100%',
                padding: '9px 16px',
                border: 'none',
                background: '#F7F3EE',
                borderTop: '1px solid #E8E0D5',
                cursor: 'pointer',
                color: '#6B7A7A',
                fontSize: 13,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: 5,
                outline: 'none',
              }}
            >
              {expanded ? (
                <><UpOutlined style={{ fontSize: 10 }} /> Show fewer dishes</>
              ) : (
                <><DownOutlined style={{ fontSize: 10 }} /> Show {sortedItems.length - INITIAL_SHOW} more dishes</>
              )}
            </button>
          )}
        </>
      )}
    </article>
  )
}
