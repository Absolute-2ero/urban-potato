import { useEffect, useState } from 'react'
import { Button, DatePicker, Empty, Popconfirm, Spin, Typography } from 'antd'
import { DeleteOutlined, LeftOutlined, PlusOutlined, RightOutlined } from '@ant-design/icons'
import dayjs from 'dayjs'
import { useNavigate } from 'react-router-dom'
import { deleteLog } from '@/api/diet'
import { AddLogModal } from '@/components/diet/AddLogModal'
import { useDietStore } from '@/stores/dietStore'
import { useAuthStore } from '@/stores/authStore'
import { PRIMARY_COLOR } from '@/constants'
import { loadGoals, DEFAULT_GOALS } from '@/utils/prefs'
import type { FoodLogEntry, MealType } from '@/types'

const { Text } = Typography

const MEALS: { value: MealType; label: string; emoji: string; color: string }[] = [
  { value: 'breakfast', label: 'Breakfast', emoji: '🌅', color: '#F57F17' },
  { value: 'lunch',     label: 'Lunch',     emoji: '☀️', color: '#E65100' },
  { value: 'dinner',    label: 'Dinner',    emoji: '🌙', color: '#1565C0' },
  { value: 'snack',     label: 'Snack',     emoji: '🍎', color: '#2D9B5A' },
]

// DRI is loaded per-user from localStorage goals; DEFAULT_GOALS used as fallback

function MacroCard({ label, value, max, unit, color }: {
  label: string; value: number; max: number; unit: string; color: string
}) {
  const pct = Math.min((value / max) * 100, 100)
  const over = value > max
  return (
    <div style={{ background: '#fff', borderRadius: 12, padding: '12px 14px', border: '1px solid #E8E0D5', flex: 1, minWidth: 0 }}>
      <Text style={{ fontSize: 11, color: '#AAB4B4', fontWeight: 600, letterSpacing: 0.8, display: 'block', marginBottom: 4 }}>
        {label.toUpperCase()}
      </Text>
      <Text strong style={{ fontSize: 18, color: over ? '#E85454' : '#1E2A2A' }}>{Math.round(value)}</Text>
      <Text type="secondary" style={{ fontSize: 11 }}> / {max} {unit}</Text>
      <div style={{ height: 4, background: '#F0EBE4', borderRadius: 2, marginTop: 8 }}>
        <div style={{ height: 4, width: `${pct}%`, background: over ? '#E85454' : color, borderRadius: 2, transition: 'width 0.3s' }} />
      </div>
    </div>
  )
}

function EntryRow({ entry, onDelete }: { entry: FoodLogEntry; onDelete: () => void }) {
  return (
    <div style={{ background: '#FAFAF8', borderRadius: 10, padding: '12px 14px', marginBottom: 6, border: '1px solid #E8E0D5', display: 'flex', gap: 12, alignItems: 'flex-start' }}>
      <div style={{ flex: 1, minWidth: 0 }}>
        <Text strong style={{ fontSize: 14, display: 'block', marginBottom: 4 }}>{entry.food_name_snapshot}</Text>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
          {entry.calories > 0 && (
            <span style={{ fontSize: 12, color: '#fa8c16', background: '#FFF8E1', borderRadius: 999, padding: '2px 8px' }}>🔥 {Math.round(entry.calories)} kcal</span>
          )}
          {entry.protein_g > 0 && (
            <span style={{ fontSize: 12, color: PRIMARY_COLOR, background: PRIMARY_COLOR + '12', borderRadius: 999, padding: '2px 8px' }}>{entry.protein_g.toFixed(1)}g protein</span>
          )}
          {entry.fat_g > 0 && (
            <span style={{ fontSize: 12, color: '#f759ab', background: '#FFF0F8', borderRadius: 999, padding: '2px 8px' }}>{entry.fat_g.toFixed(1)}g fat</span>
          )}
          {entry.carb_g > 0 && (
            <span style={{ fontSize: 12, color: '#52c41a', background: '#F6FFED', borderRadius: 999, padding: '2px 8px' }}>{entry.carb_g.toFixed(1)}g carbs</span>
          )}
          {entry.amount_g !== 100 && (
            <span style={{ fontSize: 12, color: '#AAB4B4', background: '#F5F5F5', borderRadius: 999, padding: '2px 8px' }}>{entry.amount_g}g</span>
          )}
        </div>
        {entry.notes && (
          <Text type="secondary" style={{ fontSize: 12, display: 'block', marginTop: 4, fontStyle: 'italic' }}>{entry.notes}</Text>
        )}
      </div>
      <Popconfirm title="Remove this entry?" onConfirm={onDelete} okText="Remove" cancelText="Cancel" okButtonProps={{ danger: true }}>
        <Button size="small" type="text" icon={<DeleteOutlined />} style={{ color: '#C0BDB8', flexShrink: 0 }} />
      </Popconfirm>
    </div>
  )
}

export default function DietLogPage() {
  const { logDay, loading, currentDate, loadLogs, setCurrentDate } = useDietStore()
  const { user } = useAuthStore()
  const DRI = user ? loadGoals(user.id) : DEFAULT_GOALS
  const navigate = useNavigate()
  const [addOpen, setAddOpen] = useState(false)
  const [addMeal, setAddMeal] = useState<MealType | undefined>()
  const [calOpen, setCalOpen] = useState(false)

  useEffect(() => { if (user) loadLogs() }, [user])

  const handleDelete = async (id: number) => {
    await deleteLog(id)
    loadLogs()
  }

  const entries = logDay?.entries ?? []
  const totals = logDay?.totals ?? { calories: 0, protein_g: 0, fat_g: 0, carb_g: 0 }

  const dateLabel = (() => {
    const d = dayjs(currentDate)
    const today = dayjs().format('YYYY-MM-DD')
    const yesterday = dayjs().subtract(1, 'day').format('YYYY-MM-DD')
    if (currentDate === today) return `Today, ${d.format('MMM D')}`
    if (currentDate === yesterday) return `Yesterday, ${d.format('MMM D')}`
    return d.format('ddd, MMM D')
  })()

  const openAdd = (meal?: MealType) => { setAddMeal(meal); setAddOpen(true) }

  return (
    <div style={{ background: '#F7F3EE', minHeight: 'calc(100vh - 52px)', padding: '24px 16px 60px', position: 'relative' }}>

      {/* Login gate overlay */}
      {!user && (
        <div style={{
          position: 'absolute', inset: 0, zIndex: 10,
          backdropFilter: 'blur(4px)',
          background: 'rgba(247, 243, 238, 0.85)',
          display: 'flex', flexDirection: 'column',
          alignItems: 'center', justifyContent: 'center', gap: 16,
        }}>
          <div style={{ fontSize: 48 }}>🔒</div>
          <Text strong style={{ fontSize: 18, color: '#1E2A2A' }}>Sign in to track your diet</Text>
          <Text type="secondary" style={{ fontSize: 14, textAlign: 'center', maxWidth: 280 }}>
            Log meals, track macros, and hit your daily goals — all in one place.
          </Text>
          <Button
            type="primary" size="large"
            onClick={() => navigate('/login')}
            style={{ background: PRIMARY_COLOR, borderColor: PRIMARY_COLOR, borderRadius: 999, padding: '0 32px', marginTop: 4 }}
          >
            Sign in
          </Button>
        </div>
      )}

      <div style={{ maxWidth: 680, margin: '0 auto', filter: user ? 'none' : 'blur(2px)', pointerEvents: user ? 'auto' : 'none' }}>

        {/* Date navigation */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 20 }}>
          <Button type="text" icon={<LeftOutlined />}
            onClick={() => setCurrentDate(dayjs(currentDate).subtract(1, 'day').format('YYYY-MM-DD'))} />

          <div style={{ textAlign: 'center' }}>
            {/* Clicking the date label opens the calendar */}
            <DatePicker
              value={dayjs(currentDate)}
              open={calOpen}
              onOpenChange={setCalOpen}
              onChange={(d) => { if (d) { setCurrentDate(d.format('YYYY-MM-DD')); loadLogs() } }}
              disabledDate={(d) => d.isAfter(dayjs(), 'day')}
              allowClear={false}
              inputReadOnly
              style={{ opacity: 0, position: 'absolute', pointerEvents: 'none', width: 0 }}
            />
            <div
              onClick={() => setCalOpen(true)}
              style={{ cursor: 'pointer', userSelect: 'none' }}
            >
              <Text strong style={{ fontSize: 16 }}>{dateLabel}</Text>
              <Text type="secondary" style={{ fontSize: 11, display: 'block' }}>tap to pick date</Text>
            </div>
            {currentDate !== dayjs().format('YYYY-MM-DD') && (
              <Button type="link" size="small"
                onClick={() => { setCurrentDate(dayjs().format('YYYY-MM-DD')); loadLogs() }}
                style={{ display: 'block', margin: '0 auto', padding: 0, height: 'auto', fontSize: 12 }}>
                Back to today
              </Button>
            )}
          </div>

          <Button type="text" icon={<RightOutlined />}
            disabled={currentDate === dayjs().format('YYYY-MM-DD')}
            onClick={() => setCurrentDate(dayjs(currentDate).add(1, 'day').format('YYYY-MM-DD'))} />
        </div>

        {/* Macro summary */}
        <div style={{ display: 'flex', gap: 8, marginBottom: 20, flexWrap: 'wrap' }}>
          <MacroCard label="Calories" value={totals.calories} max={DRI.calories} unit="kcal" color="#fa8c16" />
          <MacroCard label="Protein"  value={totals.protein_g} max={DRI.protein_g} unit="g" color={PRIMARY_COLOR} />
          <MacroCard label="Fat"      value={totals.fat_g}     max={DRI.fat_g}     unit="g" color="#f759ab" />
          <MacroCard label="Carbs"    value={totals.carb_g}    max={DRI.carb_g}    unit="g" color="#52c41a" />
        </div>

        {/* Add button */}
        <Button
          type="primary" icon={<PlusOutlined />} size="large" block
          style={{ background: PRIMARY_COLOR, borderColor: PRIMARY_COLOR, borderRadius: 10, marginBottom: 20 }}
          onClick={() => openAdd(undefined)}
        >
          Add entry
        </Button>

        {/* Meal sections */}
        <Spin spinning={loading}>
          {MEALS.map(({ value: mealType, label, emoji, color }) => {
            const mealEntries = entries.filter((e) => e.meal_type === mealType)
            const mealCal = mealEntries.reduce((sum, e) => sum + e.calories, 0)
            return (
              <div key={mealType} style={{ marginBottom: 16 }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <span style={{ fontSize: 18 }}>{emoji}</span>
                    <Text strong style={{ fontSize: 15, color }}>{label}</Text>
                    {mealCal > 0 && (
                      <Text type="secondary" style={{ fontSize: 12 }}>{Math.round(mealCal)} kcal</Text>
                    )}
                  </div>
                  <Button size="small" type="text" icon={<PlusOutlined />}
                    onClick={() => openAdd(mealType)} style={{ color: PRIMARY_COLOR, fontWeight: 600 }}>
                    Add
                  </Button>
                </div>
                {mealEntries.length === 0 ? (
                  <div onClick={() => openAdd(mealType)}
                    style={{ border: '1.5px dashed #E8E0D5', borderRadius: 10, padding: '12px', textAlign: 'center', cursor: 'pointer' }}>
                    <Text type="secondary" style={{ fontSize: 13 }}>+ Log your {label.toLowerCase()}</Text>
                  </div>
                ) : (
                  mealEntries.map((entry) => (
                    <EntryRow key={entry.id} entry={entry} onDelete={() => handleDelete(entry.id)} />
                  ))
                )}
              </div>
            )
          })}
          {entries.length === 0 && !loading && (
            <Empty description="Nothing logged yet — add your first entry above" style={{ marginTop: 32 }} />
          )}
        </Spin>
      </div>

      <AddLogModal
        open={addOpen}
        logDate={currentDate}
        defaultMeal={addMeal}
        onClose={() => setAddOpen(false)}
        onAdded={() => { setAddOpen(false); loadLogs() }}
      />
    </div>
  )
}
