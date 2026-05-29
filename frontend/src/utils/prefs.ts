export interface SavedPrefs {
  nutritionLabels: string[]
  dietLabels: string[]       // DietLabel values (vegetarian, vegan, halal, kosher, keto, dairy-free, gluten-free)
  allergyRestrictions: string[]  // non-dietLabel values (peanut-free, seafood-free, soy-free, no_spicy)
}

const EMPTY: SavedPrefs = { nutritionLabels: [], dietLabels: [], allergyRestrictions: [] }
const key = (userId: number) => `macrobite_prefs_${userId}`

export function loadPrefs(userId: number): SavedPrefs {
  try {
    const s = localStorage.getItem(key(userId))
    return s ? { ...EMPTY, ...JSON.parse(s) } : EMPTY
  } catch {
    return EMPTY
  }
}

export function savePrefs(userId: number, prefs: SavedPrefs): void {
  localStorage.setItem(key(userId), JSON.stringify(prefs))
}

export function clearPrefs(userId: number): void {
  localStorage.removeItem(key(userId))
}
