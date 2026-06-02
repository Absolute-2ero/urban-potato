import { useEffect, useRef } from 'react'
import { useLocation } from 'react-router-dom'
import { useMacStore } from '@/stores/macStore'
import { useSearchStore } from '@/stores/searchStore'
import { useAuthStore } from '@/stores/authStore'
import { useDietStore } from '@/stores/dietStore'
import { loadGoals } from '@/utils/prefs'
import { MacMascot } from './MacMascot'
import type { DietLabel } from '@/types'

const BUBBLE_CSS = `
  @keyframes mac-bubble-in {
    from { opacity: 0; transform: translateY(6px) scale(0.96); }
    to   { opacity: 1; transform: translateY(0)  scale(1); }
  }
`

// Inject once into <head> — avoids React 18.3 <style> hoisting / removeChild crash
if (typeof document !== 'undefined' && !document.getElementById('mac-widget-css')) {
  const _s = document.createElement('style')
  _s.id = 'mac-widget-css'
  _s.textContent = BUBBLE_CSS
  document.head.appendChild(_s)
}

// Map diet labels → Mac message pool keys
const FILTER_POOL: Partial<Record<DietLabel | string, string>> = {
  'low-fat':      'filter_lowfat',
  'low-sugar':    'filter_lowsugar',
  'low-sodium':   'filter_lowsodium',
  'high-protein': 'filter_highprotein',
  'vegan':        'filter_vegan',
  'vegetarian':   'filter_vegetarian',
  'keto':         'filter_keto',
  'halal':        'filter_halal',
  'gluten-free':  'filter_allergy',
  'dairy-free':   'filter_allergy',
  'peanut-free':  'filter_allergy',
  'seafood-free': 'filter_allergy',
  'soy-free':     'filter_allergy',
  'no-spicy':     'filter_nospicy',
}

// Pages Mac should say something about
const ROUTE_POOL: Record<string, string> = {
  '/':        'route_home',
  '/search':  'route_search',
  '/diet':    'route_diet',
  '/saved':   'route_saved',
  '/profile': 'route_profile',
}

export function MacWidget() {
  const { emotion, message, closed, tryShow, tap, dismiss, close, reopen } = useMacStore()

  const { pathname } = useLocation()

  const total       = useSearchStore(s => s.total)
  const loading     = useSearchStore(s => s.loading)
  const dietLabels  = useSearchStore(s => s.dietLabels)
  const minRating   = useSearchStore(s => s.minRating)
  const sortMode    = useSearchStore(s => s.sortMode)
  const minCalories = useSearchStore(s => s.minCalories)
  const user        = useAuthStore(s => s.user)
  const logDay      = useDietStore(s => s.logDay)
  const currentDate = useDietStore(s => s.currentDate)

  // Refs for tracking previous values between renders
  const prevLoading   = useRef(false)
  const prevLabels    = useRef<DietLabel[]>([])
  const prevRating    = useRef<number | null>(null)
  const prevSortMode  = useRef('default')
  const prevMinCal    = useRef<number | null>(null)
  const prevEntries   = useRef(-1)   // -1 = uninitialized
  const prevCals      = useRef(0)
  const prevProtein   = useRef(0)
  const lastIdleAt    = useRef(0)
  const lastInteract  = useRef(Date.now())
  const questShown    = useRef(false)
  const dismissTimer  = useRef<ReturnType<typeof setTimeout> | null>(null)
  const idleTimer     = useRef<ReturnType<typeof setInterval> | null>(null)
  const motivTimer    = useRef<ReturnType<typeof setInterval> | null>(null)

  // ── Auto-dismiss bubble after 8 s ────────────────────────────────────────
  useEffect(() => {
    if (dismissTimer.current) clearTimeout(dismissTimer.current)
    if (message) dismissTimer.current = setTimeout(() => dismiss(), 8_000)
    return () => { if (dismissTimer.current) clearTimeout(dismissTimer.current) }
  }, [message])

  // ── Time-of-day greeting on first mount ──────────────────────────────────
  useEffect(() => {
    const h = new Date().getHours()
    const pool =
      h < 9  ? 'greet_morning' :
      h < 14 ? 'greet_noon'    :
      h < 19 ? 'greet_evening' :
               'greet_night'
    const t = setTimeout(() => tryShow(pool, true), 2_000)
    return () => clearTimeout(t)
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // ── Idle timer ────────────────────────────────────────────────────────────
  useEffect(() => {
    const resetIdle = () => { lastInteract.current = Date.now() }
    window.addEventListener('mousemove',  resetIdle)
    window.addEventListener('keydown',    resetIdle)
    window.addEventListener('touchstart', resetIdle, { passive: true })

    idleTimer.current = setInterval(() => {
      const idleMs = Date.now() - lastInteract.current
      const now = Date.now()
      if (now - lastIdleAt.current < 120_000) return  // cooldown between idle messages
      if (idleMs > 300_000) {
        tryShow('idle_5min')
        lastIdleAt.current = now
      } else if (idleMs > 150_000) {
        tryShow('idle_2min')
        lastIdleAt.current = now
      }
    }, 30_000)

    return () => {
      window.removeEventListener('mousemove',  resetIdle)
      window.removeEventListener('keydown',    resetIdle)
      window.removeEventListener('touchstart', resetIdle)
      if (idleTimer.current) clearInterval(idleTimer.current)
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // ── Periodic motivation message every ~4.5 min ───────────────────────────
  useEffect(() => {
    motivTimer.current = setInterval(() => tryShow('motivation'), 270_000)
    return () => { if (motivTimer.current) clearInterval(motivTimer.current) }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // ── Sort mode changed ─────────────────────────────────────────────────────
  useEffect(() => {
    if (sortMode !== prevSortMode.current && prevSortMode.current !== '') {
      if      (sortMode === 'distance_first') tryShow('filter_sort_distance')
      else if (sortMode === 'price_asc')      tryShow('filter_sort_price')
      else if (sortMode === 'rating_first')   tryShow('filter_rating_high')
    }
    prevSortMode.current = sortMode
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sortMode])

  // ── Calorie range filter set ──────────────────────────────────────────────
  useEffect(() => {
    if (minCalories !== null && prevMinCal.current === null) {
      tryShow('filter_calorie')
    }
    prevMinCal.current = minCalories
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [minCalories])

  // ── Route change messages ─────────────────────────────────────────────────
  useEffect(() => {
    const match = Object.entries(ROUTE_POOL).find(([p]) =>
      p === '/' ? pathname === '/' : pathname === p || pathname.startsWith(p + '/')
    )
    if (!match) return
    const t = setTimeout(() => tryShow(match[1]), 1_200)
    return () => clearTimeout(t)
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pathname])

  // ── Quest suggestion on home page (once per session) ─────────────────────
  useEffect(() => {
    if (pathname !== '/' || questShown.current) return
    const t = setTimeout(() => {
      tryShow('quest')
      questShown.current = true
    }, 35_000)
    return () => clearTimeout(t)
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pathname])

  // ── Search results returned ───────────────────────────────────────────────
  useEffect(() => {
    if (prevLoading.current && !loading && pathname.startsWith('/search')) {
      if      (total === 0)  tryShow('search_none')
      else if (total <= 3)   tryShow('search_few')
      else                   tryShow('search_many')
    }
    prevLoading.current = loading
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [loading])

  // ── Diet label filter added ───────────────────────────────────────────────
  useEffect(() => {
    const added = dietLabels.filter(l => !prevLabels.current.includes(l))
    if (added.length > 0) {
      const key = FILTER_POOL[added[0]] ?? 'filter_generic'
      tryShow(key)
    }
    prevLabels.current = [...dietLabels]
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [dietLabels.join(',')])

  // ── Rating filter set high ────────────────────────────────────────────────
  useEffect(() => {
    if (minRating !== null && prevRating.current === null) {
      tryShow(minRating >= 4.3 ? 'filter_rating_high' : 'filter_generic')
    }
    prevRating.current = minRating
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [minRating])

  // ── Reset diet baseline when date changes ─────────────────────────────────
  useEffect(() => {
    prevEntries.current = -1
    prevCals.current    = 0
    prevProtein.current = 0
  }, [currentDate])

  // ── Diet log entry added / goal crossed ───────────────────────────────────
  useEffect(() => {
    if (!logDay || !user) return
    const today = new Date().toISOString().slice(0, 10)
    if (currentDate !== today) return

    const count   = logDay.entries.length
    const totals  = logDay.totals
    const DRI     = loadGoals(user.id)

    // First load — just store baseline
    if (prevEntries.current === -1) {
      prevEntries.current = count
      prevCals.current    = totals.calories
      prevProtein.current = totals.protein_g
      return
    }

    // A new entry was added
    if (count === prevEntries.current + 1) {
      const newest = logDay.entries[count - 1]
      const firstEver = !sessionStorage.getItem('mac_first_log_ever')
      if (firstEver) {
        tryShow('diet_first_log_ever', true)
        sessionStorage.setItem('mac_first_log_ever', '1')
      } else if (prevEntries.current === 0) {
        tryShow('diet_first_log_today')
      } else if (newest && newest.fat_g > 25) {
        tryShow('diet_highfat')
      } else if (newest && newest.calories > 0 && newest.calories < 400) {
        tryShow('diet_lowcal')
      }
    }

    // Calorie goal milestones
    const calPct     = totals.calories / DRI.calories
    const prevCalPct = prevCals.current / DRI.calories
    if      (calPct >= 0.92 && calPct <= 1.08 && prevCalPct < 0.92)  tryShow('diet_goal_hit', true)
    else if (calPct > 1.18  && prevCalPct <= 1.18)                    tryShow('diet_over')

    // Protein goal
    if (totals.protein_g >= DRI.protein_g && prevProtein.current < DRI.protein_g) {
      tryShow('diet_protein_goal', true)
    }

    prevEntries.current = count
    prevCals.current    = totals.calories
    prevProtein.current = totals.protein_g
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [logDay])

  // ── Render ────────────────────────────────────────────────────────────────

  if (closed) {
    return (
      <button
        onClick={reopen}
        title="Open Mac"
        style={{
          position: 'fixed', bottom: 20, right: 20, zIndex: 9999,
          width: 58, height: 58, borderRadius: '50%',
          background: '#2D9B5A', border: '2.5px solid rgba(255,255,255,0.45)',
          cursor: 'pointer', padding: 0, overflow: 'hidden',
          boxShadow: '0 4px 18px rgba(45,155,90,0.38)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          transition: 'transform 0.15s, box-shadow 0.15s',
        }}
        onMouseEnter={e => {
          e.currentTarget.style.transform   = 'scale(1.1)'
          e.currentTarget.style.boxShadow   = '0 6px 22px rgba(45,155,90,0.5)'
        }}
        onMouseLeave={e => {
          e.currentTarget.style.transform   = 'scale(1)'
          e.currentTarget.style.boxShadow   = '0 4px 18px rgba(45,155,90,0.38)'
        }}
      >
        <MacMascot emotion="idle" size={50} />
      </button>
    )
  }

  return (
    <>
      <div style={{
        position: 'fixed', bottom: 20, right: 20, zIndex: 9999,
        display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 8,
        pointerEvents: 'none',
      }}>

        {/* ── Speech bubble ──────────────────────────────────────────── */}
        {message && (
          <div
            key={message}
            style={{
              background: '#fff',
              border: '1.5px solid #E8E0D5',
              borderRadius: 14,
              padding: '10px 36px 10px 14px',
              maxWidth: 230,
              boxShadow: '0 4px 20px rgba(30,42,42,0.12)',
              position: 'relative',
              animation: 'mac-bubble-in 0.22s ease',
              pointerEvents: 'auto',
            }}
          >
            {/* Dismiss × */}
            <button
              onClick={dismiss}
              style={{
                position: 'absolute', top: 7, right: 9,
                width: 20, height: 20, borderRadius: '50%',
                background: '#F0EBE4', border: 'none',
                cursor: 'pointer', fontSize: 12, color: '#6B7A7A',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                padding: 0, lineHeight: 1,
              }}
            >×</button>

            <p style={{
              margin: 0, fontSize: 13, lineHeight: 1.55, color: '#1E2A2A',
              fontFamily: "'PingFang SC','Hiragino Sans GB','Microsoft YaHei',sans-serif",
            }}>
              {message}
            </p>

            {/* Tail pointing down toward Mac */}
            <div style={{
              position: 'absolute', bottom: -7, right: 34,
              width: 12, height: 12,
              background: '#fff',
              borderRight: '1.5px solid #E8E0D5',
              borderBottom: '1.5px solid #E8E0D5',
              transform: 'rotate(45deg)',
            }} />
          </div>
        )}

        {/* ── Mac character + hide button ────────────────────────────── */}
        <div style={{
          display: 'flex', alignItems: 'flex-end', gap: 4,
          pointerEvents: 'auto',
        }}>
          {/* Hide-Mac × (top-left of character) */}
          <button
            onClick={close}
            title="Hide Mac"
            style={{
              width: 22, height: 22, borderRadius: '50%',
              background: '#E8E0D5', border: 'none',
              cursor: 'pointer', fontSize: 11, color: '#6B7A7A',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              alignSelf: 'flex-start', marginTop: 6, flexShrink: 0,
              transition: 'background 0.15s, color 0.15s',
              padding: 0, lineHeight: 1,
            }}
            onMouseEnter={e => {
              e.currentTarget.style.background = '#E85454'
              e.currentTarget.style.color      = '#fff'
            }}
            onMouseLeave={e => {
              e.currentTarget.style.background = '#E8E0D5'
              e.currentTarget.style.color      = '#6B7A7A'
            }}
          >×</button>

          <div
            onClick={tap}
            title="Talk to Mac! 🥦"
            style={{ cursor: 'pointer', userSelect: 'none' }}
          >
            <MacMascot emotion={emotion} size={80} />
          </div>
        </div>
      </div>
    </>
  )
}
