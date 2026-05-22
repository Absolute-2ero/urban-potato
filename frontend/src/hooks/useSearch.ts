import { useCallback, useEffect } from 'react'
import { useSearchParams } from 'react-router-dom'
import { useSearchStore } from '@/stores/searchStore'
import type { DietLabel } from '@/types'

/**
 * URL 参数 ↔ SearchStore 双向同步 hook。
 * 用在 SearchPage：URL 是搜索状态的单一真值来源。
 */
export function useSearchSync() {
  const [urlParams, setUrlParams] = useSearchParams()
  const {
    q, dietLabels, priceLevels, sortMode, offset, limit,
    setQ, setDietLabels, setPriceLevels, setSortMode, setOffset,
    doSearch,
  } = useSearchStore()

  // URL → Store（初次 + 后退/前进）
  useEffect(() => {
    const urlQ = urlParams.get('q') || ''
    const urlDiet = (urlParams.getAll('diet') as DietLabel[]) || []
    const urlPrice = urlParams.getAll('price').map(Number)
    const urlSort = urlParams.get('sort') || 'default'
    const urlOffset = parseInt(urlParams.get('offset') || '0', 10)

    setQ(urlQ)
    setDietLabels(urlDiet)
    setPriceLevels(urlPrice)
    setSortMode(urlSort)
    setOffset(urlOffset)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [urlParams.toString()])

  // Store 状态变化后触发搜索（由 URL 变化驱动，避免死循环）
  useEffect(() => {
    doSearch()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [urlParams.toString()])

  // 更新 URL（保持 URL 与 store 一致）
  const push = useCallback(
    (
      patch: Partial<{
        q: string
        diet: DietLabel[]
        price: number[]
        sort: string
        offset: number
      }>
    ) => {
      const next = new URLSearchParams(urlParams)
      if ('q' in patch) {
        patch.q ? next.set('q', patch.q) : next.delete('q')
      }
      if ('diet' in patch) {
        next.delete('diet')
        patch.diet?.forEach((d) => next.append('diet', d))
      }
      if ('price' in patch) {
        next.delete('price')
        patch.price?.forEach((p) => next.append('price', String(p)))
      }
      if ('sort' in patch) {
        patch.sort && patch.sort !== 'default'
          ? next.set('sort', patch.sort)
          : next.delete('sort')
      }
      if ('offset' in patch) {
        patch.offset ? next.set('offset', String(patch.offset)) : next.delete('offset')
      }
      setUrlParams(next, { replace: false })
    },
    [urlParams, setUrlParams]
  )

  return {
    q, dietLabels, priceLevels, sortMode, offset, limit,
    push,
  }
}
