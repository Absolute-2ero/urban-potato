import { useLocation, useNavigate } from 'react-router-dom'
import { CalendarOutlined, SearchOutlined } from '@ant-design/icons'
import { PRIMARY_COLOR } from '@/constants'

const TABS = [
  {
    key: 'discover',
    label: 'Discover',
    Icon: SearchOutlined,
    to: '/',
    matches: (p: string) => p === '/' || p.startsWith('/search'),
  },
  {
    key: 'diet',
    label: 'Diet',
    Icon: CalendarOutlined,
    to: '/diet',
    matches: (p: string) => p.startsWith('/diet'),
  },
]

export function BottomTabBar() {
  const navigate = useNavigate()
  const { pathname } = useLocation()

  return (
    <div
      style={{
        position: 'fixed',
        bottom: 0,
        left: 0,
        right: 0,
        height: 60,
        background: '#fff',
        borderTop: '1px solid #E8E0D5',
        display: 'flex',
        zIndex: 200,
        boxShadow: '0 -2px 12px rgba(30,42,42,0.06)',
      }}
    >
      {TABS.map(({ key, label, Icon, to, matches }) => {
        const active = matches(pathname)
        return (
          <button
            key={key}
            onClick={() => navigate(to)}
            style={{
              flex: 1,
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              gap: 3,
              border: 'none',
              background: 'none',
              cursor: 'pointer',
              color: active ? PRIMARY_COLOR : '#AAB4B4',
              transition: 'color 0.15s',
              padding: 0,
            }}
          >
            <Icon style={{ fontSize: 22 }} />
            <span style={{ fontSize: 11, fontWeight: active ? 600 : 400 }}>{label}</span>
          </button>
        )
      })}
    </div>
  )
}
