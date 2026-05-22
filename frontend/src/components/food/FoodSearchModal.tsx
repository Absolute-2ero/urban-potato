import { useState } from 'react'
import {
  Alert, Button, InputNumber, Modal, Select, Spin, Table, Typography,
} from 'antd'
import { ExclamationCircleOutlined } from '@ant-design/icons'
import { searchFood, confirmFood } from '@/api/food'
import { addLog } from '@/api/diet'
import { MEAL_TYPES } from '@/constants'
import type { FoodItem, MealType } from '@/types'
import dayjs from 'dayjs'

const { Text } = Typography

interface Props {
  open: boolean
  onClose: () => void
  onAdded: () => void
}

export function FoodSearchModal({ open, onClose, onAdded }: Props) {
  const [query, setQuery] = useState('')
  const [loading, setLoading] = useState(false)
  const [items, setItems] = useState<FoodItem[]>([])
  const [source, setSource] = useState<string>('')
  const [requiresConfirm, setRequiresConfirm] = useState(false)
  const [selected, setSelected] = useState<FoodItem | null>(null)
  const [amount, setAmount] = useState<number>(100)
  const [mealType, setMealType] = useState<MealType>('lunch')
  const [confirming, setConfirming] = useState(false)

  const handleSearch = async () => {
    if (!query.trim()) return
    setLoading(true)
    try {
      const res = await searchFood(query)
      setItems(res.items)
      setSource(res.source)
      setRequiresConfirm(res.requires_confirm)
    } finally {
      setLoading(false)
    }
  }

  const handleAdd = async () => {
    if (!selected) return
    let food = selected

    // BR-03: LLM 结果先确认再写库
    if (requiresConfirm && !food.food_id) {
      setConfirming(true)
      try {
        food = await confirmFood(food)
      } finally {
        setConfirming(false)
      }
    }

    const ratio = amount / 100
    await addLog({
      food_id: food.food_id,
      food_name_snapshot: food.name_zh,
      log_date: dayjs().format('YYYY-MM-DD'),
      meal_type: mealType,
      amount_g: amount,
      calories: +(food.calories_per_100g * ratio).toFixed(1),
      protein_g: +(food.protein_g * ratio).toFixed(1),
      fat_g: +(food.fat_g * ratio).toFixed(1),
      carb_g: +(food.carb_g * ratio).toFixed(1),
    })
    onAdded()
    onClose()
  }

  const columns = [
    { title: '食物', dataIndex: 'name_zh', key: 'name_zh' },
    { title: '热量/100g', dataIndex: 'calories_per_100g', key: 'cal', render: (v: number) => `${v} kcal` },
    { title: '蛋白质', dataIndex: 'protein_g', key: 'pro', render: (v: number) => `${v}g` },
    { title: '脂肪', dataIndex: 'fat_g', key: 'fat', render: (v: number) => `${v}g` },
    { title: '碳水', dataIndex: 'carb_g', key: 'carb', render: (v: number) => `${v}g` },
  ]

  return (
    <Modal
      title="记录饮食"
      open={open}
      onCancel={onClose}
      footer={null}
      width={680}
    >
      <div style={{ display: 'flex', gap: 8, marginBottom: 12 }}>
        <Select
          showSearch
          placeholder="搜索食物名称…"
          style={{ flex: 1 }}
          filterOption={false}
          onSearch={setQuery}
          onSelect={() => handleSearch()}
          notFoundContent={null}
        />
        <Button type="primary" onClick={handleSearch} loading={loading}>
          搜索
        </Button>
      </div>

      {source === 'llm_estimated' && (
        <Alert
          type="warning"
          showIcon
          icon={<ExclamationCircleOutlined />}
          message="以下数据由 AI 估算，请核实后再添加（确认后将永久保存）"
          style={{ marginBottom: 8 }}
        />
      )}

      {source === 'not_found' && (
        <Alert type="info" message="未找到相关食物，请尝试其他关键词" style={{ marginBottom: 8 }} />
      )}

      <Spin spinning={loading}>
        <Table
          dataSource={items}
          columns={columns}
          rowKey={(r) => String(r.food_id ?? r.name_zh)}
          size="small"
          pagination={false}
          rowSelection={{
            type: 'radio',
            onChange: (_, rows) => setSelected(rows[0] ?? null),
          }}
          style={{ marginBottom: 16 }}
        />
      </Spin>

      {selected && (
        <div style={{ display: 'flex', gap: 12, alignItems: 'center', flexWrap: 'wrap' }}>
          <Text>份量：</Text>
          <InputNumber
            min={1} max={2000} value={amount}
            onChange={(v) => setAmount(v ?? 100)}
            addonAfter="g"
          />
          <Text>餐次：</Text>
          <Select
            value={mealType}
            onChange={setMealType}
            options={MEAL_TYPES.map((m) => ({ value: m.value, label: m.label }))}
            style={{ width: 90 }}
          />
          <Button
            type="primary"
            onClick={handleAdd}
            loading={confirming}
            disabled={!selected}
          >
            {requiresConfirm && !selected?.food_id ? '确认并添加' : '添加'}
          </Button>
        </div>
      )}
    </Modal>
  )
}
