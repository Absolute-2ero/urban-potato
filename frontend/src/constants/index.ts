import type { DietLabel } from '@/types'

export const DIET_LABEL_META: Record<
  DietLabel,
  { label: string; color: string; emoji: string }
> = {
  vegan:           { label: 'Vegan',         color: '#2D9B5A', emoji: '🌿' },
  vegetarian:      { label: 'Vegetarian',    color: '#52C41A', emoji: '🥗' },
  halal:           { label: 'Halal',         color: '#13C2C2', emoji: '☪️' },
  kosher:          { label: 'Kosher',        color: '#722ED1', emoji: '✡️' },
  organic:         { label: 'Organic',       color: '#73D13D', emoji: '🌱' },
  'gluten-free':   { label: 'Gluten-free',   color: '#FA8C16', emoji: '🌾' },
  'dairy-free':    { label: 'Dairy-free',    color: '#FFC53D', emoji: '🥛' },
  keto:            { label: 'Keto',          color: '#F759AB', emoji: '🥑' },
  'high-protein':  { label: 'High-protein',  color: '#1677FF', emoji: '💪' },
  'low-carb':      { label: 'Low-carb',      color: '#40A9FF', emoji: '🍞' },
  'low-calorie':   { label: 'Low-calorie',   color: '#69B1FF', emoji: '🔥' },
  'low-sodium':    { label: 'Low-sodium',    color: '#95DE64', emoji: '🧂' },
  'nut-free':      { label: 'Nut-free',      color: '#FF7A45', emoji: '🥜' },
  'shellfish-free':{ label: 'Shellfish-free',color: '#36CFC9', emoji: '🦞' },
  'soy-free':      { label: 'Soy-free',      color: '#B7EB8F', emoji: '🫘' },
}

export const ALL_DIET_LABELS = Object.keys(DIET_LABEL_META) as DietLabel[]

export const PRICE_LEVEL_META: Record<number, { label: string; icon: string }> = {
  1: { label: '$ Budget',      icon: '$' },
  2: { label: '$$ Moderate',   icon: '$$' },
  3: { label: '$$$ Pricey',    icon: '$$$' },
  4: { label: '$$$$ Fine dining', icon: '$$$$' },
}

export const SORT_MODES = [
  { value: 'default',        label: 'Best match' },
  { value: 'diet_first',     label: 'Diet match first' },
  { value: 'rating_first',   label: 'Highest rated' },
  { value: 'distance_first', label: 'Nearest first' },
]

export const COMMON_ALLERGENS = [
  { value: 'peanut',    label: 'Peanut' },
  { value: 'tree_nut',  label: 'Tree nut' },
  { value: 'dairy',     label: 'Dairy' },
  { value: 'gluten',    label: 'Gluten / Wheat' },
  { value: 'shellfish', label: 'Shellfish' },
  { value: 'soy',       label: 'Soy' },
  { value: 'egg',       label: 'Egg' },
  { value: 'sesame',    label: 'Sesame' },
]

export const MEAL_TYPES = [
  { value: 'breakfast', label: 'Breakfast' },
  { value: 'lunch',     label: 'Lunch' },
  { value: 'dinner',    label: 'Dinner' },
  { value: 'snack',     label: 'Snack' },
]

export const PRIMARY_COLOR = '#2D9B5A'
export const DANGER_COLOR  = '#FF4D4F'
export const WARNING_COLOR = '#FAAD14'
