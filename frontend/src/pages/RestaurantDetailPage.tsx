import { useEffect, useState } from 'react'
import { useParams, useNavigate, useLocation } from 'react-router-dom'
import {
  Button, Carousel, Col, Divider, Empty, Rate,
  Row, Skeleton, Space, Tag, Typography,
} from 'antd'
import {
  ArrowLeftOutlined, HeartFilled, HeartOutlined, PhoneOutlined, EnvironmentOutlined, PlusOutlined,
} from '@ant-design/icons'
import { AddLogModal } from '@/components/diet/AddLogModal'
import { getRestaurant } from '@/api/restaurants'
import { useSearchStore } from '@/stores/searchStore'
import { saveRestaurant, unsaveRestaurant, getSavedRestaurants } from '@/api/diet'
import { useAuthStore } from '@/stores/authStore'
import { addRestaurantView } from '@/utils/history'
import { logInteraction } from '@/api/interactions'
import { AllergenWarning } from '@/components/common/AllergenWarning'
import { DietBadgeGroup } from '@/components/common/DietBadge'
import { getPriceLevelMeta } from '@/constants'
import { currencySymbol } from '@/utils/prefs'
import { useLang } from '@/i18n/LanguageContext'
// DietBadgeGroup kept for restaurant-level label display above
import type { Restaurant } from '@/types'

const { Title, Text, Paragraph } = Typography

export default function RestaurantDetailPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const location = useLocation()
  const { user } = useAuthStore()
  const { t } = useLang()
  const { q: searchQ, dietLabels: searchDietLabels, city } = useSearchStore()
  const priceLevelMeta = getPriceLevelMeta(city)
  const sym = currencySymbol(city)
  const noHighlight = !!(location.state as any)?.noHighlight
  const [restaurant, setRestaurant] = useState<Restaurant | null>(null)
  const [loading, setLoading] = useState(true)
  const [saved, setSaved] = useState(false)
  const [logPrefill, setLogPrefill] = useState<{ name: string; calories?: number } | null>(null)

  useEffect(() => {
    if (!id) return
    Promise.all([getRestaurant(id), getSavedRestaurants().catch(() => [] as string[])]).then(
      ([r, savedIds]) => {
        setRestaurant(r)
        setSaved(savedIds.includes(id))
        setLoading(false)
        addRestaurantView(
          {
            id: (crypto.randomUUID?.() ?? Math.random().toString(36).slice(2)),
            restaurantId: r.restaurant_id,
            restaurantName: r.name,
            dishes: r.menu_items?.slice(0, 5).map((item) => item.name) ?? [],
            timestamp: Date.now(),
          },
          user?.id,
        )
        if (user) logInteraction(r.restaurant_id, 'view')
      }
    )
  }, [id])

  const toggleSave = async () => {
    if (!id) return
    if (!user) { navigate('/login'); return }
    if (saved) {
      await unsaveRestaurant(id)
    } else {
      await saveRestaurant(id)
      logInteraction(id, 'save')
    }
    setSaved(!saved)
  }

  if (loading) return <Skeleton active style={{ padding: 24 }} />
  if (!restaurant) return <Empty description="Restaurant not found" />

  const r = restaurant

  return (
    <div style={{ maxWidth: 900, margin: '0 auto', padding: '24px 16px' }}>
      {/* Back button */}
      <div style={{ marginBottom: 12 }}>
        <Button icon={<ArrowLeftOutlined />} onClick={() => navigate(-1)}>{t.rest_back}</Button>
      </div>

      {/* 过敏原警告 */}
      {(r._allergen_warning?.length ?? r.allergens.length) > 0 && (
        <div style={{ marginBottom: 16 }}>
          <AllergenWarning allergens={r._allergen_warning ?? r.allergens} />
        </div>
      )}

      <Row gutter={24}>
        {/* 图片 */}
        <Col xs={24} md={10}>
          {r.images && r.images.length > 0 ? (
            <Carousel autoplay style={{ borderRadius: 12, overflow: 'hidden' }}>
              {r.images.map((src, i) => (
                <div key={i}>
                  <img
                    src={src}
                    alt={r.name}
                    style={{ width: '100%', height: 240, objectFit: 'cover' }}
                  />
                </div>
              ))}
            </Carousel>
          ) : (
            <div style={{
              height: 240, background: '#F0EAE0', borderRadius: 12,
              display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
              gap: 8,
            }}>
              <span style={{ fontSize: 48 }}>🍽️</span>
              <span style={{ fontSize: 13, color: '#AAB4B4' }}>{t.rest_no_photo}</span>
            </div>
          )}
        </Col>

        {/* 基本信息 */}
        <Col xs={24} md={14}>
          <Space direction="vertical" style={{ width: '100%' }} size={12}>
            {/* Title */}
            <Title level={3} style={{ margin: 0 }}>
              {r.name_en || r.name}
            </Title>

            {/* Rating row */}
            {r.rating ? (
              <Space size={4}>
                <Rate disabled value={r.rating} style={{ fontSize: 14 }} />
                <Text style={{ color: '#fa8c16', fontWeight: 600 }}>
                  {r.rating.toFixed(1)}
                </Text>
                {r.rating_count != null && r.rating_count > 0 && (
                  <Text type="secondary" style={{ fontSize: 12 }}>
                    {t.rest_reviews(r.rating_count!)}
                  </Text>
                )}
              </Space>
            ) : null}

            {/* Price level + cuisine row */}
            <Space>
              {r.price_level ? (
                <Tag color="geekblue">{priceLevelMeta[r.price_level]?.label}</Tag>
              ) : null}
              {r.cuisine_type && <Tag>{r.cuisine_type}</Tag>}
            </Space>

            {/* Address */}
            {r.address && (
              <Space size={6}>
                <EnvironmentOutlined style={{ color: '#6B7A7A' }} />
                <Text style={{ fontSize: 13 }}>{r.address}</Text>
              </Space>
            )}

            {/* Phone */}
            {r.phone && (
              <Space size={6}>
                <PhoneOutlined style={{ color: '#6B7A7A' }} />
                <a href={`tel:${r.phone}`} style={{ fontSize: 13 }}>{r.phone}</a>
              </Space>
            )}

            {(() => {
              const desc = r.description?.trim()
              const tags = ((r as any).tags as string[] | undefined)
                ?.filter((t) => t !== '餐饮服务' && t !== '餐饮')
                .slice(0, 3)
              const fallback = !desc && tags?.length ? tags.join(' · ') : null
              return (desc || fallback) ? (
                <Paragraph type="secondary" style={{ fontSize: 13, margin: 0 }}>
                  {desc || fallback}
                </Paragraph>
              ) : null
            })()}

            {/* Save button */}
            <Button
              icon={saved ? <HeartFilled style={{ color: '#ff4d4f' }} /> : <HeartOutlined />}
              onClick={toggleSave}
              style={{ alignSelf: 'flex-start' }}
            >
              {saved ? t.rest_saved : t.rest_save}
            </Button>
          </Space>
        </Col>
      </Row>

      {/* Menu — individual dish cards */}
      {r.menu_items && r.menu_items.length > 0 && (
        <>
          <Divider>{t.rest_menu(r.menu_items.length)}</Divider>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 12 }}>
            {[...r.menu_items].sort((a: any, b: any) => {
              if (noHighlight) return 0
              const isMatchA = (searchDietLabels.length > 0 && a.diet_labels?.some((d: string) => searchDietLabels.includes(d as any))) || (searchQ && a.name?.toLowerCase().includes(searchQ.toLowerCase()))
              const isMatchB = (searchDietLabels.length > 0 && b.diet_labels?.some((d: string) => searchDietLabels.includes(d as any))) || (searchQ && b.name?.toLowerCase().includes(searchQ.toLowerCase()))
              return (isMatchB ? 1 : 0) - (isMatchA ? 1 : 0)
            }).map((item: any, i: number) => {
              const labelMatch = !noHighlight && searchDietLabels.length > 0 && item.diet_labels?.some((d: string) => searchDietLabels.includes(d as any))
              const nameMatch = !noHighlight && !!(searchQ && item.name?.toLowerCase().includes(searchQ.toLowerCase()))
              const isMatch = labelMatch || nameMatch
              return (
                <div
                  key={item.item_id ?? i}
                  style={{
                    background: isMatch ? '#f0faf4' : '#fff',
                    border: `1.5px solid ${isMatch ? '#2D9B5A40' : '#E8E0D5'}`,
                    borderRadius: 10,
                    padding: 12,
                    display: 'flex',
                    gap: 10,
                  }}
                >
                  {/* Dish image placeholder */}
                  <div style={{
                    width: 56, height: 56, borderRadius: 8, flexShrink: 0,
                    background: '#F0EAE0', display: 'flex', flexDirection: 'column',
                    alignItems: 'center', justifyContent: 'center', gap: 1,
                  }}>
                    <span style={{ fontSize: 20 }}>🍽️</span>
                    <span style={{ fontSize: 8, color: '#C0BDB8' }}>No photo</span>
                  </div>

                  <div style={{ flex: 1, minWidth: 0 }}>
                    {/* Name row */}
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 4 }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 5, flexWrap: 'wrap' as const, flex: 1 }}>
                        <Text strong style={{ fontSize: 13, color: '#1E2A2A' }}>{item.name_en || item.name}</Text>
                        {isMatch && (
                          <span style={{
                            fontSize: 10, color: '#2D9B5A', background: '#E8F5E9',
                            padding: '1px 6px', borderRadius: 8, fontWeight: 600,
                          }}>{t.rest_match}</span>
                        )}
                      </div>
                      {item.price && (
                        <Text style={{ fontSize: 13, fontWeight: 600, color: '#1E2A2A', flexShrink: 0 }}>
                          {sym}{item.price}
                        </Text>
                      )}
                    </div>

                    {/* Calories + macros */}
                    {(item.calories > 0 || item.protein > 0 || item.fat > 0 || item.carbs > 0) && (
                      <div style={{ marginTop: 3, fontSize: 11 }}>
                        {item.calories > 0 && (
                          <Text strong style={{ fontSize: 11, color: '#fa8c16' }}>{item.calories} kcal</Text>
                        )}
                        {(item.protein > 0 || item.fat > 0 || item.carbs > 0) && (
                          <Text type="secondary" style={{ fontSize: 11 }}>
                            {item.calories > 0 ? '  ·  ' : ''}
                            {[
                              item.protein > 0 && `P ${item.protein}g`,
                              item.fat > 0 && `F ${item.fat}g`,
                              item.carbs > 0 && `C ${item.carbs}g`,
                            ].filter(Boolean).join(' · ')}
                          </Text>
                        )}
                      </div>
                    )}

                    {/* Diet labels as colored chips */}
                    {item.diet_labels?.length > 0 && (
                      <div style={{ display: 'flex', flexWrap: 'wrap' as const, gap: 4, marginTop: 5 }}>
                        {item.diet_labels.slice(0, 6).map((label: string) => (
                          <span key={label} style={{
                            fontSize: 10, padding: '1px 6px', borderRadius: 8,
                            background: '#F0F0F0', color: '#555', fontWeight: 500,
                          }}>
                            {label}
                          </span>
                        ))}
                      </div>
                    )}

                    {/* Log button */}
                    <Button
                      size="small"
                      icon={<PlusOutlined />}
                      onClick={() => setLogPrefill({ name: item.name, calories: item.calories, protein_g: item.protein, fat_g: item.fat, carb_g: item.carbs })}
                      style={{ fontSize: 11, marginTop: 6, height: 24 }}
                    >
                      {t.rest_log_meal}
                    </Button>
                  </div>
                </div>
              )
            })}
          </div>
        </>
      )}

      {logPrefill && (
        <AddLogModal
          open={!!logPrefill}
          logDate={new Date().toISOString().slice(0, 10)}
          prefill={logPrefill}
          onClose={() => setLogPrefill(null)}
          onAdded={() => setLogPrefill(null)}
        />
      )}
    </div>
  )
}
