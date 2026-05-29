// ── 用户 ──────────────────────────────────────────────────────────────────────
export interface User {
  id: string
  username: string
  email?: string
  created_at: string
}

export interface UserCreate {
  username: string
  email?: string
  password: string
}

export interface UserLogin {
  username: string
  password: string
}

// ── 饮食档案 ──────────────────────────────────────────────────────────────────
export type DietLabel =
  | 'vegan' | 'vegetarian' | 'halal' | 'kosher' | 'organic'
  | 'gluten-free' | 'dairy-free' | 'keto' | 'high-protein' | 'low-carb'
  | 'low-calorie' | 'low-sodium' | 'nut-free' | 'shellfish-free' | 'soy-free'

export interface DietProfile {
  user_id: string
  diet_labels: DietLabel[]
  allergens: string[]
  price_pref?: 1 | 2 | 3 | 4
  updated_at?: string
}

export interface DietProfileUpdate {
  diet_labels: DietLabel[]
  allergens: string[]
  price_pref?: 1 | 2 | 3 | 4
}

// ── 食物 ──────────────────────────────────────────────────────────────────────
export interface FoodItem {
  food_id?: number
  name_zh: string
  name_en?: string
  name_pinyin?: string
  calories_per_100g: number
  protein_g: number
  fat_g: number
  carb_g: number
  sodium_mg: number
  fiber_g: number
  diet_labels: DietLabel[]
}

export type FoodSource = 'database' | 'llm_estimated' | 'not_found'

export interface FoodSearchResult {
  items: FoodItem[]
  source: FoodSource
  requires_confirm: boolean
}

// ── 饮食日志 ──────────────────────────────────────────────────────────────────
export type MealType = 'breakfast' | 'lunch' | 'dinner' | 'snack'

export interface FoodLogCreate {
  food_id?: number
  food_name_snapshot: string
  log_date: string      // YYYY-MM-DD
  meal_type: MealType
  amount_g: number
  calories: number
  protein_g: number
  fat_g: number
  carb_g: number
  notes?: string
}

export interface FoodLogEntry extends FoodLogCreate {
  id: number
  user_id: string
  created_at: string
}

export interface DailyTotals {
  calories: number
  protein_g: number
  fat_g: number
  carb_g: number
}

export interface DietLogDay {
  entries: FoodLogEntry[]
  totals: DailyTotals
}

// ── 餐厅 ──────────────────────────────────────────────────────────────────────
export interface GeoPoint {
  lat: number
  lng: number
}

export interface MenuItem {
  item_id?: string
  name: string
  price?: number
  diet_labels?: DietLabel[]
  allergens?: string[]
  calories?: number
  protein?: number
  fat?: number
  carbs?: number
}

export interface Restaurant {
  restaurant_id: string
  name: string
  name_en?: string
  description?: string
  cuisine_type?: string
  address?: string
  phone?: string
  price_level?: 1 | 2 | 3 | 4
  rating?: number
  rating_count?: number
  geo?: GeoPoint
  diet_labels: DietLabel[]
  allergens: string[]
  allergen_free: string[]
  images?: string[]
  menu_items?: MenuItem[]
  matched_dishes?: MenuItem[]   // server-side inner_hits from ES nested query
  // ranking fields
  _final_score?: number
  _distance_m?: number
  _allergen_warning?: string[]
}

// ── 搜索 ──────────────────────────────────────────────────────────────────────
export interface Facets {
  diet_labels: Record<string, number>
  price_level: Record<string, number>
  cuisine_type: Record<string, number>
}

export interface SearchParams {
  q?: string
  diet_labels?: DietLabel[]
  price_levels?: number[]
  lat?: number
  lng?: number
  radius_km?: number
  sort_mode?: string
  offset?: number
  limit?: number
}

export interface SearchResponse {
  total: number
  hits: Restaurant[]
  facets: Facets
  spell_suggestion?: string
  detected_diet_labels: DietLabel[]
  query_tokens: string[]
  sort_mode: string
  offset: number
  limit: number
  /** 后台已触发实时爬虫，约 5-10s 后重搜可见新数据 */
  crawl_triggered?: boolean
}
