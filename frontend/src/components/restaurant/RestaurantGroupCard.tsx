import { useState } from 'react'
import { Button, Space, Tag, Typography } from 'antd'
import { DownOutlined, EnvironmentOutlined, PlusOutlined, UpOutlined } from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'
import { AllergenWarning } from '@/components/common/AllergenWarning'
import { AddLogModal } from '@/components/diet/AddLogModal'
import { useAuthStore } from '@/stores/authStore'
import { PRICE_LEVEL_META } from '@/constants'
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
  if (q && item.name?.toLowerCase().includes(q.toLowerCase())) {
    score += 2
  }
  return score
}

const MAX_VISIBLE = 6

function DishPlaceholder() {
  return (
    <div style={{
      width: 52, height: 52, borderRadius: 8, flexShrink: 0,
      background: '#F0EAE0', display: 'flex', flexDirection: 'column',
      alignItems: 'center', justifyContent: 'center', gap: 1,
    }}>
      <span style={{ fontSize: 18 }}>🍽️</span>
      <span style={{ fontSize: 8, color: '#C0BDB8' }}>No photo</span>
    </div>
  )
}

export function RestaurantGroupCard({ restaurant: r, activeDietLabels = [], query = '', onDietClick }: Props) {
  const navigate = useNavigate()
  const { user } = useAuthStore()
  const [showAll, setShowAll] = useState(false)
  const [logItem, setLogItem] = useState<MenuItem | null>(null)

  const handleLogClick = (e: React.MouseEvent, item: MenuItem) => {
    e.stopPropagation()
    if (!user) { navigate('/login'); return }
    setLogItem(item)
  }

  // Prefer server-side matched_dishes (ES inner_hits) — already filtered & price-sorted.
  // Fall back to client-side filtering when server didn't return inner_hits
  // (e.g. empty query browsing).
  const matchedItems: MenuItem[] = r.matched_dishes && r.matched_dishes.length > 0
    ? r.matched_dishes
    : (activeDietLabels.length > 0 || query)
      ? (r.menu_items ?? [])
          .filter((item) => dishMatchScore(item, activeDietLabels, query) > 0)
          .sort((a, b) => dishMatchScore(b, activeDietLabels, query) - dishMatchScore(a, activeDietLabels, query))
      : []

  const hasMore = matchedItems.length > MAX_VISIBLE

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
          {/* Restaurant thumbnail or placeholder */}
          {r.images?.[0] ? (
            <img
              src={r.images[0]}
              alt={r.name}
              style={{ width: 56, height: 56, objectFit: 'cover', borderRadius: 8, flexShrink: 0 }}
              onError={(e) => {
                const el = e.currentTarget
                el.style.display = 'none'
                const ph = el.nextElementSibling as HTMLElement
                if (ph) ph.style.display = 'flex'
              }}
            />
          ) : null}
          <div style={{
            width: 56, height: 56, borderRadius: 8, flexShrink: 0,
            background: '#F0EAE0', display: r.images?.[0] ? 'none' : 'flex',
            alignItems: 'center', justifyContent: 'center', flexDirection: 'column', gap: 1,
          }}>
            <span style={{ fontSize: 22 }}>🍽️</span>
            <span style={{ fontSize: 8, color: '#C0BDB8' }}>No photo</span>
          </div>

          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
              <Title level={5} style={{ margin: 0, color: '#1E2A2A', fontSize: 15, lineHeight: 1.3 }} ellipsis>
                {r.name_en || r.name}
              </Title>
              <Space size={6} style={{ flexShrink: 0, marginLeft: 8 }}>
                {r.rating ? (
                  <Text style={{ fontSize: 13, color: '#F5A623', fontWeight: 600 }}>
                    ★ {r.rating.toFixed(1)}
                    {r.rating_count != null && r.rating_count > 0 && (
                      <Text type="secondary" style={{ fontSize: 11, fontWeight: 400, marginLeft: 3 }}>
                        ({r.rating_count})
                      </Text>
                    )}
                  </Text>
                ) : null}
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
              {r.price_level ? (
                <Tag color="geekblue" style={{ fontSize: 11, borderRadius: 6, margin: 0 }}>
                  {PRICE_LEVEL_META[r.price_level]?.icon}
                </Tag>
              ) : null}
            </Space>
          </div>
        </div>
      </div>

      {/* Matched dishes */}
      {matchedItems.length > 0 && (
        <div style={{ borderTop: '1px solid #F0EAE0' }}>
          {matchedItems.map((item, i) => (
            <div
              key={item.item_id ?? i}
              style={{
                padding: '10px 14px',
                background: i % 2 === 0 ? '#FDFAF7' : '#F7F3EE',
                borderBottom: i < matchedItems.length - 1 ? '1px solid #EDE5D8' : 'none',
                display: !showAll && i >= MAX_VISIBLE ? 'none' : 'flex',
                gap: 10,
                alignItems: 'flex-start',
              }}
            >
              <DishPlaceholder />

              <div style={{ flex: 1, minWidth: 0, display: 'flex', gap: 8, alignItems: 'flex-start' }}>
                {/* Left: name + match + macros + labels */}
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6, overflow: 'hidden' }}>
                    <Text style={{ fontSize: 14, color: '#1E2A2A', fontWeight: 500, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' as const }}>
                      {item.name}
                    </Text>
                    <span style={{ fontSize: 10, color: '#2D9B5A', background: '#E8F5E9', padding: '1px 7px', borderRadius: 8, fontWeight: 600, flexShrink: 0 }}>
                      ✓ match
                    </span>
                  </div>

                  {(item.calories || item.protein || item.fat || item.carbs) && (
                    <div style={{ marginTop: 3, fontSize: 11 }}>
                      {item.calories && (
                        <Text strong style={{ fontSize: 11, color: '#fa8c16' }}>{item.calories} kcal</Text>
                      )}
                      {(item.protein || item.fat || item.carbs) && (
                        <Text type="secondary" style={{ fontSize: 11 }}>
                          {item.calories ? '  ·  ' : ''}
                          {[
                            item.protein && `P ${item.protein}g`,
                            item.fat && `F ${item.fat}g`,
                            item.carbs && `C ${item.carbs}g`,
                          ].filter(Boolean).join(' · ')}
                        </Text>
                      )}
                    </div>
                  )}

                  {item.diet_labels && item.diet_labels.length > 0 && (
                    <div style={{ display: 'flex', flexWrap: 'wrap' as const, gap: 3, marginTop: 4 }}>
                      {item.diet_labels.slice(0, 5).map((label) => (
                        <span key={label} style={{ fontSize: 10, padding: '1px 6px', borderRadius: 8, background: '#F0F0F0', color: '#555', fontWeight: 500 }}>
                          {label}
                        </span>
                      ))}
                    </div>
                  )}
                </div>

                {/* Right: price + Log button */}
                <div style={{ flexShrink: 0, display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 6 }}>
                  {item.price !== undefined && (
                    <Text style={{ fontSize: 13, color: '#1E2A2A', fontWeight: 500 }}>
                      ${item.price}
                    </Text>
                  )}
                  <Button
                    size="small"
                    icon={<PlusOutlined />}
                    onClick={(e) => handleLogClick(e, item)}
                    style={{ fontSize: 11, height: 22, borderColor: '#2D9B5A', color: '#2D9B5A' }}
                  >
                    Log
                  </Button>
                </div>
              </div>
            </div>
          ))}

          {hasMore && (
            <button
              onClick={(e) => { e.stopPropagation(); setShowAll((v) => !v) }}
              style={{
                width: '100%', padding: '8px 16px', border: 'none',
                background: '#F7F3EE', borderTop: '1px solid #E8E0D5',
                cursor: 'pointer', color: '#6B7A7A', fontSize: 13,
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                gap: 5, outline: 'none',
              }}
            >
              {showAll
                ? <span><UpOutlined style={{ fontSize: 10 }} /> Show fewer</span>
                : <span><DownOutlined style={{ fontSize: 10 }} /> {matchedItems.length - MAX_VISIBLE} more matches</span>
              }
            </button>
          )}
        </div>
      )}
      {logItem && (
        <AddLogModal
          open={!!logItem}
          logDate={new Date().toISOString().slice(0, 10)}
          prefill={{
            name: logItem.name,
            calories: logItem.calories,
            protein_g: logItem.protein,
            fat_g: logItem.fat,
            carb_g: logItem.carbs,
          }}
          onClose={() => setLogItem(null)}
          onAdded={() => setLogItem(null)}
        />
      )}
    </article>
  )
}
