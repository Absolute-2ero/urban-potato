import type { DietLabel } from '@/types'

// ── 饮食标签元数据 ────────────────────────────────────────────────────────────
export const DIET_LABEL_META: Record<
  DietLabel,
  { label: string; color: string; emoji: string }
> = {
  vegan:        { label: '纯素',   color: '#2D9B5A', emoji: '🌿' },
  vegetarian:   { label: '素食',   color: '#52C41A', emoji: '🥗' },
  halal:        { label: '清真',   color: '#13C2C2', emoji: '☪️' },
  kosher:       { label: '犹太洁食', color: '#722ED1', emoji: '✡️' },
  organic:      { label: '有机',   color: '#73D13D', emoji: '🌱' },
  'gluten-free':{ label: '无麸质', color: '#FA8C16', emoji: '🌾' },
  'dairy-free': { label: '无乳制品', color: '#FFC53D', emoji: '🥛' },
  keto:         { label: '生酮',   color: '#F759AB', emoji: '🥑' },
  'high-protein': { label: '高蛋白', color: '#1677FF', emoji: '💪' },
  'low-carb':   { label: '低碳水', color: '#40A9FF', emoji: '🍞' },
  'low-calorie':{ label: '低卡',   color: '#69B1FF', emoji: '🔥' },
  'low-sodium': { label: '低钠',   color: '#95DE64', emoji: '🧂' },
  'nut-free':   { label: '无坚果', color: '#FF7A45', emoji: '🥜' },
  'shellfish-free': { label: '无贝类', color: '#36CFC9', emoji: '🦞' },
  'soy-free':   { label: '无大豆', color: '#B7EB8F', emoji: '🫘' },
}

export const ALL_DIET_LABELS = Object.keys(DIET_LABEL_META) as DietLabel[]

// ── 价格档次 ──────────────────────────────────────────────────────────────────
export const PRICE_LEVEL_META: Record<number, { label: string; icon: string }> = {
  1: { label: '¥ 经济', icon: '¥' },
  2: { label: '¥¥ 实惠', icon: '¥¥' },
  3: { label: '¥¥¥ 中档', icon: '¥¥¥' },
  4: { label: '¥¥¥¥ 高档', icon: '¥¥¥¥' },
}

// ── 排序模式 ──────────────────────────────────────────────────────────────────
export const SORT_MODES = [
  { value: 'default',       label: '综合排序' },
  { value: 'diet_first',    label: '饮食匹配优先' },
  { value: 'rating_first',  label: '评分优先' },
  { value: 'distance_first',label: '距离优先' },
]

// ── 过敏原选项 ────────────────────────────────────────────────────────────────
export const COMMON_ALLERGENS = [
  { value: 'peanut',    label: '花生' },
  { value: 'tree_nut',  label: '坚果' },
  { value: 'dairy',     label: '乳制品' },
  { value: 'gluten',    label: '麸质/小麦' },
  { value: 'shellfish', label: '贝类/海鲜' },
  { value: 'soy',       label: '大豆' },
  { value: 'egg',       label: '鸡蛋' },
  { value: 'sesame',    label: '芝麻' },
]

// ── 膳食类型 ──────────────────────────────────────────────────────────────────
export const MEAL_TYPES = [
  { value: 'breakfast', label: '早餐' },
  { value: 'lunch',     label: '午餐' },
  { value: 'dinner',    label: '晚餐' },
  { value: 'snack',     label: '加餐' },
]

// ── 主题色 ────────────────────────────────────────────────────────────────────
export const PRIMARY_COLOR = '#2D9B5A'
export const DANGER_COLOR  = '#FF4D4F'
export const WARNING_COLOR = '#FAAD14'
