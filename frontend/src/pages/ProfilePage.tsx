import { useEffect, useState } from 'react'
import { Button, DatePicker, InputNumber, Modal, Typography, message } from 'antd'
import { CheckOutlined, DeleteOutlined, DownloadOutlined } from '@ant-design/icons'
import type { Dayjs } from 'dayjs'
import dayjs from 'dayjs'
import { exportLogs } from '@/api/diet'
import { useNavigate } from 'react-router-dom'
import { useAuthStore } from '@/stores/authStore'
import { loadPrefs, savePrefs, loadGoals, saveGoals, DEFAULT_GOALS, type SavedPrefs, type DailyGoals } from '@/utils/prefs'
import { PRIMARY_COLOR } from '@/constants'

const { Title, Text } = Typography

const NUTRITION_OPTIONS = [
  { value: 'low_fat', label: 'Low-fat', emoji: '💧' },
  { value: 'low_sugar', label: 'Low-sugar', emoji: '🍬' },
  { value: 'low_sodium', label: 'Low-sodium', emoji: '🧂' },
  { value: 'high_protein', label: 'High-protein', emoji: '💪' },
  { value: 'no_added_oil', label: 'Low oil', emoji: '🫙' },
]

const DIET_OPTIONS = [
  { value: 'vegetarian', label: 'Vegetarian', emoji: '🥗' },
  { value: 'vegan', label: 'Vegan', emoji: '🌿' },
  { value: 'halal', label: 'Halal', emoji: '☪️' },
  { value: 'kosher', label: 'Kosher', emoji: '✡️' },
  { value: 'keto', label: 'Keto', emoji: '🥑' },
]

const ALLERGY_OPTIONS = [
  { value: 'peanut-free', label: 'Peanut-free', emoji: '🥜', isDietLabel: false },
  { value: 'dairy-free', label: 'Dairy-free', emoji: '🥛', isDietLabel: true },
  { value: 'gluten-free', label: 'Gluten-free', emoji: '🌾', isDietLabel: true },
  { value: 'seafood-free', label: 'Seafood-free', emoji: '🦐', isDietLabel: false },
  { value: 'soy-free', label: 'Soy-free', emoji: '🫘', isDietLabel: false },
  { value: 'no_spicy', label: 'No spicy', emoji: '🌶️', isDietLabel: false },
]

function ToggleChips({
  options,
  selected,
  color,
  onToggle,
}: {
  options: { value: string; label: string; emoji: string }[]
  selected: string[]
  color: string
  onToggle: (v: string) => void
}) {
  return (
    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 9 }}>
      {options.map((opt) => {
        const active = selected.includes(opt.value)
        return (
          <button
            key={opt.value}
            onClick={() => onToggle(opt.value)}
            style={{
              display: 'flex', alignItems: 'center', gap: 6,
              padding: '8px 14px', borderRadius: 999,
              border: `2px solid ${active ? color : '#E8E0D5'}`,
              background: active ? color + '15' : '#FAFAF8',
              color: active ? color : '#6B7A7A',
              fontSize: 13, fontWeight: active ? 600 : 400,
              cursor: 'pointer', outline: 'none', transition: 'all 0.15s',
            }}
          >
            <span>{opt.emoji}</span>
            <span>{opt.label}</span>
            {active && <CheckOutlined style={{ fontSize: 10 }} />}
          </button>
        )
      })}
    </div>
  )
}

function PrefSection({
  emoji, title, subtitle, color, children,
}: {
  emoji: string; title: string; subtitle: string; color: string; children: React.ReactNode
}) {
  return (
    <div style={{ background: '#fff', borderRadius: 14, padding: '20px 20px', border: '1px solid #E8E0D5', marginBottom: 14 }}>
      <div style={{ marginBottom: 12 }}>
        <Text strong style={{ fontSize: 15, color, display: 'block' }}>{emoji} {title}</Text>
        <Text type="secondary" style={{ fontSize: 13 }}>{subtitle}</Text>
      </div>
      {children}
    </div>
  )
}

export default function ProfilePage() {
  const { user, deleteAccount } = useAuthStore()
  const navigate = useNavigate()
  const [prefs, setPrefs] = useState<SavedPrefs>({ nutritionLabels: [], dietLabels: [], allergyRestrictions: [] })
  const [goals, setGoals] = useState<DailyGoals>(DEFAULT_GOALS)
  const [deleting, setDeleting] = useState(false)
  const [exportOpen, setExportOpen] = useState(false)
  const [exportRange, setExportRange] = useState<[Dayjs, Dayjs]>([dayjs().subtract(30, 'day'), dayjs()])
  const [exporting, setExporting] = useState(false)

  useEffect(() => {
    if (user) {
      setPrefs(loadPrefs(user.id))
      setGoals(loadGoals(user.id))
    }
  }, [user?.id])

  if (!user) {
    return (
      <div style={{ textAlign: 'center', padding: 80 }}>
        <Title level={4}>Please sign in first</Title>
        <Button type="primary" onClick={() => navigate('/login')} style={{ background: PRIMARY_COLOR, borderColor: PRIMARY_COLOR }}>
          Sign in
        </Button>
      </div>
    )
  }

  const toggleNutrition = (v: string) =>
    setPrefs((p) => ({
      ...p,
      nutritionLabels: p.nutritionLabels.includes(v)
        ? p.nutritionLabels.filter((x) => x !== v)
        : [...p.nutritionLabels, v],
    }))

  const toggleDiet = (v: string) =>
    setPrefs((p) => ({
      ...p,
      dietLabels: p.dietLabels.includes(v)
        ? p.dietLabels.filter((x) => x !== v)
        : [...p.dietLabels, v],
    }))

  const toggleAllergy = (v: string) => {
    const opt = ALLERGY_OPTIONS.find((o) => o.value === v)!
    if (opt.isDietLabel) {
      setPrefs((p) => ({
        ...p,
        dietLabels: p.dietLabels.includes(v)
          ? p.dietLabels.filter((x) => x !== v)
          : [...p.dietLabels, v],
      }))
    } else {
      setPrefs((p) => ({
        ...p,
        allergyRestrictions: p.allergyRestrictions.includes(v)
          ? p.allergyRestrictions.filter((x) => x !== v)
          : [...p.allergyRestrictions, v],
      }))
    }
  }

  // Which allergy option values are currently selected (from either dietLabels or allergyRestrictions)
  const selectedAllergies = ALLERGY_OPTIONS
    .filter((o) => o.isDietLabel ? prefs.dietLabels.includes(o.value) : prefs.allergyRestrictions.includes(o.value))
    .map((o) => o.value)

  const handleSave = () => {
    savePrefs(user.id, prefs)
    saveGoals(user.id, goals)
    message.success('Preferences saved')
  }

  const handleExport = async () => {
    setExporting(true)
    try {
      const blob = await exportLogs(
        exportRange[0].format('YYYY-MM-DD'),
        exportRange[1].format('YYYY-MM-DD'),
      )
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `diet_${exportRange[0].format('YYYY-MM-DD')}_${exportRange[1].format('YYYY-MM-DD')}.csv`
      a.click()
      URL.revokeObjectURL(url)
      setExportOpen(false)
    } finally {
      setExporting(false)
    }
  }

  const handleDeleteAccount = () => {
    Modal.confirm({
      title: 'Delete your account?',
      content: 'This will permanently remove your account and all saved data. This cannot be undone.',
      okText: 'Delete account',
      okButtonProps: { danger: true },
      cancelText: 'Cancel',
      onOk: async () => {
        setDeleting(true)
        try {
          await deleteAccount()
          navigate('/')
        } catch {
          message.error('Failed to delete account — please try again')
        } finally {
          setDeleting(false)
        }
      },
    })
  }

  return (
    <div style={{ background: '#F7F3EE', minHeight: 'calc(100vh - 52px)', padding: '32px 16px 60px' }}>
      <div style={{ maxWidth: 560, margin: '0 auto' }}>

        {/* User info */}
        <div style={{ background: '#fff', borderRadius: 14, padding: '20px 20px', border: '1px solid #E8E0D5', marginBottom: 20 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
            <div style={{
              width: 48, height: 48, borderRadius: '50%',
              background: PRIMARY_COLOR + '20', border: `2px solid ${PRIMARY_COLOR}`,
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              fontSize: 20, color: PRIMARY_COLOR, fontWeight: 700,
            }}>
              {user.username[0].toUpperCase()}
            </div>
            <div>
              <Text strong style={{ fontSize: 16, display: 'block' }}>{user.username}</Text>
              {user.email && <Text type="secondary" style={{ fontSize: 13 }}>{user.email}</Text>}
            </div>
          </div>
        </div>

        {/* Preferences heading */}
        <Text style={{ fontSize: 11, color: '#AAB4B4', textTransform: 'uppercase', letterSpacing: 1.2, fontWeight: 600, display: 'block', marginBottom: 12 }}>
          Default preferences
        </Text>

        {/* Health */}
        <PrefSection emoji="🥗" title="Health" subtitle="Nutritional goals applied to every search" color="#6A1B9A">
          <ToggleChips options={NUTRITION_OPTIONS} selected={prefs.nutritionLabels} color="#6A1B9A" onToggle={toggleNutrition} />
        </PrefSection>

        {/* Diet */}
        <PrefSection emoji="🌿" title="Diet" subtitle="Your dietary lifestyle preferences" color="#2D9B5A">
          <ToggleChips options={DIET_OPTIONS} selected={prefs.dietLabels} color="#2D9B5A" onToggle={toggleDiet} />
        </PrefSection>

        {/* Allergies */}
        <PrefSection emoji="⚠️" title="Allergies" subtitle="Ingredients and foods you avoid" color="#E85454">
          <ToggleChips options={ALLERGY_OPTIONS} selected={selectedAllergies} color="#E85454" onToggle={toggleAllergy} />
        </PrefSection>

        {/* Daily goals */}
        <PrefSection emoji="🎯" title="Daily nutrition goals" subtitle="Used for progress bars on your diet tracker" color="#E65100">
          {([
            { key: 'calories', label: 'Calories', unit: 'kcal', color: '#fa8c16', max: 6000 },
            { key: 'protein_g', label: 'Protein', unit: 'g', color: '#2D9B5A', max: 500 },
            { key: 'fat_g', label: 'Fat', unit: 'g', color: '#f759ab', max: 500 },
            { key: 'carb_g', label: 'Carbs', unit: 'g', color: '#52c41a', max: 500 },
          ] as { key: keyof DailyGoals; label: string; unit: string; color: string; max: number }[]).map(({ key, label, unit, color, max }) => (
            <div key={key} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
              <Text strong style={{ color, fontSize: 14 }}>{label}</Text>
              <InputNumber
                min={0} max={max} value={goals[key]}
                onChange={(v) => setGoals((g) => ({ ...g, [key]: v ?? 0 }))}
                style={{ width: 130 }}
                addonAfter={unit}
              />
            </div>
          ))}
          <Button size="small" type="text" style={{ color: '#AAB4B4', padding: 0, marginTop: 4 }}
            onClick={() => setGoals(DEFAULT_GOALS)}>
            Reset to defaults
          </Button>
        </PrefSection>

        {/* Save button */}
        <Button
          type="primary"
          block
          size="large"
          onClick={handleSave}
          style={{ background: PRIMARY_COLOR, borderColor: PRIMARY_COLOR, borderRadius: 10, marginBottom: 32 }}
        >
          Save preferences
        </Button>

        {/* Data */}
        <div style={{ borderTop: '1px solid #F0E8E0', paddingTop: 24, marginBottom: 24 }}>
          <Text style={{ fontSize: 11, color: '#AAB4B4', textTransform: 'uppercase', letterSpacing: 1.2, fontWeight: 600, display: 'block', marginBottom: 12 }}>
            Your data
          </Text>
          <Button
            icon={<DownloadOutlined />}
            onClick={() => setExportOpen(true)}
            style={{ borderRadius: 8 }}
          >
            Export diet history
          </Button>
        </div>

        {/* Danger zone */}
        <div style={{ borderTop: '1px solid #F0E8E0', paddingTop: 24 }}>
          <Text style={{ fontSize: 11, color: '#AAB4B4', textTransform: 'uppercase', letterSpacing: 1.2, fontWeight: 600, display: 'block', marginBottom: 12 }}>
            Danger zone
          </Text>
          <Button
            danger
            icon={<DeleteOutlined />}
            onClick={handleDeleteAccount}
            loading={deleting}
            style={{ borderRadius: 8 }}
          >
            Delete account
          </Button>
        </div>
      </div>

      <Modal
        title="Export diet history"
        open={exportOpen}
        onCancel={() => setExportOpen(false)}
        onOk={handleExport}
        okText="Download CSV"
        confirmLoading={exporting}
        okButtonProps={{ style: { background: PRIMARY_COLOR, borderColor: PRIMARY_COLOR } }}
      >
        <div style={{ padding: '16px 0' }}>
          <Text type="secondary" style={{ display: 'block', marginBottom: 12 }}>
            Select the date range to export:
          </Text>
          <DatePicker.RangePicker
            value={exportRange}
            onChange={(v) => { if (v?.[0] && v?.[1]) setExportRange([v[0], v[1]]) }}
            disabledDate={(d) => d.isAfter(dayjs(), 'day')}
            presets={[
              { label: 'Last 7 days',   value: [dayjs().subtract(7, 'day'),   dayjs()] },
              { label: 'Last 30 days',  value: [dayjs().subtract(30, 'day'),  dayjs()] },
              { label: 'Last 3 months', value: [dayjs().subtract(3, 'month'), dayjs()] },
            ]}
            style={{ width: '100%' }}
          />
        </div>
      </Modal>
    </div>
  )
}
