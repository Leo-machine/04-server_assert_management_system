import { useEffect, useMemo, useState } from 'react'
import { Navigate } from 'react-router-dom'
import { api, getStoredUser } from '../api'
import ListToolbar from '../components/ListToolbar'
import { filterByQuery } from '../lib/fuzzy'
import { OPS_ROLES, hasRole, homePathFor } from '../lib/roles'
import { PART_CATEGORIES } from '../lib/categories'
import Pagination from '../components/Pagination'
import { usePagination } from '../hooks/usePagination'

const BAR_COLORS = ['#005a9c', '#0f766e', '#0369a1', '#1d4ed8', '#0a7ea4', '#0284c7']

export default function AllocatableSummary() {
  const me = getStoredUser()
  const canView = hasRole(me, OPS_ROLES)
  const [rows, setRows] = useState([])
  const [overview, setOverview] = useState(null)
  const [category, setCategory] = useState('内存')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [query, setQuery] = useState('')

  function load(cat) {
    setLoading(true)
    setError('')
    const q = cat ? `?category=${encodeURIComponent(cat)}` : ''
    api.get(`/inventory/allocatable-summary${q}`)
      .then(setRows)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    if (!canView) return undefined
    load(category)
  }, [category, canView])

  useEffect(() => {
    if (!canView) return undefined
    api.get('/inventory/allocatable-overview')
      .then(setOverview)
      .catch((e) => setError(e.message))
  }, [canView])

  const visible = useMemo(
    () =>
      filterByQuery(rows, query, (r) => [
        r.category,
        r.spec_label,
        r.capacity_gb,
        r.ddr_gen,
        r.allocatable_count,
        r.home_owner_unit,
      ]),
    [rows, query],
  )

  const chart = useMemo(() => {
    const sorted = [...visible].sort(
      (a, b) => (b.allocatable_count || 0) - (a.allocatable_count || 0),
    )
    const max = Math.max(1, ...sorted.map((r) => r.allocatable_count || 0))
    const total = sorted.reduce((s, r) => s + (r.allocatable_count || 0), 0)
    return { sorted, max, total, specs: sorted.length }
  }, [visible])
  const pagination = usePagination(visible)

  const panorama = useMemo(() => {
    const byCategory = overview?.by_category || Object.fromEntries(PART_CATEGORIES.map((cat) => [cat, 0]))
    return {
      total: overview?.total_assets || 0,
      inStock: overview?.in_stock || 0,
      occupied: overview?.occupied || 0,
      allocatable: overview?.allocatable || 0,
      reserved: overview?.reserved || 0,
      statuses: overview?.by_status || {},
      byCategory,
      maxCategory: Math.max(1, ...Object.values(byCategory)),
      allocRate: overview?.alloc_rate || 0,
    }
  }, [overview])

  if (!canView) {
    return <Navigate to={homePathFor(me)} replace />
  }

  return (
    <div className="as-page">
      <header className="as-header">
        <div>
          <span className="as-page-kicker">资源调配 · ALLOCATABLE CAPACITY</span>
          <h2>可调余量</h2>
          <p className="muted">
            在库 ∩ 本单位信息中心 ∩ 通用可调 · 内存按规格聚合，其余品类按型号聚合
          </p>
        </div>
      </header>

      {error && <div className="error">{error}</div>}

      <section className="as-panorama" aria-labelledby="as-panorama-title">
        <div className="as-section-title as-panorama-head">
          <div>
            <h3 id="as-panorama-title">库存全景图</h3>
            <span className="muted">全品类实时口径 · 从资产总量到可调能力</span>
          </div>
          <span className="as-panorama-time">当前数据</span>
        </div>

        <div className="as-flow" role="img" aria-label={`共 ${panorama.total} 件配件，在库 ${panorama.inStock} 件，通用可调 ${panorama.allocatable} 件`}>
          <div className="as-flow-node as-flow-total">
            <span className="as-flow-kicker">资产池</span>
            <strong>{panorama.total}</strong>
            <small>全部配件</small>
          </div>
          <span className="as-flow-arrow" aria-hidden="true">→</span>
          <div className="as-flow-branch">
            <div className="as-flow-node as-flow-stock">
              <span className="as-flow-kicker">库内资源</span>
              <strong>{panorama.inStock}</strong>
              <small>在库 · 可继续分配</small>
            </div>
            <div className="as-flow-node as-flow-occupied">
              <span className="as-flow-kicker">已离库 / 占用</span>
              <strong>{panorama.occupied}</strong>
              <small>在用、借出、损坏等</small>
            </div>
          </div>
          <span className="as-flow-arrow" aria-hidden="true">→</span>
          <div className="as-flow-branch as-flow-result">
            <div className="as-flow-node as-flow-alloc">
              <span className="as-flow-kicker">核心可调能力</span>
              <strong>{panorama.allocatable}</strong>
              <small>本单位产权 ∩ 通用可调</small>
              <em>{panorama.allocRate.toFixed(0)}% 在库可调率</em>
            </div>
            <div className="as-flow-node as-flow-reserved">
              <span className="as-flow-kicker">保留 / 其他</span>
              <strong>{panorama.reserved}</strong>
              <small>保留标记或非本单位产权</small>
            </div>
          </div>
        </div>

        <div className="as-category-map" aria-label="各品类可调数量">
          <div className="as-category-map-title">
            <strong>全品类可调能力</strong>
            <span className="muted">点击品类查看明细 · 条形长度表示可调数量</span>
          </div>
          <div className="as-category-grid">
            {PART_CATEGORIES.map((cat) => {
              const count = panorama.byCategory[cat] || 0
              const width = count ? Math.max(8, (count / panorama.maxCategory) * 100) : 0
              return (
                <button
                  type="button"
                  key={cat}
                  className={`as-category-item ${category === cat ? 'is-active' : ''}`}
                  onClick={() => setCategory(cat)}
                  aria-pressed={category === cat}
                >
                  <span className="as-category-label"><strong>{cat}</strong><em>{count} 件</em></span>
                  <span className="as-category-track"><i style={{ width: `${width}%` }} /></span>
                </button>
              )
            })}
          </div>
        </div>
      </section>

      <section className="as-kpi" aria-label="汇总">
        <div className="as-kpi-card">
          <div className="as-kpi-value">{chart.total}</div>
          <div className="as-kpi-label">可调总数</div>
        </div>
        <div className="as-kpi-card">
          <div className="as-kpi-value">{chart.specs}</div>
          <div className="as-kpi-label">规格组数</div>
        </div>
        <div className="as-kpi-card as-kpi-owner">
          <div className="as-kpi-value as-kpi-sm">
            {rows[0]?.home_owner_unit || '本单位信息中心'}
          </div>
          <div className="as-kpi-label">产权口径</div>
        </div>
      </section>

      <ListToolbar
        query={query}
        onQueryChange={setQuery}
        placeholder="搜索规格 / 容量 / 代际…"
        resultText={
          <>
            显示 <strong>{visible.length}</strong>
            {loading ? ' · 加载中…' : ''}
          </>
        }
      />

      <div className="as-body">
        <section className="as-chart-card" aria-label="可调余量柱状图">
          <div className="as-section-title">
            <h3>{category}规格分布</h3>
            <span className="muted">柱高 = 可调数量</span>
          </div>

          {!chart.sorted.length ? (
            <div className="as-empty">{rows.length ? '无匹配规格' : '暂无可调库存'}</div>
          ) : (
            <div className="as-bars" role="img" aria-label="可调余量柱状图">
              {chart.sorted.map((r, i) => {
                const count = r.allocatable_count || 0
                const pct = Math.max(count > 0 ? 8 : 0, (count / chart.max) * 100)
                const color = BAR_COLORS[i % BAR_COLORS.length]
                return (
                  <div
                    key={`${r.category}-${r.model_id ?? ''}-${r.capacity_gb ?? ''}-${r.ddr_gen ?? ''}`}
                    className="as-bar-col"
                    title={`${r.spec_label}：${count}`}
                  >
                    <div className="as-bar-value">{count}</div>
                    <div className="as-bar-track">
                      <div
                        className="as-bar-fill"
                        style={{ height: `${pct}%`, background: color }}
                      />
                    </div>
                    <div className="as-bar-label">
                      <span className="as-bar-spec">{r.spec_label || '未填'}</span>
                      {r.ddr_gen && <span className="as-bar-sub">{r.ddr_gen}</span>}
                    </div>
                  </div>
                )
              })}
            </div>
          )}
        </section>

        <section className="as-table-card">
          <div className="as-section-title">
            <h3>{category}明细</h3>
            <span className="muted">与图同源数据</span>
          </div>
          <div className="as-table-wrap">
            <table className="as-table">
              <thead>
                <tr>
                  <th className="as-col-cat">品类</th>
                  <th className="as-col-spec">规格</th>
                  <th className="as-col-num">容量GB</th>
                  <th className="as-col-gen">代际</th>
                  <th className="as-col-num">可调数量</th>
                  <th className="as-col-bar">占比</th>
                </tr>
              </thead>
              <tbody>
                {!visible.length && !loading && (
                  <tr>
                    <td colSpan={6} className="as-empty-cell">
                      {rows.length ? '无匹配规格' : '暂无可调库存'}
                    </td>
                  </tr>
                )}
                {pagination.pageItems.map((r, i) => {
                  const count = r.allocatable_count || 0
                  const share = chart.total ? (count / chart.total) * 100 : 0
                  const color = BAR_COLORS[i % BAR_COLORS.length]
                  return (
                    <tr key={`${r.category}-${r.model_id ?? ''}-${r.capacity_gb ?? ''}-${r.ddr_gen ?? ''}`}>
                      <td className="as-col-cat">{r.category}</td>
                      <td className="as-col-spec">
                        <strong>{r.spec_label}</strong>
                      </td>
                      <td className="as-col-num">{r.capacity_gb ?? '—'}</td>
                      <td className="as-col-gen">{r.ddr_gen ?? '—'}</td>
                      <td className="as-col-num">
                        <strong className="as-count">{count}</strong>
                      </td>
                      <td className="as-col-bar">
                        <div className="as-inline-bar">
                          <div className="as-inline-track">
                            <i style={{ width: `${share}%`, background: color }} />
                          </div>
                          <span>{share.toFixed(0)}%</span>
                        </div>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
          <Pagination pagination={pagination} />
        </section>
      </div>
    </div>
  )
}
