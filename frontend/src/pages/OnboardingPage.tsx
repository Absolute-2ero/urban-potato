import { useState } from 'react'
import { Button, InputNumber, Steps, Typography, message } from 'antd'
import { CheckOutlined } from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'
import { useAuthStore } from '@/stores/authStore'
import { savePrefs, saveGoals, DEFAULT_GOALS, type DailyGoals } from '@/utils/prefs'
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

const GOAL_PRESETS = [
  { label: '⚖️ Weight loss',   goals: { calories: 1500, protein_g: 80, fat_g: 50, carb_g: 150 } },
  { label: '🏃 Maintenance',   goals: { calories: 2000, protein_g: 60, fat_g: 65, carb_g: 300 } },
  { label: '💪 Muscle gain',   goals: { calories: 2500, protein_g: 120, fat_g: 70, carb_g: 280 } },
]

function ToggleChips({
  options, selected, color, onToggle,
}: {
  options: { value: string; label: string; emoji: string }[]
  selected: string[]
  color: string
  onToggle: (v: string) => void
}) {
  return (
    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 10, marginBottom: 28 }}>
      {options.map((opt) => {
        const active = selected.includes(opt.value)
        return (
          <button key={opt.value} onClick={() => onToggle(opt.value)} style={{
            display: 'flex', alignItems: 'center', gap: 7,
            padding: '9px 16px', borderRadius: 999,
            border: `2px solid ${active ? color : '#E8E0D5'}`,
            background: active ? color + '15' : '#fff',
            color: active ? color : '#6B7A7A',
            fontSize: 14, fontWeight: active ? 600 : 400,
            cursor: 'pointer', outline: 'none', transition: 'all 0.15s',
          }}>
            <span>{opt.emoji}</span>
            <span>{opt.label}</span>
            {active && <CheckOutlined style={{ fontSize: 11 }} />}
          </button>
        )
      })}
    </div>
  )
}

function GoalRow({ label, value, unit, color, onChange }: {
  label: string; value: number; unit: string; color: string; onChange: (v: number) => void
}) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 14 }}>
      <div>
        <Text strong style={{ color, fontSize: 14 }}>{label}</Text>
        <Text type="secondary" style={{ fontSize: 12, marginLeft: 6 }}>{unit}</Text>
      </div>
      <InputNumber
        min={0} max={unit === 'kcal' ? 6000 : 500}
        value={value}
        onChange={(v) => onChange(v ?? 0)}
        style={{ width: 110 }}
        size="middle"
        addonAfter={unit}
      />
    </div>
  )
}

export default function OnboardingPage() {
  const navigate = useNavigate()
  const { user } = useAuthStore()
  const [step, setStep] = useState(0)
  const [goals, setGoals] = useState<DailyGoals>(DEFAULT_GOALS)
  const [nutritionLabels, setNutritionLabels] = useState<string[]>([])
  const [dietLabels, setDietLabels] = useState<string[]>([])
  const [selectedAllergies, setSelectedAllergies] = useState<string[]>([])

  const toggler = (setter: React.Dispatch<React.SetStateAction<string[]>>) => (v: string) =>
    setter((prev) => prev.includes(v) ? prev.filter((x) => x !== v) : [...prev, v])

  const finish = () => {
    if (user) {
      const allergyDietLabels = ALLERGY_OPTIONS
        .filter((o) => o.isDietLabel && selectedAllergies.includes(o.value))
        .map((o) => o.value)
      const allergyRestrictions = selectedAllergies.filter(
        (v) => !ALLERGY_OPTIONS.find((o) => o.value === v)?.isDietLabel
      )
      savePrefs(user.id, {
        nutritionLabels,
        dietLabels: [...dietLabels, ...allergyDietLabels],
        allergyRestrictions,
      })
      saveGoals(user.id, goals)
      message.success('Preferences saved!')
    }
    navigate('/search')
  }

  const cardStyle: React.CSSProperties = {
    background: '#fff', borderRadius: 16, padding: '28px 24px',
    boxShadow: '0 2px 16px rgba(30,42,42,0.07)', border: '1px solid #E8E0D5',
  }

  return (
    <div style={{ minHeight: 'calc(100vh - 52px)', background: '#F7F3EE', display: 'flex', alignItems: 'flex-start', justifyContent: 'center', padding: '40px 16px 80px' }}>
      <div style={{ width: '100%', maxWidth: 560 }}>
        <div style={{ textAlign: 'center', marginBottom: 36 }}>
          <div style={{ fontSize: 40, marginBottom: 8 }}>🥗</div>
          <Title level={2} style={{ margin: '0 0 6px', color: PRIMARY_COLOR }}>
            Set your preferences
          </Title>
          <Text type="secondary" style={{ fontSize: 15 }}>
            Personalise your defaults — change anytime in your profile
          </Text>
        </div>

        <Steps
          current={step}
          size="small"
          style={{ marginBottom: 28 }}
          items={[
            { title: '🎯 Goals' },
            { title: '🥗 Health' },
            { title: '🌿 Diet' },
            { title: '⚠️ Allergies' },
          ]}
        />

        {/* Step 0: Daily goals */}
        {step === 0 && (
          <div style={cardStyle}>
            <Title level={4} style={{ marginTop: 0, marginBottom: 4, color: '#E65100' }}>Daily nutrition goals</Title>
            <Text type="secondary" style={{ display: 'block', marginBottom: 20, fontSize: 14 }}>
              Set targets for your diet tracker. Start with a preset or customise below.
            </Text>

            {/* Presets */}
            <div style={{ display: 'flex', gap: 8, marginBottom: 20, flexWrap: 'wrap' }}>
              {GOAL_PRESETS.map((p) => (
                <button
                  key={p.label}
                  onClick={() => setGoals(p.goals)}
                  style={{
                    padding: '7px 14px', borderRadius: 999, fontSize: 13,
                    border: `2px solid ${JSON.stringify(goals) === JSON.stringify(p.goals) ? '#E65100' : '#E8E0D5'}`,
                    background: JSON.stringify(goals) === JSON.stringify(p.goals) ? '#FFF3E0' : '#fff',
                    color: JSON.stringify(goals) === JSON.stringify(p.goals) ? '#E65100' : '#6B7A7A',
                    cursor: 'pointer', outline: 'none', fontWeight: JSON.stringify(goals) === JSON.stringify(p.goals) ? 600 : 400,
                    transition: 'all 0.15s',
                  }}
                >
                  {p.label}
                </button>
              ))}
            </div>

            <GoalRow label="Calories" value={goals.calories} unit="kcal" color="#fa8c16"
              onChange={(v) => setGoals((g) => ({ ...g, calories: v }))} />
            <GoalRow label="Protein"  value={goals.protein_g} unit="g"    color={PRIMARY_COLOR}
              onChange={(v) => setGoals((g) => ({ ...g, protein_g: v }))} />
            <GoalRow label="Fat"      value={goals.fat_g}     unit="g"    color="#f759ab"
              onChange={(v) => setGoals((g) => ({ ...g, fat_g: v }))} />
            <GoalRow label="Carbs"    value={goals.carb_g}    unit="g"    color="#52c41a"
              onChange={(v) => setGoals((g) => ({ ...g, carb_g: v }))} />

            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: 8 }}>
              <Button type="text" onClick={() => navigate('/search')} style={{ color: '#AAB4B4' }}>
                Skip for now
              </Button>
              <Button type="primary" onClick={() => setStep(1)} style={{ background: PRIMARY_COLOR, borderColor: PRIMARY_COLOR }}>
                Next: Health →
              </Button>
            </div>
          </div>
        )}

        {/* Step 1: Health */}
        {step === 1 && (
          <div style={cardStyle}>
            <Title level={4} style={{ marginTop: 0, marginBottom: 4, color: '#6A1B9A' }}>Any health goals?</Title>
            <Text type="secondary" style={{ display: 'block', marginBottom: 20, fontSize: 14 }}>
              Filter search results by nutrition focus
            </Text>
            <ToggleChips options={NUTRITION_OPTIONS} selected={nutritionLabels} color="#6A1B9A" onToggle={toggler(setNutritionLabels)} />
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <Button type="text" onClick={() => setStep(0)}>← Back</Button>
              <Button type="primary" onClick={() => setStep(2)} style={{ background: PRIMARY_COLOR, borderColor: PRIMARY_COLOR }}>
                Next: Diet →
              </Button>
            </div>
          </div>
        )}

        {/* Step 2: Diet */}
        {step === 2 && (
          <div style={cardStyle}>
            <Title level={4} style={{ marginTop: 0, marginBottom: 4, color: '#2D9B5A' }}>What's your diet?</Title>
            <Text type="secondary" style={{ display: 'block', marginBottom: 20, fontSize: 14 }}>
              Select all dietary lifestyles that apply
            </Text>
            <ToggleChips options={DIET_OPTIONS} selected={dietLabels} color="#2D9B5A" onToggle={toggler(setDietLabels)} />
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <Button type="text" onClick={() => setStep(1)}>← Back</Button>
              <Button type="primary" onClick={() => setStep(3)} style={{ background: PRIMARY_COLOR, borderColor: PRIMARY_COLOR }}>
                Next: Allergies →
              </Button>
            </div>
          </div>
        )}

        {/* Step 3: Allergies */}
        {step === 3 && (
          <div style={cardStyle}>
            <Title level={4} style={{ marginTop: 0, marginBottom: 4, color: '#E85454' }}>Any allergies or avoidances?</Title>
            <Text type="secondary" style={{ display: 'block', marginBottom: 20, fontSize: 14 }}>
              We'll flag warnings when these ingredients appear
            </Text>
            <ToggleChips options={ALLERGY_OPTIONS} selected={selectedAllergies} color="#E85454" onToggle={toggler(setSelectedAllergies)} />
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <Button type="text" onClick={() => setStep(2)}>← Back</Button>
              <Button type="primary" icon={<CheckOutlined />} onClick={finish}
                style={{ background: PRIMARY_COLOR, borderColor: PRIMARY_COLOR }}>
                Save & start
              </Button>
            </div>
          </div>
        )}

        <div style={{ textAlign: 'center', marginTop: 16 }}>
          <Button type="link" onClick={() => navigate('/search')} style={{ color: '#AAB4B4', fontSize: 13 }}>
            I'll set this up later in Profile
          </Button>
        </div>
      </div>
    </div>
  )
}
