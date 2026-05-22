import { Progress, Space, Tooltip, Typography } from 'antd'

const { Text } = Typography

// 每日推荐摄入量（参考值）
const DRI = {
  calories: 2000,
  protein_g: 60,
  fat_g: 65,
  carb_g: 300,
}

interface Props {
  totals: {
    calories: number
    protein_g: number
    fat_g: number
    carb_g: number
  }
}

function NutrientRow({
  label, value, max, unit, color,
}: {
  label: string; value: number; max: number; unit: string; color: string
}) {
  const pct = Math.min(Math.round((value / max) * 100), 100)
  return (
    <div style={{ marginBottom: 8 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 2 }}>
        <Text style={{ fontSize: 13 }}>{label}</Text>
        <Tooltip title={`推荐摄入 ${max}${unit}`}>
          <Text style={{ fontSize: 13, color: pct > 100 ? '#ff4d4f' : '#666' }}>
            {value.toFixed(0)}/{max}{unit} ({pct}%)
          </Text>
        </Tooltip>
      </div>
      <Progress
        percent={pct}
        showInfo={false}
        strokeColor={pct > 100 ? '#ff4d4f' : color}
        trailColor="#f0f0f0"
        size="small"
      />
    </div>
  )
}

export function NutritionBar({ totals }: Props) {
  return (
    <div style={{ background: '#fff', borderRadius: 8, padding: 16 }}>
      <Text strong style={{ fontSize: 14, display: 'block', marginBottom: 12 }}>
        今日营养摄入
      </Text>
      <NutrientRow
        label="热量"
        value={totals.calories}
        max={DRI.calories}
        unit="kcal"
        color="#fa8c16"
      />
      <NutrientRow
        label="蛋白质"
        value={totals.protein_g}
        max={DRI.protein_g}
        unit="g"
        color="#1677ff"
      />
      <NutrientRow
        label="脂肪"
        value={totals.fat_g}
        max={DRI.fat_g}
        unit="g"
        color="#f759ab"
      />
      <NutrientRow
        label="碳水"
        value={totals.carb_g}
        max={DRI.carb_g}
        unit="g"
        color="#52c41a"
      />
    </div>
  )
}
