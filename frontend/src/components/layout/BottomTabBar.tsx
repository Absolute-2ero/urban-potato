import { useLocation, useNavigate } from 'react-router-dom'
import { CalendarOutlined, HeartOutlined, SearchOutlined } from '@ant-design/icons'
import { PRIMARY_COLOR } from '@/constants'
import { useLang } from '@/i18n/LanguageContext'

const TABS = [
  { key: 'discover', tKey: 'nav_discover' as const, Icon: SearchOutlined, to: '/', matches: (p: string) => p === '/' || p.startsWith('/search') },
  { key: 'diet',     tKey: 'nav_diet' as const,     Icon: CalendarOutlined, to: '/diet',   matches: (p: string) => p.startsWith('/diet') },
  { key: 'saved',    tKey: 'nav_saved' as const,    Icon: HeartOutlined,    to: '/saved',  matches: (p: string) => p.startsWith('/saved') },
]

export function BottomTabBar() {
  const navigate = useNavigate()
  const { pathname } = useLocation()
  const { t } = useLang()

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
      {TABS.map(({ key, tKey, Icon, to, matches }) => {
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
            <span style={{ fontSize: 11, fontWeight: active ? 600 : 400 }}>{t[tKey]}</span>
          </button>
        )
      })}
    </div>
  )
}
