import { Alert } from 'antd'
import { WarningFilled } from '@ant-design/icons'
import { useLang } from '@/i18n/LanguageContext'

interface Props {
  allergens: string[]
}

export function AllergenWarning({ allergens }: Props) {
  const { t } = useLang()
  if (!allergens || allergens.length === 0) return null

  const nameMap: Record<string, keyof typeof t> = {
    peanut:    'allergen_peanut',
    tree_nut:  'allergen_tree_nut',
    dairy:     'allergen_dairy',
    gluten:    'allergen_gluten',
    shellfish: 'allergen_shellfish',
    soy:       'allergen_soy',
    egg:       'allergen_egg',
    sesame:    'allergen_sesame',
    fish:      'allergen_fish',
  }

  const names = allergens.map((a) => t[nameMap[a]] as string || a).join(', ')

  return (
    <Alert
      type="error"
      showIcon
      icon={<WarningFilled />}
      message={
        <span>
          <strong>{t.allergen_contains}</strong> {names}
        </span>
      }
      style={{ marginBottom: 8, padding: '4px 12px' }}
    />
  )
}
