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
    setQ, setDietLabels, setPriceLevels, setSortMode, setOffset, setLocalFilters,
    doSearch,
  } = useSearchStore()

  // URL → Store + 立即搜索（合并为一个 effect 避免竞争条件）
  // 问题：若分两个 effect，setDietLabels 是异步的，doSearch 调用时 store 里
  // 还是旧值，导致导航过来时标签没有生效。
  // 解决：解析完 URL 后直接把值作为 override 传给 doSearch。
  useEffect(() => {
    const urlQ        = urlParams.get('q') || ''
    const urlDiet     = (urlParams.getAll('diet') as DietLabel[]) || []
    const urlPrice    = urlParams.getAll('price').map(Number)
    const urlSort     = urlParams.get('sort') || 'default'
    const urlOffset   = parseInt(urlParams.get('offset') || '0', 10)
    const urlRadiusKm = urlParams.get('radius_km') ? Number(urlParams.get('radius_km')) : null
    const urlSemantic = urlParams.get('semantic') === 'true'

    setQ(urlQ)
    setDietLabels(urlDiet)
    setPriceLevels(urlPrice)
    setSortMode(urlSort)
    setOffset(urlOffset)
    if (urlRadiusKm != null) setLocalFilters({ radiusKm: urlRadiusKm })

    doSearch({
      q:            urlQ,
      diet_labels:  urlDiet.length ? urlDiet : undefined,
      price_levels: urlPrice.length ? urlPrice : undefined,
      sort_mode:    urlSort,
      offset:       urlOffset,
      ...(urlRadiusKm != null ? { radius_km: urlRadiusKm } : {}),
      ...(urlSemantic ? { semantic: true } : {}),
    })
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
