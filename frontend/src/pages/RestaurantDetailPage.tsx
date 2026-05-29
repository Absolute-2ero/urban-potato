import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import {
  Button, Carousel, Col, Descriptions, Divider, Empty, Rate,
  Row, Skeleton, Space, Table, Tag, Typography,
} from 'antd'
import {
  ArrowLeftOutlined, HeartFilled, HeartOutlined, PhoneOutlined, EnvironmentOutlined, PlusOutlined,
} from '@ant-design/icons'
import { AddLogModal } from '@/components/diet/AddLogModal'
import { getRestaurant } from '@/api/restaurants'
import { saveRestaurant, unsaveRestaurant, getSavedRestaurants } from '@/api/diet'
import { useAuthStore } from '@/stores/authStore'
import { addRestaurantView } from '@/utils/history'
import { AllergenWarning } from '@/components/common/AllergenWarning'
import { DietBadgeGroup } from '@/components/common/DietBadge'
import { PRICE_LEVEL_META } from '@/constants'
import type { Restaurant } from '@/types'

const { Title, Text, Paragraph } = Typography

export default function RestaurantDetailPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const { user } = useAuthStore()
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
  if (!restaurant) return <Empty description="餐厅不存在" />

  const r = restaurant

  return (
    <div style={{ maxWidth: 900, margin: '0 auto', padding: '24px 16px' }}>
      {/* 顶部导航 */}
      <div style={{ display: 'flex', alignItems: 'center', marginBottom: 24, gap: 12 }}>
        <Button icon={<ArrowLeftOutlined />} onClick={() => navigate(-1)}>
          返回
        </Button>
        <Title level={3} style={{ margin: 0, flex: 1 }}>
          {r.name}
        </Title>
        <Button
          icon={saved ? <HeartFilled style={{ color: '#ff4d4f' }} /> : <HeartOutlined />}
          onClick={toggleSave}
        >
          {saved ? '已收藏' : '收藏'}
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
            <div
              style={{
                height: 240, background: '#f0f0f0', borderRadius: 12,
                display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 48,
              }}
            >
              🍽️
            </div>
          )}
        </Col>

        {/* 基本信息 */}
        <Col xs={24} md={14}>
          <Space direction="vertical" style={{ width: '100%' }} size={12}>
            {/* 评分 + 价格 */}
            <Space>
              {r.rating && (
                <Space size={4}>
                  <Rate disabled value={r.rating} style={{ fontSize: 14 }} />
                  <Text style={{ color: '#fa8c16', fontWeight: 600 }}>
                    {r.rating.toFixed(1)}
                  </Text>
                  {r.rating_count && (
                    <Text type="secondary" style={{ fontSize: 12 }}>
                      ({r.rating_count} 评价)
                    </Text>
                  )}
                </Space>
              )}
              {r.price_level && (
                <Tag color="geekblue">{PRICE_LEVEL_META[r.price_level]?.label}</Tag>
              )}
              {r.cuisine_type && <Tag>{r.cuisine_type}</Tag>}
            </Space>

            {/* 饮食标签 */}
            {r.diet_labels.length > 0 && (
              <DietBadgeGroup labels={r.diet_labels} maxVisible={8} />
            )}

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

      {/* 菜单 */}
      {r.menu_items && r.menu_items.length > 0 && (
        <>
          <Divider>菜单</Divider>
          <Table
            dataSource={r.menu_items}
            rowKey={(item) => item.item_id ?? item.name}
            size="small"
            pagination={false}
            columns={[
              { title: '菜品', dataIndex: 'name', key: 'name' },
              {
                title: '价格',
                dataIndex: 'price',
                key: 'price',
                render: (p: number) => p ? `¥${p.toFixed(0)}` : '-',
                width: 80,
              },
              {
                title: '热量',
                dataIndex: 'calories',
                key: 'cal',
                render: (c: number) => c ? `${c}kcal` : '-',
                width: 90,
              },
              {
                title: 'Macros',
                key: 'macros',
                width: 140,
                render: (_: unknown, item: any) => {
                  const parts = []
                  if (item.protein) parts.push(`P:${item.protein}g`)
                  if (item.fat) parts.push(`F:${item.fat}g`)
                  if (item.carbs) parts.push(`C:${item.carbs}g`)
                  return parts.length ? (
                    <span style={{ fontSize: 11, color: '#6B7A7A' }}>{parts.join(' · ')}</span>
                  ) : '-'
                },
              },
              {
                title: '饮食标签',
                dataIndex: 'diet_labels',
                key: 'diet',
                render: (labels: string[]) =>
                  labels?.length ? (
                    <DietBadgeGroup labels={labels as any} maxVisible={3} />
                  ) : '-',
              },
              {
                title: '',
                key: 'log',
                width: 60,
                render: (_: unknown, item: any) => (
                  <Button
                    size="small"
                    icon={<PlusOutlined />}
                    onClick={() => setLogPrefill({ name: item.name, calories: item.calories, protein_g: item.protein, fat_g: item.fat, carb_g: item.carbs })}
                    style={{ fontSize: 12 }}
                  >
                    Log
                  </Button>
                ),
              },
            ]}
          />
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
