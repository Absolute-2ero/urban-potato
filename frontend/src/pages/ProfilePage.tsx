import { useEffect, useState } from 'react'
import {
  Button, Card, Checkbox, Divider, Form, message, Select, Space, Typography,
} from 'antd'
import { useNavigate } from 'react-router-dom'
import { useAuthStore } from '@/stores/authStore'
import { useDietStore } from '@/stores/dietStore'
import { ALL_DIET_LABELS, COMMON_ALLERGENS, DIET_LABEL_META } from '@/constants'
import type { DietLabel } from '@/types'

const { Title, Text } = Typography

export default function ProfilePage() {
  const { user, logout } = useAuthStore()
  const { profile, loadProfile, saveProfile } = useDietStore()
  const navigate = useNavigate()
  const [form] = Form.useForm()
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    loadProfile()
  }, [])

  useEffect(() => {
    if (profile) {
      form.setFieldsValue({
        diet_labels: profile.diet_labels,
        allergens: profile.allergens,
        price_pref: profile.price_pref,
      })
    }
  }, [profile, form])

  const handleSave = async (values: {
    diet_labels: DietLabel[]
    allergens: string[]
    price_pref?: 1 | 2 | 3 | 4
  }) => {
    setSaving(true)
    try {
      await saveProfile(values)
      message.success('饮食档案已保存')
    } finally {
      setSaving(false)
    }
  }

  const handleLogout = async () => {
    await logout()
    navigate('/')
  }

  if (!user) {
    return (
      <div style={{ textAlign: 'center', padding: 80 }}>
        <Title level={4}>请先登录</Title>
        <Button type="primary" onClick={() => navigate('/login')}>
          去登录
        </Button>
      </div>
    )
  }

  return (
    <div style={{ maxWidth: 600, margin: '0 auto', padding: '24px 16px' }}>
      <Title level={4} style={{ marginBottom: 24 }}>👤 个人中心</Title>

      <Card style={{ marginBottom: 24 }}>
        <Space direction="vertical">
          <Text strong>用户名：{user.username}</Text>
          {user.email && <Text type="secondary">邮箱：{user.email}</Text>}
        </Space>
        <div style={{ marginTop: 16 }}>
          <Button danger onClick={handleLogout}>退出登录</Button>
        </div>
      </Card>

      <Card title="饮食偏好设置">
        <Form form={form} layout="vertical" onFinish={handleSave}>
          <Form.Item name="diet_labels" label="饮食标签（选择你的饮食类型）">
            <Checkbox.Group>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
                {ALL_DIET_LABELS.map((label) => (
                  <Checkbox key={label} value={label}>
                    {DIET_LABEL_META[label]?.emoji} {DIET_LABEL_META[label]?.label}
                  </Checkbox>
                ))}
              </div>
            </Checkbox.Group>
          </Form.Item>

          <Divider />

          <Form.Item name="allergens" label="过敏原（选择你的过敏原，搜索时会自动警告）">
            <Checkbox.Group>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
                {COMMON_ALLERGENS.map((a) => (
                  <Checkbox key={a.value} value={a.value}>
                    {a.label}
                  </Checkbox>
                ))}
              </div>
            </Checkbox.Group>
          </Form.Item>

          <Divider />

          <Form.Item name="price_pref" label="价格偏好">
            <Select
              allowClear
              placeholder="不限"
              options={[
                { value: 1, label: '¥ 经济实惠' },
                { value: 2, label: '¥¥ 人均 50-100' },
                { value: 3, label: '¥¥¥ 人均 100-200' },
                { value: 4, label: '¥¥¥¥ 高档' },
              ]}
            />
          </Form.Item>

          <Button type="primary" htmlType="submit" loading={saving} block>
            保存设置
          </Button>
        </Form>
      </Card>
    </div>
  )
}
