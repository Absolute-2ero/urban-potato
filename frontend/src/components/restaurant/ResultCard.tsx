import { Card, Rate, Space, Tag, Typography } from 'antd'
import {
  EnvironmentOutlined,
  HeartOutlined,
  PhoneOutlined,
} from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'
import { AllergenWarning } from '@/components/common/AllergenWarning'
import { DietBadgeGroup } from '@/components/common/DietBadge'
import { PRICE_LEVEL_META } from '@/constants'
import type { DietLabel, Restaurant } from '@/types'

const { Text, Title } = Typography

interface Props {
  restaurant: Restaurant
  onDietClick?: (label: DietLabel) => void
}

function formatDistance(m?: number): string {
  if (m === undefined) return ''
  if (m < 1000) return `${m}m`
  return `${(m / 1000).toFixed(1)}km`
}

export function ResultCard({ restaurant: r, onDietClick }: Props) {
  const navigate = useNavigate()

  const handleClick = () => {
    navigate(`/restaurants/${r.restaurant_id}`)
  }

  return (
    <Card
      hoverable
      onClick={handleClick}
      style={{ marginBottom: 16, borderRadius: 12 }}
      styles={{ body: { padding: '12px 16px' } }}
    >
      {/* 过敏原警告（最高优先级）*/}
      <AllergenWarning allergens={r._allergen_warning ?? []} />

      <div style={{ display: 'flex', gap: 16 }}>
        {/* 封面图 */}
        {r.images?.[0] && (
          <img
            src={r.images[0]}
            alt={r.name}
            style={{
              width: 100, height: 80, objectFit: 'cover',
              borderRadius: 8, flexShrink: 0,
            }}
            onError={(e) => { (e.currentTarget as HTMLImageElement).style.display = 'none' }}
          />
        )}

        <div style={{ flex: 1, minWidth: 0 }}>
          {/* 标题行 */}
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
            <Title level={5} style={{ margin: 0, lineHeight: 1.3 }} ellipsis>
              {r.name}
            </Title>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexShrink: 0, marginLeft: 8 }}>
              {r.rating && (
                <Space size={2}>
                  <Rate disabled value={r.rating} count={5} style={{ fontSize: 12 }} />
                  <Text style={{ fontSize: 12, color: '#fa8c16', fontWeight: 600 }}>
                    {r.rating.toFixed(1)}
                  </Text>
                </Space>
              )}
            </div>
          </div>

          {/* 菜系 + 价格 */}
          <Space size={4} style={{ marginTop: 4 }}>
            {r.cuisine_type && (
              <Tag style={{ fontSize: 11, borderRadius: 6 }}>{r.cuisine_type}</Tag>
            )}
            {r.price_level && (
              <Tag color="geekblue" style={{ fontSize: 11, borderRadius: 6 }}>
                {PRICE_LEVEL_META[r.price_level]?.icon}
              </Tag>
            )}
            {r._distance_m !== undefined && (
              <Text type="secondary" style={{ fontSize: 12 }}>
                <EnvironmentOutlined /> {formatDistance(r._distance_m)}
              </Text>
            )}
          </Space>

          {/* 饮食标签 */}
          {r.diet_labels.length > 0 && (
            <div style={{ marginTop: 6 }}>
              <DietBadgeGroup
                labels={r.diet_labels}
                maxVisible={5}
                onLabelClick={(l) => { onDietClick?.(l) }}
              />
            </div>
          )}

          {/* 地址 */}
          {r.address && (
            <Text type="secondary" style={{ fontSize: 12, display: 'block', marginTop: 4 }} ellipsis>
              <EnvironmentOutlined /> {r.address}
            </Text>
          )}
        </div>
      </div>
    </Card>
  )
}
