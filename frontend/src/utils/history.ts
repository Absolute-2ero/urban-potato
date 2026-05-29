export interface SearchRecord {
  id: string
  query: string
  dietLabels: string[]
  timestamp: number
  resultCount: number
}

export interface RestaurantViewRecord {
  id: string
  restaurantId: string
  restaurantName: string
  dishes: string[]
  timestamp: number
}

const MAX_SEARCHES = 50
const MAX_VIEWS = 100

const sk = (uid?: number) => `macrobite_sh_${uid ?? 'anon'}`
const vk = (uid?: number) => `macrobite_vh_${uid ?? 'anon'}`

function readJSON<T>(key: string): T[] {
  try { return JSON.parse(localStorage.getItem(key) ?? '[]') } catch { return [] }
}

function writeJSON<T>(key: string, data: T[]): void {
  localStorage.setItem(key, JSON.stringify(data))
}

// ── Search history ─────────────────────────────────────────────────────────

export function loadSearchHistory(uid?: number): SearchRecord[] {
  return readJSON<SearchRecord>(sk(uid))
}

export function addSearchRecord(entry: SearchRecord, uid?: number): void {
  const records = readJSON<SearchRecord>(sk(uid))
  // deduplicate: if last entry is same query+labels, just update timestamp & count
  const last = records[0]
  if (last && last.query === entry.query &&
      JSON.stringify(last.dietLabels) === JSON.stringify(entry.dietLabels)) {
    records[0] = { ...last, timestamp: entry.timestamp, resultCount: entry.resultCount }
    writeJSON(sk(uid), records)
    return
  }
  writeJSON(sk(uid), [entry, ...records].slice(0, MAX_SEARCHES))
}

export function removeSearchRecord(id: string, uid?: number): void {
  writeJSON(sk(uid), readJSON<SearchRecord>(sk(uid)).filter((r) => r.id !== id))
}

export function clearSearchHistory(uid?: number): void {
  localStorage.removeItem(sk(uid))
}

// ── Restaurant view history ────────────────────────────────────────────────

export function loadViewHistory(uid?: number): RestaurantViewRecord[] {
  return readJSON<RestaurantViewRecord>(vk(uid))
}

export function addRestaurantView(entry: RestaurantViewRecord, uid?: number): void {
  const records = readJSON<RestaurantViewRecord>(vk(uid))
  // deduplicate: if same restaurant was viewed recently, move it to top with updated time
  const filtered = records.filter((r) => r.restaurantId !== entry.restaurantId)
  writeJSON(vk(uid), [entry, ...filtered].slice(0, MAX_VIEWS))
}

export function removeViewRecord(id: string, uid?: number): void {
  writeJSON(vk(uid), readJSON<RestaurantViewRecord>(vk(uid)).filter((r) => r.id !== id))
}

export function clearViewHistory(uid?: number): void {
  localStorage.removeItem(vk(uid))
}

// ── Relative time helper ───────────────────────────────────────────────────

export function relativeTime(ts: number): string {
  const diff = Date.now() - ts
  const mins = Math.floor(diff / 60_000)
  const hours = Math.floor(diff / 3_600_000)
  const days = Math.floor(diff / 86_400_000)
  if (mins < 1) return 'just now'
  if (mins < 60) return `${mins}m ago`
  if (hours < 24) return `${hours}h ago`
  if (days < 7) return `${days}d ago`
  return new Date(ts).toLocaleDateString()
}
