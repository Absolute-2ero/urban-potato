import { useEffect, useRef, useState } from 'react'
import { Alert, Button, Col, Empty, Pagination, Row, Spin, Typography } from 'antd'
import { ReloadOutlined, RocketOutlined } from '@ant-design/icons'
import { SearchBar } from '@/components/search/SearchBar'
import { FilterPanel } from '@/components/search/FilterPanel'
import { ResultCard } from '@/components/restaurant/ResultCard'
import { useSearchSync } from '@/hooks/useSearch'
import { useSearchStore } from '@/stores/searchStore'
import type { DietLabel } from '@/types'

const { Text } = Typography

const CRAWL_REFRESH_DELAY = 10_000   // 10s 后自动重搜

export default function SearchPage() {
  const { q, dietLabels, priceLevels, sortMode, offset, limit, push } = useSearchSync()
  const {
    results, total, facets, loading, error,
    spellSuggestion, detectedDietLabels, crawlTriggered,
    doSearch,
  } = useSearchStore()

  // 爬虫触发后倒计时自动重搜
  const [countdown, setCountdown] = useState<number | null>(null)
  const countdownRef = useRef<ReturnType<typeof setInterval> | null>(null)

  useEffect(() => {
    if (crawlTriggered) {
      setCountdown(Math.round(CRAWL_REFRESH_DELAY / 1000))
      countdownRef.current = setInterval(() => {
        setCountdown((prev) => {
          if (prev === null || prev <= 1) {
            clearInterval(countdownRef.current!)
            doSearch()   // 自动重搜
            return null
          }
          return prev - 1
        })
      }, 1000)
    }
    return () => {
      if (countdownRef.current) clearInterval(countdownRef.current)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [crawlTriggered])

  const handleDietClick = (label: DietLabel) => {
    const next = dietLabels.includes(label)
      ? dietLabels.filter((l) => l !== label)
      : [...dietLabels, label]
    push({ diet: next, offset: 0 })
  }

  return (
    <div style={{ maxWidth: 1200, margin: '0 auto', padding: '24px 16px' }}>
      {/* 搜索框 */}
      <div style={{ marginBottom: 24 }}>
        <SearchBar
          value={q}
          onChange={(val) => push({ q: val })}
          onSearch={(val) => push({ q: val, offset: 0 })}
        />
      </div>

      {/* 拼写建议 */}
      {spellSuggestion && (
        <Alert
          type="info"
          showIcon
          message={
            <span>
              您是否要搜索：
              <a onClick={() => push({ q: spellSuggestion, offset: 0 })}>
                <strong>{spellSuggestion}</strong>
              </a>
              ？
            </span>
          }
          style={{ marginBottom: 16 }}
          closable
        />
      )}

      {/* 检测到的饮食标签提示 */}
      {detectedDietLabels.length > 0 && (
        <Alert
          type="success"
          showIcon
          message={`已识别饮食偏好：${detectedDietLabels.join('、')}`}
          style={{ marginBottom: 16 }}
          closable
        />
      )}

      {/* 🚀 实时爬虫触发提示 */}
      {crawlTriggered && (
        <Alert
          type="warning"
          showIcon
          icon={<RocketOutlined />}
          message={
            <span>
              结果较少，已自动从网络补充数据
              {countdown !== null
                ? `，${countdown}s 后自动刷新…`
                : ''}
            </span>
          }
          action={
            <Button
              size="small"
              icon={<ReloadOutlined />}
              onClick={() => doSearch()}
            >
              立即刷新
            </Button>
          }
          style={{ marginBottom: 16 }}
        />
      )}

      <Row gutter={24}>
        {/* 左侧筛选 */}
        <Col xs={0} sm={0} md={6} lg={5}>
          <FilterPanel
            dietLabels={dietLabels}
            priceLevels={priceLevels}
            sortMode={sortMode}
            facets={facets ?? undefined}
            onDietChange={(labels) => push({ diet: labels, offset: 0 })}
            onPriceChange={(levels) => push({ price: levels, offset: 0 })}
            onSortChange={(mode) => push({ sort: mode, offset: 0 })}
          />
        </Col>

        {/* 右侧结果 */}
        <Col xs={24} sm={24} md={18} lg={19}>
          {/* 结果统计 */}
          {!loading && !error && (
            <Text type="secondary" style={{ marginBottom: 12, display: 'block' }}>
              找到 <strong>{total}</strong> 家餐厅
              {crawlTriggered && (
                <Text type="warning" style={{ marginLeft: 8, fontSize: 12 }}>
                  （数据补充中…）
                </Text>
              )}
            </Text>
          )}

          {error && (
            <Alert type="error" message={`搜索失败：${error}`} style={{ marginBottom: 16 }} />
          )}

          <Spin spinning={loading}>
            {results.length === 0 && !loading ? (
              <Empty
                description={
                  crawlTriggered
                    ? '正在从网络抓取数据，请稍后刷新…'
                    : '没有找到匹配的餐厅，试试调整搜索词或筛选条件'
                }
              />
            ) : (
              results.map((r) => (
                <ResultCard
                  key={r.restaurant_id}
                  restaurant={r}
                  onDietClick={handleDietClick}
                />
              ))
            )}
          </Spin>

          {/* 分页 */}
          {total > limit && (
            <div style={{ textAlign: 'center', marginTop: 24 }}>
              <Pagination
                current={Math.floor(offset / limit) + 1}
                pageSize={limit}
                total={total}
                onChange={(page) => push({ offset: (page - 1) * limit })}
                showSizeChanger={false}
              />
            </div>
          )}
        </Col>
      </Row>
    </div>
  )
}
