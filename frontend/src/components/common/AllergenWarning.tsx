import { Alert } from 'antd'
import { WarningFilled } from '@ant-design/icons'

interface Props {
  allergens: string[]
}

const ALLERGEN_ZH: Record<string, string> = {
  peanut: '花生',
  tree_nut: '坚果',
  dairy: '乳制品',
  gluten: '麸质',
  shellfish: '贝类',
  soy: '大豆',
  egg: '鸡蛋',
  sesame: '芝麻',
}

export function AllergenWarning({ allergens }: Props) {
  if (!allergens || allergens.length === 0) return null

  const names = allergens.map((a) => ALLERGEN_ZH[a] || a).join('、')

  return (
    <Alert
      type="error"
      showIcon
      icon={<WarningFilled />}
      message={
        <span>
          <strong>过敏原警告：</strong>该餐厅含有 {names}
        </span>
      }
      style={{ marginBottom: 8, padding: '4px 12px' }}
    />
  )
}
