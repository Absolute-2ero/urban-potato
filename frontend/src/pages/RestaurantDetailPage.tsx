import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import {
  Button, Carousel, Col, Descriptions, Divider, Empty, Rate,
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
import { AllergenWarning } from '@/components/common/AllergenWarning'
import { DietBadgeGroup } from '@/components/common/DietBadge'
import { PRICE_LEVEL_META } from '@/constants'
// DietBadgeGroup kept for restaurant-level label display above
import type { Restaurant } from '@/types'

const { Title, Text, Paragraph } = Typography

export default function RestaurantDetailPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const { user } = useAuthStore()
  const { q: searchQ, dietLabels: searchDietLabels } = useSearchStore()
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
            id: crypto.randomUUID(),
            restaurantId: r.restaurant_id,
            restaurantName: r.name,
            dishes: r.menu_items?.slice(0, 5).map((item) => item.name) ?? [],
            timestamp: Date.now(),
          },
          user?.id,
        )
      }
    )
  }, [id])

  const toggleSave = async () => {
    if (!id) return
    if (saved) {
      await unsaveRestaurant(id)
    } else {
      await saveRestaurant(id)
    }
    setSaved(!saved)
  }

  if (loading) return <Skeleton active style={{ padding: 24 }} />
  if (!restaurant) return <Empty description="Restaurant not found" />

  const r = restaurant

  return (
    <div style={{ maxWidth: 900, margin: '0 auto', padding: '24px 16px' }}>
      {/* 顶部导航 */}
      <div style={{ display: 'flex', alignItems: 'center', marginBottom: 24, gap: 12 }}>
        <Button icon={<ArrowLeftOutlined />} onClick={() => navigate(-1)}>
          Back
        </Button>
        <Title level={3} style={{ margin: 0, flex: 1 }}>
          {r.name_en || r.name}
        </Title>
        <Button
          icon={saved ? <HeartFilled style={{ color: '#ff4d4f' }} /> : <HeartOutlined />}
          onClick={toggleSave}
        >
          {saved ? 'Saved' : 'Save'}
        </Button>
      </div>

      {/* 过敏原警告 */}
      {(r._allergen_warning?.length ?? r.allergens.length) > 0 && (
        <AllergenWarning allergens={r._allergen_warning ?? r.allergens} />
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
              <span style={{ fontSize: 13, color: '#AAB4B4' }}>No photo available</span>
            </div>
          )}
        </Col>

        {/* 基本信息 */}
        <Col xs={24} md={14}>
          <Space direction="vertical" style={{ width: '100%' }} size={12}>
            {/* Rating + price */}
            <Space>
              {r.rating ? (
                <Space size={4}>
                  <Rate disabled value={r.rating} style={{ fontSize: 14 }} />
                  <Text style={{ color: '#fa8c16', fontWeight: 600 }}>
                    {r.rating.toFixed(1)}
                  </Text>
                  {r.rating_count != null && r.rating_count > 0 && (
                    <Text type="secondary" style={{ fontSize: 12 }}>
                      ({r.rating_count} reviews)
                    </Text>
                  )}
                </Space>
              ) : null}
              {r.price_level ? (
                <Tag color="geekblue">{PRICE_LEVEL_META[r.price_level]?.label}</Tag>
              ) : null}
              {r.cuisine_type && <Tag>{r.cuisine_type}</Tag>}
            </Space>

            {/* 联系 + 地址 */}
            <Descriptions column={1} size="small">
              {r.address && (
                <Descriptions.Item label={<EnvironmentOutlined />}>
                  {r.address}
                </Descriptions.Item>
              )}
              {r.phone && (
                <Descriptions.Item label={<PhoneOutlined />}>
                  <a href={`tel:${r.phone}`}>{r.phone}</a>
                </Descriptions.Item>
              )}
            </Descriptions>

            {r.description && (
              <Paragraph type="secondary" style={{ fontSize: 13 }}>
                {r.description}
              </Paragraph>
            )}
          </Space>
        </Col>
      </Row>

      {/* Menu — individual dish cards */}
      {r.menu_items && r.menu_items.length > 0 && (
        <>
          <Divider>Menu ({r.menu_items.length} dishes)</Divider>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 12 }}>
            {[...r.menu_items].sort((a: any, b: any) => {
              const isMatchA = (searchDietLabels.length > 0 && a.diet_labels?.some((d: string) => searchDietLabels.includes(d as any))) || (searchQ && a.name?.toLowerCase().includes(searchQ.toLowerCase()))
              const isMatchB = (searchDietLabels.length > 0 && b.diet_labels?.some((d: string) => searchDietLabels.includes(d as any))) || (searchQ && b.name?.toLowerCase().includes(searchQ.toLowerCase()))
              return (isMatchB ? 1 : 0) - (isMatchA ? 1 : 0)
            }).map((item: any, i: number) => {
              const labelMatch = searchDietLabels.length > 0 && item.diet_labels?.some((d: string) => searchDietLabels.includes(d as any))
              const nameMatch = searchQ && item.name?.toLowerCase().includes(searchQ.toLowerCase())
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
                        <Text strong style={{ fontSize: 13, color: '#1E2A2A' }}>{item.name}</Text>
                        {isMatch && (
                          <span style={{
                            fontSize: 10, color: '#2D9B5A', background: '#E8F5E9',
                            padding: '1px 6px', borderRadius: 8, fontWeight: 600,
                          }}>✓ match</span>
                        )}
                      </div>
                      {item.price && (
                        <Text style={{ fontSize: 13, fontWeight: 600, color: '#1E2A2A', flexShrink: 0 }}>
                          ${item.price}
                        </Text>
                      )}
                    </div>

                    {/* Calories + macros */}
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

                    {/* Price */}
                    {item.price && (
                      <Text style={{ fontSize: 12, color: '#6B7A7A', display: 'block', marginTop: 2 }}>
                        ${item.price}
                      </Text>
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
                      Log meal
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
