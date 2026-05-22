import { useNavigate } from 'react-router-dom'
import { Button, Space, Typography } from 'antd'
import { SearchOutlined } from '@ant-design/icons'
import { SearchBar } from '@/components/search/SearchBar'
import { DietBadge } from '@/components/common/DietBadge'
import { ALL_DIET_LABELS, PRIMARY_COLOR } from '@/constants'
import { useState } from 'react'
import type { DietLabel } from '@/types'

const { Title, Text } = Typography

const HOT_LABELS: DietLabel[] = ['vegan', 'halal', 'gluten-free', 'keto', 'high-protein', 'organic']

export default function HomePage() {
  const navigate = useNavigate()
  const [q, setQ] = useState('')

  const goSearch = (query: string, diet?: DietLabel) => {
    const params = new URLSearchParams()
    if (query) params.set('q', query)
    if (diet) params.append('diet', diet)
    navigate(`/search?${params.toString()}`)
  }

  return (
    <div
      style={{
        minHeight: '100vh',
        background: 'linear-gradient(135deg, #f0fff4 0%, #e6fffb 50%, #f0f5ff 100%)',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        padding: '60px 24px 40px',
      }}
    >
      {/* Logo */}
      <div style={{ textAlign: 'center', marginBottom: 48 }}>
        <div style={{ fontSize: 56, marginBottom: 8 }}>🥗</div>
        <Title
          style={{
            margin: 0,
            color: PRIMARY_COLOR,
            fontSize: 42,
            fontWeight: 800,
            letterSpacing: -1,
          }}
        >
          DietSearch
        </Title>
        <Text style={{ fontSize: 18, color: '#666', marginTop: 8, display: 'block' }}>
          找到真正适合你的餐厅
        </Text>
      </div>

      {/* 搜索框 */}
      <div style={{ width: '100%', maxWidth: 680, marginBottom: 32 }}>
        <SearchBar
          value={q}
          onChange={setQ}
          onSearch={(v) => goSearch(v)}
          placeholder="素食餐厅、清真料理、无麸质披萨…"
        />
      </div>

      {/* 热门标签 */}
      <div style={{ textAlign: 'center', marginBottom: 48 }}>
        <Text type="secondary" style={{ fontSize: 14, marginBottom: 12, display: 'block' }}>
          热门饮食标签
        </Text>
        <Space wrap size={8} style={{ justifyContent: 'center' }}>
          {HOT_LABELS.map((label) => (
            <DietBadge
              key={label}
              label={label}
              onClick={() => goSearch('', label)}
            />
          ))}
        </Space>
      </div>

      {/* 功能介绍 */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
          gap: 24,
          maxWidth: 800,
          width: '100%',
        }}
      >
        {[
          { emoji: '🔍', title: '智能搜索', desc: 'BM25 + 语义理解，精准匹配你的饮食需求' },
          { emoji: '⚠️', title: '过敏原守护', desc: '实时标注过敏原，保护你的饮食安全' },
          { emoji: '📊', title: '营养追踪', desc: '记录每日饮食，轻松掌握营养摄入' },
          { emoji: '📍', title: '附近推荐', desc: '基于位置，优先推荐距你最近的餐厅' },
        ].map((item) => (
          <div
            key={item.title}
            style={{
              background: 'rgba(255,255,255,0.8)',
              borderRadius: 16,
              padding: 24,
              textAlign: 'center',
              backdropFilter: 'blur(8px)',
              boxShadow: '0 2px 16px rgba(45,155,90,0.08)',
            }}
          >
            <div style={{ fontSize: 36, marginBottom: 12 }}>{item.emoji}</div>
            <Title level={5} style={{ margin: '0 0 8px', color: PRIMARY_COLOR }}>
              {item.title}
            </Title>
            <Text type="secondary" style={{ fontSize: 13 }}>{item.desc}</Text>
          </div>
        ))}
      </div>
    </div>
  )
}
