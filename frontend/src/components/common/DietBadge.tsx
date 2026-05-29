import { Tag } from 'antd'
import { DIET_LABEL_META } from '@/constants'
import type { DietLabel } from '@/types'

interface Props {
  label: DietLabel
  size?: 'small' | 'default'
  onClick?: () => void
}

export function DietBadge({ label, size = 'default', onClick }: Props) {
  const meta = DIET_LABEL_META[label]
  if (!meta) return null

  return (
    <Tag
      title={meta.label}
      color={meta.color}
      style={{
        cursor: onClick ? 'pointer' : 'default',
        fontSize: size === 'small' ? 11 : 12,
        padding: size === 'small' ? '0 4px' : '0 7px',
        borderRadius: 12,
        userSelect: 'none',
      }}
      onClick={onClick}
    >
      {meta.emoji} {meta.label}
    </Tag>
  )
}

interface GroupProps {
  labels: DietLabel[]
  maxVisible?: number
  onLabelClick?: (label: DietLabel) => void
}

export function DietBadgeGroup({ labels, maxVisible = 4, onLabelClick }: GroupProps) {
  const visible = labels.slice(0, maxVisible)
  const hidden = labels.slice(maxVisible)

  return (
    <span>
      {visible.map((l) => (
        <DietBadge key={l} label={l} size="small" onClick={() => onLabelClick?.(l)} />
      ))}
      {hidden.length > 0 && (
        <Tag
          title={hidden.map((l) => DIET_LABEL_META[l]?.label).join(', ')}
          style={{ fontSize: 11, borderRadius: 12, cursor: 'default' }}
        >
          +{hidden.length}
        </Tag>
      )}
    </span>
  )
}
