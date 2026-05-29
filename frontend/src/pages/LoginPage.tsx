import { useState } from 'react'
import { Button, Card, Form, Input, message, Tabs, Typography } from 'antd'
import { useNavigate } from 'react-router-dom'
import { useAuthStore } from '@/stores/authStore'
import { PRIMARY_COLOR } from '@/constants'

const { Title } = Typography

export default function LoginPage() {
  const { login, register } = useAuthStore()
  const navigate = useNavigate()
  const [loading, setLoading] = useState(false)

  const handleLogin = async (values: { username: string; password: string }) => {
    setLoading(true)
    try {
      await login(values)
      message.success('登录成功')
      navigate(-1)
    } catch {
      message.error('用户名或密码错误')
    } finally {
      setLoading(false)
    }
  }

  const handleRegister = async (values: {
    username: string; email?: string; password: string; confirm: string
  }) => {
    if (values.password !== values.confirm) {
      message.error('两次输入的密码不一致')
      return
    }
    setLoading(true)
    try {
      await register({ username: values.username, email: values.email, password: values.password })
      message.success('Account created!')
      navigate('/onboarding')
    } catch (err: unknown) {
      const detail = (err as any)?.response?.data?.detail || '注册失败'
      message.error(detail)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div
      style={{
        minHeight: '100vh', display: 'flex', alignItems: 'center',
        justifyContent: 'center', background: '#f5f5f5',
      }}
    >
      <Card style={{ width: 420, borderRadius: 16, boxShadow: '0 4px 24px rgba(0,0,0,0.08)' }}>
        <Title level={3} style={{ textAlign: 'center', color: PRIMARY_COLOR, marginBottom: 24 }}>
          🥗 DietSearch
        </Title>

        <Tabs
          defaultActiveKey="login"
          centered
          items={[
            {
              key: 'login',
              label: '登录',
              children: (
                <Form layout="vertical" onFinish={handleLogin}>
                  <Form.Item name="username" label="用户名" rules={[{ required: true }]}>
                    <Input size="large" />
                  </Form.Item>
                  <Form.Item name="password" label="密码" rules={[{ required: true }]}>
                    <Input.Password size="large" />
                  </Form.Item>
                  <Button type="primary" htmlType="submit" size="large" block loading={loading}
                    style={{ background: PRIMARY_COLOR, borderColor: PRIMARY_COLOR }}>
                    登录
                  </Button>
                </Form>
              ),
            },
            {
              key: 'register',
              label: '注册',
              children: (
                <Form layout="vertical" onFinish={handleRegister}>
                  <Form.Item name="username" label="用户名" rules={[
                    { required: true }, { min: 2, max: 32 },
                  ]}>
                    <Input size="large" />
                  </Form.Item>
                  <Form.Item name="email" label="邮箱（可选）">
                    <Input size="large" type="email" />
                  </Form.Item>
                  <Form.Item name="password" label="密码" rules={[
                    { required: true }, { min: 6 },
                  ]}>
                    <Input.Password size="large" />
                  </Form.Item>
                  <Form.Item name="confirm" label="确认密码" rules={[{ required: true }]}>
                    <Input.Password size="large" />
                  </Form.Item>
                  <Button type="primary" htmlType="submit" size="large" block loading={loading}
                    style={{ background: PRIMARY_COLOR, borderColor: PRIMARY_COLOR }}>
                    注册
                  </Button>
                </Form>
              ),
            },
          ]}
        />
      </Card>
    </div>
  )
}
