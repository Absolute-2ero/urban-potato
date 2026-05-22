import { useEffect } from 'react'
import { BrowserRouter, Link, Navigate, Route, Routes, useLocation } from 'react-router-dom'
import { Avatar, Button, ConfigProvider, Dropdown, Layout, Menu, Typography } from 'antd'
import {
  HomeOutlined,
  LoginOutlined,
  SearchOutlined,
  UserOutlined,
  CalendarOutlined,
} from '@ant-design/icons'
import { useAuthStore } from '@/stores/authStore'
import { PRIMARY_COLOR } from '@/constants'
import HomePage from '@/pages/HomePage'
import SearchPage from '@/pages/SearchPage'
import DietLogPage from '@/pages/DietLogPage'
import RestaurantDetailPage from '@/pages/RestaurantDetailPage'
import ProfilePage from '@/pages/ProfilePage'
import LoginPage from '@/pages/LoginPage'

const { Header, Content } = Layout
const { Text } = Typography

function AppHeader() {
  const { user, logout } = useAuthStore()
  const location = useLocation()

  const navItems = [
    { key: '/', icon: <HomeOutlined />, label: <Link to="/">首页</Link> },
    { key: '/search', icon: <SearchOutlined />, label: <Link to="/search">搜索</Link> },
    { key: '/diet', icon: <CalendarOutlined />, label: <Link to="/diet">饮食日记</Link> },
  ]

  const activeKey = navItems.find((item) => location.pathname === item.key)?.key ?? ''

  return (
    <Header
      style={{
        display: 'flex', alignItems: 'center',
        background: '#fff', borderBottom: '1px solid #f0f0f0',
        padding: '0 24px', position: 'sticky', top: 0, zIndex: 100,
      }}
    >
      {/* Logo */}
      <Link to="/" style={{ display: 'flex', alignItems: 'center', gap: 8, marginRight: 32 }}>
        <span style={{ fontSize: 22 }}>🥗</span>
        <Text strong style={{ color: PRIMARY_COLOR, fontSize: 18 }}>DietSearch</Text>
      </Link>

      <Menu
        mode="horizontal"
        selectedKeys={[activeKey]}
        items={navItems}
        style={{ flex: 1, borderBottom: 'none' }}
      />

      {/* 用户区 */}
      <div style={{ marginLeft: 'auto' }}>
        {user ? (
          <Dropdown
            menu={{
              items: [
                { key: 'profile', label: <Link to="/profile">个人中心</Link> },
                { key: 'logout', label: '退出登录', danger: true, onClick: logout },
              ],
            }}
          >
            <Avatar style={{ backgroundColor: PRIMARY_COLOR, cursor: 'pointer' }}>
              {user.username[0].toUpperCase()}
            </Avatar>
          </Dropdown>
        ) : (
          <Link to="/login">
            <Button type="primary" icon={<LoginOutlined />}
              style={{ background: PRIMARY_COLOR, borderColor: PRIMARY_COLOR }}>
              登录
            </Button>
          </Link>
        )}
      </div>
    </Header>
  )
}

function AppContent() {
  return (
    <Content style={{ minHeight: 'calc(100vh - 64px)', background: '#fafafa' }}>
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/search" element={<SearchPage />} />
        <Route path="/diet" element={<DietLogPage />} />
        <Route path="/restaurants/:id" element={<RestaurantDetailPage />} />
        <Route path="/profile" element={<ProfilePage />} />
        <Route path="/login" element={<LoginPage />} />
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
        <Layout>
          <AppHeader />
          <AppContent />
        </Layout>
      </BrowserRouter>
    </ConfigProvider>
  )
}
