import { Alert } from 'antd'
import { WarningFilled } from '@ant-design/icons'

interface Props {
  allergens: string[]
}

const ALLERGEN_EN: Record<string, string> = {
  peanut:    'Peanut',
  tree_nut:  'Tree nut',
  dairy:     'Dairy',
  gluten:    'Gluten',
  shellfish: 'Shellfish',
  soy:       'Soy',
  egg:       'Egg',
  sesame:    'Sesame',
}

export function AllergenWarning({ allergens }: Props) {
  if (!allergens || allergens.length === 0) return null

  const names = allergens.map((a) => ALLERGEN_EN[a] || a).join(', ')

  return (
    <Alert
      type="error"
      showIcon
      icon={<WarningFilled />}
      message={
        <span>
          <strong>Allergen warning: </strong>Contains {names}
        </span>
      }
      style={{ marginBottom: 8, padding: '4px 12px' }}
    />
  )
}
