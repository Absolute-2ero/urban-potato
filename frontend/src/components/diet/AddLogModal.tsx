import { useEffect, useState } from 'react'
import { Button, DatePicker, Input, InputNumber, Modal, Segmented, Spin, Typography, message } from 'antd'
import { SearchOutlined } from '@ant-design/icons'
import type { Dayjs } from 'dayjs'
import { searchFood } from '@/api/food'
import { addLog } from '@/api/diet'
import { PRIMARY_COLOR } from '@/constants'
import type { FoodItem, MealType } from '@/types'
import dayjs from 'dayjs'

const { Text } = Typography

const MEALS: { value: MealType; label: string; emoji: string }[] = [
  { value: 'breakfast', label: 'Breakfast', emoji: '🌅' },
  { value: 'lunch',     label: 'Lunch',     emoji: '☀️' },
  { value: 'dinner',    label: 'Dinner',    emoji: '🌙' },
  { value: 'snack',     label: 'Snack',     emoji: '🍎' },
]

function autoMealType(): MealType {
  const h = new Date().getHours()
  if (h >= 5 && h < 10) return 'breakfast'
  if (h >= 10 && h < 15) return 'lunch'
  if (h >= 15 && h < 18) return 'snack'
  if (h >= 18 && h < 22) return 'dinner'
  return 'snack'
}

interface Props {
  open: boolean
  logDate: string
  defaultMeal?: MealType
  /** Pre-filled from a menu item — skips search mode */
  prefill?: {
    name: string
    calories?: number
    protein_g?: number
    fat_g?: number
    carb_g?: number
  }
  onClose: () => void
  onAdded: () => void
}

export function AddLogModal({ open, logDate, defaultMeal, prefill, onClose, onAdded }: Props) {
  const [mode, setMode] = useState<'search' | 'manual'>(prefill ? 'manual' : 'search')
  const [meal, setMeal] = useState<MealType>(defaultMeal ?? autoMealType())
  const [selectedDate, setSelectedDate] = useState<string>(dayjs().format('YYYY-MM-DD'))

  // Search mode state
  const [searchQ, setSearchQ] = useState('')
  const [searching, setSearching] = useState(false)
  const [results, setResults] = useState<FoodItem[]>([])
  const [picked, setPicked] = useState<FoodItem | null>(null)
  const [amountG, setAmountG] = useState(100)

  // Manual mode state
  const [name, setName] = useState(prefill?.name ?? '')
  const [calories, setCalories] = useState<number>(prefill?.calories ?? 0)
  const [protein, setProtein] = useState<number>(prefill?.protein_g ?? 0)
  const [fat, setFat] = useState<number>(prefill?.fat_g ?? 0)
  const [carbs, setCarbs] = useState<number>(prefill?.carb_g ?? 0)
  const [portionG, setPortionG] = useState(100)
  const [notes, setNotes] = useState('')

  const [saving, setSaving] = useState(false)

  useEffect(() => {
    if (open) {
      setSelectedDate(dayjs().format('YYYY-MM-DD'))
      setMeal(defaultMeal ?? autoMealType())
      setPicked(null)
      setResults([])
      setSearchQ('')
      setAmountG(100)
      if (prefill) {
        setMode('manual')
        setName(prefill.name)
        setCalories(prefill.calories ?? 0)
        setProtein(prefill.protein_g ?? 0)
        setFat(prefill.fat_g ?? 0)
        setCarbs(prefill.carb_g ?? 0)
        setPortionG(100)
      } else {
        setMode('search')
        setName('')
        setCalories(0)
        setProtein(0)
        setFat(0)
        setCarbs(0)
      }
      setNotes('')
    }
  }, [open])

  const handleSearch = async () => {
    if (!searchQ.trim()) return
    setSearching(true)
    setPicked(null)
    try {
      const res = await searchFood(searchQ)
      setResults(res.items)
    } finally {
      setSearching(false)
    }
  }

  const scaledMacros = picked
    ? {
        calories: +(picked.calories_per_100g * amountG / 100).toFixed(1),
        protein_g: +(picked.protein_g * amountG / 100).toFixed(1),
        fat_g: +(picked.fat_g * amountG / 100).toFixed(1),
        carb_g: +(picked.carb_g * amountG / 100).toFixed(1),
      }
    : null

  const handleSave = async () => {
    setSaving(true)
    try {
      if (mode === 'search' && picked && scaledMacros) {
        await addLog({
          food_id: picked.food_id,
          food_name_snapshot: picked.name_zh,
          log_date: selectedDate,
          meal_type: meal,
          amount_g: amountG,
          ...scaledMacros,
          notes: notes || undefined,
        })
      } else {
        if (!name.trim()) { message.warning('Please enter a dish name'); return }
        await addLog({
          food_name_snapshot: name.trim(),
          log_date: selectedDate,
          meal_type: meal,
          amount_g: portionG,
          calories,
          protein_g: protein,
          fat_g: fat,
          carb_g: carbs,
          notes: notes || undefined,
        })
      }
      onAdded()
      onClose()
    } catch {
      message.error('Failed to save — please try again')
    } finally {
      setSaving(false)
    }
  }

  const macroChip = (label: string, value: number, color: string) => (
    <div style={{ textAlign: 'center' as const }}>
      <Text style={{ fontSize: 15, fontWeight: 700, color, display: 'block' }}>{value}</Text>
      <Text type="secondary" style={{ fontSize: 11 }}>{label}</Text>
    </div>
  )

  return (
    <Modal
      open={open}
      onCancel={onClose}
      footer={null}
      width={480}
      title={
        <Text strong style={{ fontSize: 16 }}>Log a meal</Text>
      }
    >
      {/* Date picker */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 16, padding: '10px 12px', background: '#F7F3EE', borderRadius: 10 }}>
        <Text type="secondary" style={{ fontSize: 12, fontWeight: 600, letterSpacing: 0.5 }}>DATE</Text>
        <DatePicker
          value={dayjs(selectedDate)}
          onChange={(d: Dayjs | null) => { if (d) setSelectedDate(d.format('YYYY-MM-DD')) }}
          disabledDate={(d) => d.isAfter(dayjs(), 'day')}
          allowClear={false}
          style={{ flex: 1 }}
          format="ddd, MMM D, YYYY"
        />
      </div>

      {/* Meal type selector */}
      <div style={{ marginBottom: 16 }}>
        <Text type="secondary" style={{ fontSize: 12, display: 'block', marginBottom: 6 }}>MEAL</Text>
        <Segmented
          block
          value={meal}
          onChange={(v) => setMeal(v as MealType)}
          options={MEALS.map((m) => ({ value: m.value, label: `${m.emoji} ${m.label}` }))}
        />
      </div>

      {/* Mode tabs — hidden when prefill is active */}
      {!prefill && (
        <div style={{ display: 'flex', gap: 0, marginBottom: 16, borderBottom: '1px solid #E8E0D5' }}>
          {(['search', 'manual'] as const).map((m) => (
            <button
              key={m}
              onClick={() => { setMode(m); setPicked(null); setResults([]) }}
              style={{
                padding: '8px 20px', border: 'none', background: 'none',
                borderBottom: mode === m ? `2px solid ${PRIMARY_COLOR}` : '2px solid transparent',
                color: mode === m ? PRIMARY_COLOR : '#6B7A7A',
                fontWeight: mode === m ? 600 : 400, fontSize: 14, cursor: 'pointer',
              }}
            >
              {m === 'search' ? '🔍 Search food' : '✏️ Enter manually'}
            </button>
          ))}
        </div>
      )}

      {/* Search mode */}
      {mode === 'search' && (
        <div>
          <div style={{ display: 'flex', gap: 8, marginBottom: 12 }}>
            <Input
              placeholder="Search food database…"
              value={searchQ}
              onChange={(e) => setSearchQ(e.target.value)}
              onPressEnter={handleSearch}
              prefix={<SearchOutlined style={{ color: '#AAB4B4' }} />}
            />
            <Button type="primary" onClick={handleSearch} loading={searching}
              style={{ background: PRIMARY_COLOR, borderColor: PRIMARY_COLOR }}>
              Search
            </Button>
          </div>
          <Spin spinning={searching}>
            {results.length > 0 && !picked && (
              <div style={{ maxHeight: 200, overflowY: 'auto' as const, marginBottom: 12 }}>
                {results.map((item, i) => (
                  <div
                    key={i}
                    onClick={() => setPicked(item)}
                    style={{
                      padding: '10px 12px', borderRadius: 8, cursor: 'pointer', marginBottom: 4,
                      border: '1px solid #E8E0D5', background: '#FAFAF8',
                      display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                    }}
                    onMouseEnter={(e) => (e.currentTarget.style.background = PRIMARY_COLOR + '10')}
                    onMouseLeave={(e) => (e.currentTarget.style.background = '#FAFAF8')}
                  >
                    <Text strong style={{ fontSize: 14 }}>{item.name_zh}</Text>
                    <Text type="secondary" style={{ fontSize: 12 }}>{item.calories_per_100g} kcal/100g</Text>
                  </div>
                ))}
              </div>
            )}
          </Spin>
          {picked && (
            <div style={{ background: PRIMARY_COLOR + '08', borderRadius: 10, padding: '14px 16px', marginBottom: 12, border: `1px solid ${PRIMARY_COLOR}30` }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
                <Text strong>{picked.name_zh}</Text>
                <button onClick={() => setPicked(null)} style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#AAB4B4', fontSize: 16 }}>×</button>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 12 }}>
                <Text type="secondary" style={{ fontSize: 13 }}>Amount:</Text>
                <InputNumber
                  min={1} max={2000} value={amountG}
                  onChange={(v) => setAmountG(v ?? 100)}
                  addonAfter="g"
                  style={{ width: 110 }}
                />
              </div>
              {scaledMacros && (
                <div style={{ display: 'flex', justifyContent: 'space-around', background: '#fff', borderRadius: 8, padding: '10px 0' }}>
                  {macroChip('kcal', scaledMacros.calories, '#fa8c16')}
                  {macroChip('protein', scaledMacros.protein_g, PRIMARY_COLOR)}
                  {macroChip('fat', scaledMacros.fat_g, '#f759ab')}
                  {macroChip('carbs', scaledMacros.carb_g, '#52c41a')}
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* Manual mode */}
      {mode === 'manual' && (
        <div>
          <div style={{ marginBottom: 12 }}>
            <Text type="secondary" style={{ fontSize: 12, display: 'block', marginBottom: 4 }}>DISH NAME</Text>
            <Input
              placeholder="e.g. Grilled chicken breast"
              value={name}
              onChange={(e) => setName(e.target.value)}
              readOnly={!!prefill}
            />
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10, marginBottom: 12 }}>
            {[
              { label: 'Calories (kcal)', val: calories, set: setCalories, color: '#fa8c16' },
              { label: 'Protein (g)', val: protein, set: setProtein, color: PRIMARY_COLOR },
              { label: 'Fat (g)', val: fat, set: setFat, color: '#f759ab' },
              { label: 'Carbs (g)', val: carbs, set: setCarbs, color: '#52c41a' },
            ].map(({ label, val, set, color }) => (
              <div key={label}>
                <Text type="secondary" style={{ fontSize: 12, display: 'block', marginBottom: 4 }}>{label.toUpperCase()}</Text>
                <InputNumber
                  min={0} max={9999} value={val} step={0.1}
                  onChange={(v) => set(v ?? 0)}
                  style={{ width: '100%', borderColor: color + '60' }}
                />
              </div>
            ))}
          </div>
          <div style={{ display: 'flex', gap: 10, marginBottom: 12 }}>
            <div style={{ flex: 1 }}>
              <Text type="secondary" style={{ fontSize: 12, display: 'block', marginBottom: 4 }}>PORTION (g, optional)</Text>
              <InputNumber min={1} max={5000} value={portionG} onChange={(v) => setPortionG(v ?? 100)} addonAfter="g" style={{ width: '100%' }} />
            </div>
          </div>
        </div>
      )}

      {/* Notes (both modes) */}
      <div style={{ marginBottom: 20 }}>
        <Text type="secondary" style={{ fontSize: 12, display: 'block', marginBottom: 4 }}>NOTES (optional)</Text>
        <Input
          placeholder="e.g. Had this at lunch meeting"
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
        />
      </div>

      <Button
        type="primary"
        block
        size="large"
        loading={saving}
        onClick={handleSave}
        disabled={mode === 'search' && !picked}
        style={{ background: PRIMARY_COLOR, borderColor: PRIMARY_COLOR, borderRadius: 10 }}
      >
        Add to log
      </Button>
    </Modal>
  )
}
