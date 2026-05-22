import { useEffect, useState } from 'react'
import {
  Button, DatePicker, Divider, Empty, List, Popconfirm,
  Segmented, Space, Spin, Tag, Typography,
} from 'antd'
import { DeleteOutlined, PlusOutlined } from '@ant-design/icons'
import dayjs from 'dayjs'
import { deleteLog } from '@/api/diet'
import { NutritionBar } from '@/components/diet/NutritionBar'
import { FoodSearchModal } from '@/components/food/FoodSearchModal'
import { useDietStore } from '@/stores/dietStore'
import { MEAL_TYPES } from '@/constants'
import type { FoodLogEntry, MealType } from '@/types'

const { Text, Title } = Typography

const DEFAULT_TOTALS = { calories: 0, protein_g: 0, fat_g: 0, carb_g: 0 }

export default function DietLogPage() {
  const { logDay, loading, currentDate, loadLogs, setCurrentDate } = useDietStore()
  const [addOpen, setAddOpen] = useState(false)
  const [activeMeal, setActiveMeal] = useState<MealType | 'all'>('all')

  useEffect(() => {
    loadLogs()
  }, [])

  const handleDelete = async (id: number) => {
    await deleteLog(id)
    loadLogs()
  }

  const entries = logDay?.entries ?? []
  const totals = logDay?.totals ?? DEFAULT_TOTALS

  const filtered =
    activeMeal === 'all'
      ? entries
      : entries.filter((e) => e.meal_type === activeMeal)

  const mealOptions = [
    { label: '全部', value: 'all' },
    ...MEAL_TYPES.map((m) => ({ label: m.label, value: m.value })),
  ]

  return (
    <div style={{ maxWidth: 800, margin: '0 auto', padding: '24px 16px' }}>
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginBottom: 24,
        }}
      >
        <Title level={4} style={{ margin: 0 }}>📊 饮食日记</Title>
        <Space>
          <DatePicker
            value={dayjs(currentDate)}
            onChange={(d) => d && setCurrentDate(d.format('YYYY-MM-DD'))}
            allowClear={false}
            format="YYYY-MM-DD"
          />
          <Button
            type="primary"
            icon={<PlusOutlined />}
            onClick={() => setAddOpen(true)}
          >
            记录饮食
          </Button>
        </Space>
      </div>

      {/* 营养摄入进度 */}
      <NutritionBar totals={totals} />

      <Divider />

      {/* 餐次筛选 */}
      <Segmented
        options={mealOptions}
        value={activeMeal}
        onChange={(v) => setActiveMeal(v as MealType | 'all')}
        style={{ marginBottom: 16 }}
      />

      <Spin spinning={loading}>
        {filtered.length === 0 ? (
          <Empty description="今天还没有记录，点击「记录饮食」开始吧！" />
        ) : (
          <List
            dataSource={filtered}
            renderItem={(entry: FoodLogEntry) => {
              const mealLabel = MEAL_TYPES.find((m) => m.value === entry.meal_type)?.label
              return (
                <List.Item
                  key={entry.id}
                  actions={[
                    <Popconfirm
                      title="删除这条记录？"
                      onConfirm={() => handleDelete(entry.id)}
                      okText="删除"
                      cancelText="取消"
                    >
                      <Button size="small" danger icon={<DeleteOutlined />} />
                    </Popconfirm>,
                  ]}
                  style={{
                    background: '#fff',
                    borderRadius: 8,
                    padding: '12px 16px',
                    marginBottom: 8,
                    border: '1px solid #f0f0f0',
                  }}
                >
                  <List.Item.Meta
                    title={
                      <Space>
                        <Text strong>{entry.food_name_snapshot}</Text>
                        <Tag color="default">{mealLabel}</Tag>
                        <Text type="secondary" style={{ fontSize: 12 }}>
                          {entry.amount_g}g
                        </Text>
                      </Space>
                    }
                    description={
                      <Space size={16} style={{ fontSize: 12, color: '#666' }}>
                        <span>🔥 {entry.calories.toFixed(0)} kcal</span>
                        <span>蛋白 {entry.protein_g.toFixed(1)}g</span>
                        <span>脂肪 {entry.fat_g.toFixed(1)}g</span>
                        <span>碳水 {entry.carb_g.toFixed(1)}g</span>
                      </Space>
                    }
                  />
                </List.Item>
              )
            }}
          />
        )}
      </Spin>

      <FoodSearchModal
        open={addOpen}
        onClose={() => setAddOpen(false)}
        onAdded={() => loadLogs()}
      />
    </div>
  )
}
