import React from 'react'
import { Tag, Tooltip } from 'antd'
import { DIET_LABEL_META } from '@/constants'
import type { Confidence, DietLabel, LabelWithConfidence } from '@/types'

// 置信度 → 视觉样式
const CONFIDENCE_STYLE: Record<Confidence, React.CSSProperties> = {
  high:   { opacity: 1 },
  medium: { opacity: 0.7, borderStyle: 'dashed' },
  low:    { opacity: 0.45, borderStyle: 'dotted' },
}
const CONFIDENCE_LABEL: Record<Confidence, string> = {
  high:   '高置信度',
  medium: '中置信度',
  low:    '低置信度（仅供参考）',
}

interface Props {
  label: DietLabel
  size?: 'small' | 'default'
  confidence?: Confidence
  onClick?: () => void
}

export function DietBadge({ label, size = 'default', confidence, onClick }: Props) {
  const meta = DIET_LABEL_META[label]
  if (!meta) return null

  const confStyle = confidence ? CONFIDENCE_STYLE[confidence] : {}
  const tooltipTitle = confidence
    ? `${meta.label}（${CONFIDENCE_LABEL[confidence]}）`
    : meta.label

  return (
    <Tooltip title={tooltipTitle}>
      <Tag
        color={meta.color}
        style={{
          cursor: onClick ? 'pointer' : 'default',
          fontSize: size === 'small' ? 11 : 12,
          padding: size === 'small' ? '0 4px' : '0 7px',
          borderRadius: 12,
          userSelect: 'none',
          ...confStyle,
        }}
        onClick={onClick}
      >
        {meta.emoji} {meta.label}
        {confidence === 'low' && <span style={{ fontSize: 9, marginLeft: 2 }}>?</span>}
      </Tag>
    </Tooltip>
  )
}

interface GroupProps {
  labels: DietLabel[]
  labelsDetail?: LabelWithConfidence[]
  maxVisible?: number
  onLabelClick?: (label: DietLabel) => void
}

export function DietBadgeGroup({ labels, labelsDetail, maxVisible = 4, onLabelClick }: GroupProps) {
  // 构建 label → confidence 映射
  const confMap: Record<string, Confidence> = {}
  labelsDetail?.forEach(({ label, confidence }) => { confMap[label] = confidence })

  const visible = labels.slice(0, maxVisible)
  const hidden  = labels.slice(maxVisible)

  return (
    <span>
      {visible.map((l) => (
        <DietBadge
          key={l}
          label={l}
          size="small"
          confidence={confMap[l]}
          onClick={() => onLabelClick?.(l)}
        />
      ))}
      {hidden.length > 0 && (
        <Tooltip title={hidden.map((l) => DIET_LABEL_META[l]?.label).join('、')}>
          <Tag style={{ fontSize: 11, borderRadius: 12 }}>+{hidden.length}</Tag>
        </Tooltip>
      )}
    </span>
  )
}
