export interface SavedPrefs {
  nutritionLabels: string[]
  dietLabels: string[]
  allergyRestrictions: string[]
}

export interface DailyGoals {
  calories: number
  protein_g: number
  fat_g: number
  carb_g: number
}

export const DEFAULT_GOALS: DailyGoals = {
  calories: 2000,
  protein_g: 60,
  fat_g: 65,
  carb_g: 300,
}

const EMPTY: SavedPrefs = { nutritionLabels: [], dietLabels: [], allergyRestrictions: [] }
const prefsKey = (userId: string | number) => `macrobite_prefs_${userId}`
const goalsKey = (userId: string | number) => `macrobite_goals_${userId}`

export function loadPrefs(userId: string | number): SavedPrefs {
  try {
    const s = localStorage.getItem(prefsKey(userId))
    return s ? { ...EMPTY, ...JSON.parse(s) } : EMPTY
  } catch {
    return EMPTY
  }
}

export function savePrefs(userId: string | number, prefs: SavedPrefs): void {
  localStorage.setItem(prefsKey(userId), JSON.stringify(prefs))
}

export function clearPrefs(userId: string | number): void {
  localStorage.removeItem(prefsKey(userId))
}

export function loadGoals(userId: string | number): DailyGoals {
  try {
    const s = localStorage.getItem(goalsKey(userId))
    return s ? { ...DEFAULT_GOALS, ...JSON.parse(s) } : DEFAULT_GOALS
  } catch {
    return DEFAULT_GOALS
  }
}

export function saveGoals(userId: string | number, goals: DailyGoals): void {
  localStorage.setItem(goalsKey(userId), JSON.stringify(goals))
}
