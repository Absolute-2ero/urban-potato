import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Button, Empty, Popconfirm, Rate, Skeleton, Space, Tag, Typography } from 'antd'
import { DeleteOutlined, HeartFilled, EnvironmentOutlined } from '@ant-design/icons'
import { getSavedRestaurants, unsaveRestaurant } from '@/api/diet'
import { getRestaurant } from '@/api/restaurants'
import { useAuthStore } from '@/stores/authStore'
import { AllergenWarning } from '@/components/common/AllergenWarning'
import { getPriceLevelMeta, PRIMARY_COLOR } from '@/constants'
import { useSearchStore } from '@/stores/searchStore'
import { useLang } from '@/i18n/LanguageContext'
import type { Restaurant } from '@/types'

const { Title, Text } = Typography

function RestaurantThumbnail({ src, alt }: { src?: string; alt: string }) {
  const [error, setError] = useState(false)
  if (src && !error) {
    return (
      <img
        src={src} alt={alt}
        style={{ width: 88, height: 88, objectFit: 'cover', borderRadius: 8, flexShrink: 0 }}
        onError={() => setError(true)}
      />
    )
  }
  return (
    <div style={{
      width: 88, height: 88, borderRadius: 8, flexShrink: 0,
      background: '#F0EAE0', display: 'flex', alignItems: 'center', justifyContent: 'center',
    }}>
      <span style={{ fontSize: 28 }}>🍽️</span>
    </div>
  )
}

export default function SavedRestaurantsPage() {
  const navigate = useNavigate()
  const { user } = useAuthStore()
  const { city } = useSearchStore()
  const priceLevelMeta = getPriceLevelMeta(city)
  const [restaurants, setRestaurants] = useState<Restaurant[]>([])
  const [loading, setLoading] = useState(true)
  const [unsavingId, setUnsavingId] = useState<string | null>(null)
  const [unsavingAll, setUnsavingAll] = useState(false)
  const { t } = useLang()

  const loadSaved = async () => {
    setLoading(true)
    try {
      const ids = await getSavedRestaurants()
      const results = await Promise.all(ids.map((id) => getRestaurant(id).catch(() => null)))
      setRestaurants(results.filter(Boolean) as Restaurant[])
    } catch {
      setRestaurants([])
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    if (user) loadSaved()
    else setLoading(false)
  }, [user])

  const handleUnsave = async (id: string) => {
    setUnsavingId(id)
    try {
      await unsaveRestaurant(id)
      setRestaurants((prev) => prev.filter((r) => r.restaurant_id !== id))
    } finally {
      setUnsavingId(null)
    }
  }

  const handleUnsaveAll = async () => {
    setUnsavingAll(true)
    try {
      await Promise.all(restaurants.map((r) => unsaveRestaurant(r.restaurant_id)))
      setRestaurants([])
    } finally {
      setUnsavingAll(false)
    }
  }

  return (
    <div style={{ background: '#F7F3EE', minHeight: 'calc(100vh - 52px)', padding: '24px 16px 80px', position: 'relative' }}>

      {/* Login gate overlay */}
      {!user && (
        <div style={{
          position: 'absolute', inset: 0, zIndex: 10,
          backdropFilter: 'blur(4px)',
          background: 'rgba(247, 243, 238, 0.85)',
          display: 'flex', flexDirection: 'column',
          alignItems: 'center', justifyContent: 'center', gap: 16,
        }}>
          <div style={{ fontSize: 48 }}>🔒</div>
          <Text strong style={{ fontSize: 18, color: '#1E2A2A' }}>{t.saved_gate_title}</Text>
          <Text type="secondary" style={{ fontSize: 14, textAlign: 'center', maxWidth: 280 }}>
            {t.saved_gate_desc}
          </Text>
          <Button
            type="primary" size="large"
            onClick={() => navigate('/login')}
            style={{ background: PRIMARY_COLOR, borderColor: PRIMARY_COLOR, borderRadius: 999, padding: '0 32px', marginTop: 4 }}
          >
            {t.saved_sign_in}
          </Button>
        </div>
      )}

      <div style={{ maxWidth: 700, margin: '0 auto', filter: user ? 'none' : 'blur(2px)', pointerEvents: user ? 'auto' : 'none' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 20 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <Title level={3} style={{ margin: 0 }}>{t.saved_title}</Title>
          {!loading && (
            <Text type="secondary" style={{ fontSize: 13 }}>({restaurants.length})</Text>
          )}
        </div>
        {restaurants.length > 0 && (
          <Popconfirm
            title={t.saved_unsave_confirm_title}
            description={t.saved_unsave_confirm_desc}
            onConfirm={handleUnsaveAll}
            okText={t.saved_unsave_ok}
            okButtonProps={{ danger: true }}
            cancelText={t.saved_cancel}
          >
            <Button danger size="small" icon={<DeleteOutlined />} loading={unsavingAll}>
              {t.saved_unsave_all}
            </Button>
          </Popconfirm>
        )}
      </div>

      {loading ? (
        <Space direction="vertical" style={{ width: '100%' }} size={12}>
          {[1, 2, 3].map((i) => <Skeleton key={i} active avatar paragraph={{ rows: 2 }} />)}
        </Space>
      ) : restaurants.length === 0 ? (
        <Empty
          image={<span style={{ fontSize: 56 }}>🍽️</span>}
          description={
            <span style={{ color: '#6B7A7A' }}>
              {t.saved_empty}
            </span>
          }
          style={{ marginTop: 60 }}
        >
          <Button type="primary" onClick={() => navigate('/')}
            style={{ background: PRIMARY_COLOR, borderColor: PRIMARY_COLOR }}>
            {t.saved_discover}
          </Button>
        </Empty>
      ) : (
        <Space direction="vertical" style={{ width: '100%' }} size={12}>
          {restaurants.map((r) => (
            <div
              key={r.restaurant_id}
              style={{
                background: '#fff',
                border: '1.5px solid #E8E0D5',
                borderRadius: 12,
                overflow: 'hidden',
                cursor: 'pointer',
                transition: 'box-shadow 0.15s',
              }}
              onClick={() => navigate(`/restaurants/${r.restaurant_id}`, { state: { noHighlight: true } })}
              onMouseEnter={(e) => (e.currentTarget.style.boxShadow = '0 2px 12px rgba(30,42,42,0.1)')}
              onMouseLeave={(e) => (e.currentTarget.style.boxShadow = 'none')}
            >
              {r._allergen_warning?.length ? (
                <div style={{ padding: '8px 16px 0' }}>
                  <AllergenWarning allergens={r._allergen_warning} />
                </div>
              ) : null}

              <div style={{ display: 'flex', gap: 14, padding: 14 }}>
                {/* Image */}
                <RestaurantThumbnail src={r.images?.[0]} alt={r.name} />

                {/* Info */}
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 8 }}>
                    <Text strong style={{ fontSize: 15, color: '#1E2A2A', lineHeight: 1.3 }}>
                      {r.name_en || r.name}
                    </Text>
                    {/* Unsave button — stop propagation so click doesn't navigate */}
                    <Button
                      size="small"
                      type="text"
                      danger
                      icon={<HeartFilled />}
                      loading={unsavingId === r.restaurant_id}
                      onClick={(e) => { e.stopPropagation(); handleUnsave(r.restaurant_id) }}
                      style={{ flexShrink: 0, color: '#ff4d4f' }}
                    />
                  </div>

                  {r.rating ? (
                    <Space size={4} style={{ marginTop: 4 }}>
                      <Rate disabled value={r.rating} style={{ fontSize: 11 }} />
                      <Text style={{ fontSize: 12, color: '#fa8c16', fontWeight: 600 }}>{r.rating.toFixed(1)}</Text>
                      {r.rating_count != null && r.rating_count > 0 && (
                        <Text type="secondary" style={{ fontSize: 11 }}>({r.rating_count})</Text>
                      )}
                    </Space>
                  ) : null}

                  <Space size={4} style={{ marginTop: 4 }}>
                    {r.cuisine_type && <Tag style={{ fontSize: 11, borderRadius: 6 }}>{r.cuisine_type}</Tag>}
                    {r.price_level ? (
                      <Tag color="geekblue" style={{ fontSize: 11, borderRadius: 6 }}>
                        {priceLevelMeta[r.price_level]?.label}
                      </Tag>
                    ) : null}
                  </Space>

                  {r.address && (
                    <Text type="secondary" style={{ fontSize: 12, display: 'block', marginTop: 4 }} ellipsis>
                      <EnvironmentOutlined /> {r.address}
                    </Text>
                  )}

                </div>
              </div>
            </div>
          ))}
        </Space>
      )}
      </div>
    </div>
  )
}
