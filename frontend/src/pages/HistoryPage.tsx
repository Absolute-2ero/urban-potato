import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Button, Empty, Tabs, Typography } from 'antd'
import { ClockCircleOutlined, CloseOutlined, DeleteOutlined, SearchOutlined, ShopOutlined } from '@ant-design/icons'
import { useAuthStore } from '@/stores/authStore'
import {
  type SearchRecord, type RestaurantViewRecord,
  loadSearchHistory, loadViewHistory,
  removeSearchRecord, removeViewRecord,
  clearSearchHistory, clearViewHistory,
  relativeTime,
} from '@/utils/history'
import { PRIMARY_COLOR } from '@/constants'

const { Text, Title } = Typography

const DIET_LABEL_COLORS: Record<string, string> = {
  vegan: '#2D9B5A', vegetarian: '#2D9B5A', halal: '#2D9B5A',
  kosher: '#2D9B5A', keto: '#2D9B5A',
  'dairy-free': '#E85454', 'gluten-free': '#E85454',
}

function SearchItem({
  record,
  onRemove,
  onReplay,
}: {
  record: SearchRecord
  onRemove: () => void
  onReplay: () => void
}) {
  return (
    <div
      onClick={onReplay}
      style={{
        background: '#fff', borderRadius: 12, padding: '14px 16px',
        border: '1px solid #E8E0D5', marginBottom: 8, cursor: 'pointer',
        display: 'flex', alignItems: 'flex-start', gap: 12,
        transition: 'box-shadow 0.15s',
      }}
      onMouseEnter={(e) => (e.currentTarget.style.boxShadow = '0 2px 10px rgba(30,42,42,0.08)')}
      onMouseLeave={(e) => (e.currentTarget.style.boxShadow = 'none')}
    >
      <SearchOutlined style={{ fontSize: 16, color: PRIMARY_COLOR, marginTop: 2, flexShrink: 0 }} />
      <div style={{ flex: 1, minWidth: 0 }}>
        <Text strong style={{ display: 'block', fontSize: 14, color: '#1E2A2A' }}>
          {record.query || <span style={{ color: '#AAB4B4', fontWeight: 400 }}>No keyword</span>}
        </Text>
        {record.dietLabels.length > 0 && (
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 5, marginTop: 6 }}>
            {record.dietLabels.map((l) => (
              <span
                key={l}
                style={{
                  padding: '2px 8px', borderRadius: 999, fontSize: 11, fontWeight: 500,
                  background: (DIET_LABEL_COLORS[l] ?? PRIMARY_COLOR) + '15',
                  color: DIET_LABEL_COLORS[l] ?? PRIMARY_COLOR,
                  border: `1px solid ${(DIET_LABEL_COLORS[l] ?? PRIMARY_COLOR)}30`,
                }}
              >
                {l}
              </span>
            ))}
          </div>
        )}
        <Text type="secondary" style={{ fontSize: 12, display: 'block', marginTop: 5 }}>
          <ClockCircleOutlined style={{ marginRight: 4 }} />
          {relativeTime(record.timestamp)}
          {record.resultCount > 0 && ` · ${record.resultCount} result${record.resultCount !== 1 ? 's' : ''}`}
        </Text>
      </div>
      <button
        onClick={(e) => { e.stopPropagation(); onRemove() }}
        style={{
          background: 'none', border: 'none', cursor: 'pointer', padding: 4,
          color: '#C0BDB8', borderRadius: 4, flexShrink: 0,
          display: 'flex', alignItems: 'center',
        }}
      >
        <CloseOutlined style={{ fontSize: 12 }} />
      </button>
    </div>
  )
}

function RestaurantItem({
  record,
  onRemove,
  onOpen,
}: {
  record: RestaurantViewRecord
  onRemove: () => void
  onOpen: () => void
}) {
  return (
    <div
      onClick={onOpen}
      style={{
        background: '#fff', borderRadius: 12, padding: '14px 16px',
        border: '1px solid #E8E0D5', marginBottom: 8, cursor: 'pointer',
        display: 'flex', alignItems: 'flex-start', gap: 12,
        transition: 'box-shadow 0.15s',
      }}
      onMouseEnter={(e) => (e.currentTarget.style.boxShadow = '0 2px 10px rgba(30,42,42,0.08)')}
      onMouseLeave={(e) => (e.currentTarget.style.boxShadow = 'none')}
    >
      <ShopOutlined style={{ fontSize: 16, color: '#E65100', marginTop: 2, flexShrink: 0 }} />
      <div style={{ flex: 1, minWidth: 0 }}>
        <Text strong style={{ display: 'block', fontSize: 14, color: '#1E2A2A' }}>
          {record.restaurantName}
        </Text>
        {record.dishes.length > 0 && (
          <Text type="secondary" style={{ fontSize: 12, display: 'block', marginTop: 4 }}>
            {record.dishes.join(' · ')}
          </Text>
        )}
        <Text type="secondary" style={{ fontSize: 12, display: 'block', marginTop: 5 }}>
          <ClockCircleOutlined style={{ marginRight: 4 }} />
          {relativeTime(record.timestamp)}
        </Text>
      </div>
      <button
        onClick={(e) => { e.stopPropagation(); onRemove() }}
        style={{
          background: 'none', border: 'none', cursor: 'pointer', padding: 4,
          color: '#C0BDB8', borderRadius: 4, flexShrink: 0,
          display: 'flex', alignItems: 'center',
        }}
      >
        <CloseOutlined style={{ fontSize: 12 }} />
      </button>
    </div>
  )
}

export default function HistoryPage() {
  const navigate = useNavigate()
  const { user } = useAuthStore()
  const uid = user?.id

  const [searches, setSearches] = useState<SearchRecord[]>([])
  const [views, setViews] = useState<RestaurantViewRecord[]>([])

  useEffect(() => {
    setSearches(loadSearchHistory(uid))
    setViews(loadViewHistory(uid))
  }, [uid])

  const removeSearch = (id: string) => {
    removeSearchRecord(id, uid)
    setSearches((prev) => prev.filter((r) => r.id !== id))
  }

  const clearAllSearches = () => {
    clearSearchHistory(uid)
    setSearches([])
  }

  const removeView = (id: string) => {
    removeViewRecord(id, uid)
    setViews((prev) => prev.filter((r) => r.id !== id))
  }

  const clearAllViews = () => {
    clearViewHistory(uid)
    setViews([])
  }

  const replaySearch = (r: SearchRecord) => {
    const params = new URLSearchParams()
    if (r.query) params.set('q', r.query)
    r.dietLabels.forEach((d) => params.append('diet', d))
    navigate(`/search?${params.toString()}`)
  }

  const searchTab = (
    <div>
      {searches.length > 0 && (
        <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 12 }}>
          <Button size="small" danger icon={<DeleteOutlined />} onClick={clearAllSearches}>
            Clear all
          </Button>
        </div>
      )}
      {searches.length === 0
        ? <Empty description="No search history yet" style={{ marginTop: 48 }} />
        : searches.map((r) => (
            <SearchItem key={r.id} record={r} onRemove={() => removeSearch(r.id)} onReplay={() => replaySearch(r)} />
          ))
      }
    </div>
  )

  const viewTab = (
    <div>
      {views.length > 0 && (
        <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 12 }}>
          <Button size="small" danger icon={<DeleteOutlined />} onClick={clearAllViews}>
            Clear all
          </Button>
        </div>
      )}
      {views.length === 0
        ? <Empty description="No restaurants viewed yet" style={{ marginTop: 48 }} />
        : views.map((r) => (
            <RestaurantItem
              key={r.id}
              record={r}
              onRemove={() => removeView(r.id)}
              onOpen={() => navigate(`/restaurants/${r.restaurantId}`)}
            />
          ))
      }
    </div>
  )

  return (
    <div style={{ background: '#F7F3EE', minHeight: 'calc(100vh - 52px)', padding: '28px 16px 60px' }}>
      <div style={{ maxWidth: 620, margin: '0 auto' }}>
        <Title level={4} style={{ marginBottom: 20, color: '#1E2A2A' }}>
          History
        </Title>
        <Tabs
          defaultActiveKey="searches"
          items={[
            {
              key: 'searches',
              label: (
                <span>
                  <SearchOutlined /> Searches
                  {searches.length > 0 && (
                    <span style={{
                      marginLeft: 6, fontSize: 11, background: PRIMARY_COLOR + '20',
                      color: PRIMARY_COLOR, borderRadius: 999, padding: '1px 7px', fontWeight: 600,
                    }}>
                      {searches.length}
                    </span>
                  )}
                </span>
              ),
              children: searchTab,
            },
            {
              key: 'restaurants',
              label: (
                <span>
                  <ShopOutlined /> Restaurants
                  {views.length > 0 && (
                    <span style={{
                      marginLeft: 6, fontSize: 11, background: '#E6520020',
                      color: '#E65100', borderRadius: 999, padding: '1px 7px', fontWeight: 600,
                    }}>
                      {views.length}
                    </span>
                  )}
                </span>
              ),
              children: viewTab,
            },
          ]}
        />
      </div>
    </div>
  )
}
