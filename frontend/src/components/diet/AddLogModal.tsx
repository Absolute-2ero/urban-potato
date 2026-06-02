import { useEffect, useState } from 'react'
import { Button, DatePicker, Input, InputNumber, Modal, Segmented, Typography, message } from 'antd'
import type { Dayjs } from 'dayjs'
import { addLog } from '@/api/diet'
import { PRIMARY_COLOR } from '@/constants'
import type { MealType } from '@/types'
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
  if (h >= 5  && h < 10) return 'breakfast'
  if (h >= 10 && h < 15) return 'lunch'
  if (h >= 15 && h < 18) return 'snack'
  if (h >= 18 && h < 22) return 'dinner'
  return 'snack'
}

interface Props {
  open: boolean
  logDate: string
  defaultMeal?: MealType
  /** Pre-filled from a menu item */
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
  const [meal, setMeal]         = useState<MealType>(defaultMeal ?? autoMealType())
  const [selectedDate, setDate] = useState(dayjs().format('YYYY-MM-DD'))
  const [name, setName]         = useState(prefill?.name ?? '')
  const [calories, setCalories] = useState<number>(prefill?.calories ?? 0)
  const [protein, setProtein]   = useState<number>(prefill?.protein_g ?? 0)
  const [fat, setFat]           = useState<number>(prefill?.fat_g ?? 0)
  const [carbs, setCarbs]       = useState<number>(prefill?.carb_g ?? 0)
  const [portionG, setPortion]  = useState(100)
  const [notes, setNotes]       = useState('')
  const [saving, setSaving]     = useState(false)

  useEffect(() => {
    if (!open) return
    setDate(dayjs().format('YYYY-MM-DD'))
    setMeal(defaultMeal ?? autoMealType())
    setName(prefill?.name ?? '')
    setCalories(prefill?.calories ?? 0)
    setProtein(prefill?.protein_g ?? 0)
    setFat(prefill?.fat_g ?? 0)
    setCarbs(prefill?.carb_g ?? 0)
    setPortion(100)
    setNotes('')
  }, [open])

  const handleSave = async () => {
    if (!name.trim()) { message.warning('Please enter a dish name'); return }
    setSaving(true)
    try {
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
      onAdded()
      onClose()
    } catch {
      message.error('Failed to save — please try again')
    } finally {
      setSaving(false)
    }
  }

  return (
    <Modal
      open={open}
      onCancel={onClose}
      footer={null}
      width={440}
      title={<Text strong style={{ fontSize: 16 }}>Log a meal</Text>}
    >
      {/* Date */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 16, padding: '10px 12px', background: '#F7F3EE', borderRadius: 10 }}>
        <Text type="secondary" style={{ fontSize: 12, fontWeight: 600, letterSpacing: 0.5 }}>DATE</Text>
        <DatePicker
          value={dayjs(selectedDate)}
          onChange={(d: Dayjs | null) => { if (d) setDate(d.format('YYYY-MM-DD')) }}
          disabledDate={(d) => d.isAfter(dayjs(), 'day')}
          allowClear={false}
          style={{ flex: 1 }}
          format="ddd, MMM D, YYYY"
        />
      </div>

      {/* Meal type */}
      <div style={{ marginBottom: 16 }}>
        <Text type="secondary" style={{ fontSize: 12, display: 'block', marginBottom: 6 }}>MEAL</Text>
        <Segmented
          block
          value={meal}
          onChange={(v) => setMeal(v as MealType)}
          options={MEALS.map((m) => ({ value: m.value, label: `${m.emoji} ${m.label}` }))}
        />
      </div>

      {/* Dish name */}
      <div style={{ marginBottom: 12 }}>
        <Text type="secondary" style={{ fontSize: 12, display: 'block', marginBottom: 4 }}>DISH NAME</Text>
        <Input
          placeholder="e.g. Grilled chicken breast"
          value={name}
          onChange={(e) => setName(e.target.value)}
          readOnly={!!prefill}
        />
      </div>

      {/* Macros 2×2 grid */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10, marginBottom: 12 }}>
        {([
          { label: 'Calories (kcal)', val: calories, set: setCalories, color: '#fa8c16' },
          { label: 'Protein (g)',     val: protein,  set: setProtein,  color: PRIMARY_COLOR },
          { label: 'Fat (g)',         val: fat,       set: setFat,      color: '#f759ab' },
          { label: 'Carbs (g)',       val: carbs,     set: setCarbs,    color: '#52c41a' },
        ] as { label: string; val: number; set: (v: number) => void; color: string }[]).map(({ label, val, set, color }) => (
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

      {/* Portion */}
      <div style={{ marginBottom: 12 }}>
        <Text type="secondary" style={{ fontSize: 12, display: 'block', marginBottom: 4 }}>PORTION (g, optional)</Text>
        <InputNumber min={1} max={5000} value={portionG} onChange={(v) => setPortion(v ?? 100)} addonAfter="g" style={{ width: 140 }} />
      </div>

      {/* Notes */}
      <div style={{ marginBottom: 20 }}>
        <Text type="secondary" style={{ fontSize: 12, display: 'block', marginBottom: 4 }}>NOTES (optional)</Text>
        <Input
          placeholder="e.g. Had this at lunch meeting"
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
        />
      </div>

      <Button
        type="primary" block size="large"
        loading={saving}
        onClick={handleSave}
        style={{ background: PRIMARY_COLOR, borderColor: PRIMARY_COLOR, borderRadius: 10 }}
      >
        Add to log
      </Button>
    </Modal>
  )
}
