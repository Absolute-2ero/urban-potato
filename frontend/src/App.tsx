import { useEffect, Component, type ReactNode, type ErrorInfo } from 'react'
import { BrowserRouter, Link, Navigate, Route, Routes, useLocation } from 'react-router-dom'
import { Avatar, Button, ConfigProvider, Dropdown, Layout, Typography } from 'antd'
import { CalendarOutlined, HistoryOutlined, LoginOutlined, SearchOutlined, UserOutlined } from '@ant-design/icons'
import { useAuthStore } from '@/stores/authStore'
import { PRIMARY_COLOR } from '@/constants'
import HomePage from '@/pages/HomePage'
import AboutPage from '@/pages/AboutPage'
import SearchPage from '@/pages/SearchPage'
import DietLogPage from '@/pages/DietLogPage'
import RestaurantDetailPage from '@/pages/RestaurantDetailPage'
import ProfilePage from '@/pages/ProfilePage'
import LoginPage from '@/pages/LoginPage'
import OnboardingPage from '@/pages/OnboardingPage'
import HistoryPage from '@/pages/HistoryPage'

const { Header, Content } = Layout
const { Text } = Typography

class ErrorBoundary extends Component<{ children: ReactNode }, { error: Error | null }> {
  state = { error: null }
  static getDerivedStateFromError(error: Error) { return { error } }
  componentDidCatch(error: Error, info: ErrorInfo) { console.error('React error:', error, info) }
  render() {
    if (this.state.error) {
      return (
        <div style={{ padding: 40, textAlign: 'center' }}>
          <Text type="danger" style={{ display: 'block', marginBottom: 8 }}>
            Something went wrong — <a onClick={() => { this.setState({ error: null }); window.location.reload() }}>reload</a>
          </Text>
          <pre style={{ textAlign: 'left', background: '#fff1f0', padding: 16, borderRadius: 8, fontSize: 12, overflow: 'auto', maxWidth: 800, margin: '0 auto' }}>
            {this.state.error.message}{'\n'}{this.state.error.stack}
          </pre>
        </div>
      )
    }
    return this.props.children
  }
}

const NAV_TABS = [
  { key: 'discover', label: 'Discover', icon: SearchOutlined, to: () => sessionStorage.getItem('lastSearchUrl') || '/', matches: (p: string) => p === '/' || p.startsWith('/search') || p.startsWith('/restaurants') },
  { key: 'diet', label: 'Diet', icon: CalendarOutlined, to: () => '/diet', matches: (p: string) => p.startsWith('/diet') },
]

function AppHeader() {
  const { user, logout } = useAuthStore()
  const { pathname } = useLocation()

  return (
    <Header
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 0,
        background: '#fff',
        borderBottom: '1px solid #E8E0D5',
        padding: '0 20px',
        height: 52,
        position: 'sticky',
        top: 0,
        zIndex: 100,
        boxShadow: '0 1px 4px rgba(30,42,42,0.06)',
      }}
    >
      {/* Logo */}
      <Link
        to="/"
        onClick={() => sessionStorage.removeItem('lastSearchUrl')}
        style={{ display: 'flex', alignItems: 'center', gap: 7, textDecoration: 'none', marginRight: 24 }}
      >
        <span style={{ fontSize: 20 }}>🥗</span>
        <Text strong style={{ color: PRIMARY_COLOR, fontSize: 16, letterSpacing: -0.3 }}>
          MacroBite
        </Text>
      </Link>

      {/* Nav tabs */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 4, flex: 1 }}>
        {NAV_TABS.map(({ key, label, icon: Icon, to, matches }) => {
          const active = matches(pathname)
          return (
            <Link
              key={key}
              to={to()}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 5,
                padding: '6px 12px',
                borderRadius: 8,
                textDecoration: 'none',
                background: active ? PRIMARY_COLOR + '12' : 'transparent',
                color: active ? PRIMARY_COLOR : '#6B7A7A',
                fontSize: 14,
                fontWeight: active ? 600 : 400,
                transition: 'all 0.12s',
              }}
            >
              <Icon style={{ fontSize: 15 }} />
              {label}
            </Link>
          )
        })}
      </div>

      {/* About link */}
      <Link to="/about" style={{
        fontSize: 13, color: pathname === '/about' ? PRIMARY_COLOR : '#6B7A7A',
        fontWeight: pathname === '/about' ? 600 : 400,
        marginRight: 12, textDecoration: 'none',
      }}>
        About
      </Link>

      {/* User */}
      <div>
        {user ? (
          <Dropdown
            menu={{
              items: [
                { key: 'profile', label: <Link to="/profile"><UserOutlined style={{ marginRight: 6 }} />Profile</Link> },
                { key: 'history', label: <Link to="/history"><HistoryOutlined style={{ marginRight: 6 }} />History</Link> },
                { key: 'logout', label: 'Sign out', danger: true, onClick: logout },
              ],
            }}
          >
            <Avatar
              style={{ backgroundColor: PRIMARY_COLOR, cursor: 'pointer', fontSize: 14 }}
              size={32}
            >
              {user.username[0].toUpperCase()}
            </Avatar>
          </Dropdown>
        ) : (
          <Link to="/login">
            <Button
              type="primary"
              size="small"
              icon={<LoginOutlined />}
              style={{ background: PRIMARY_COLOR, borderColor: PRIMARY_COLOR }}
            >
              Sign in
            </Button>
          </Link>
        )}
      </div>
    </Header>
  )
}

function AppRoutes() {
  return (
    <Content>
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/search" element={<SearchPage />} />
        <Route path="/diet" element={<DietLogPage />} />
        <Route path="/restaurants/:id" element={<RestaurantDetailPage />} />
        <Route path="/profile" element={<ProfilePage />} />
        <Route path="/login" element={<LoginPage />} />
        <Route path="/onboarding" element={<OnboardingPage />} />
        <Route path="/history" element={<HistoryPage />} />
        <Route path="/about" element={<AboutPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Content>
  )
}

export default function App() {
  const init = useAuthStore((s) => s.init)
  useEffect(() => { init() }, [init])

  return (
    <ConfigProvider
      theme={{
        token: {
          colorPrimary: PRIMARY_COLOR,
          borderRadius: 8,
          fontFamily: "'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', sans-serif",
        },
      }}
    >
      <BrowserRouter>
        <Layout style={{ minHeight: '100vh', background: '#F7F3EE' }}>
          <AppHeader />
          <ErrorBoundary>
            <AppRoutes />
          </ErrorBoundary>
        </Layout>
      </BrowserRouter>
    </ConfigProvider>
  )
}
