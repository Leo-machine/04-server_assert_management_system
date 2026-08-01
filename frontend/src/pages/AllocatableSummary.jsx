import { useEffect, useMemo, useState } from 'react'
import { api } from '../api'
import ListToolbar from '../components/ListToolbar'
import { filterByQuery } from '../lib/fuzzy'

const BAR_COLORS = ['#005a9c', '#0f766e', '#0369a1', '#1d4ed8', '#0a7ea4', '#0284c7']

export default function AllocatableSummary() {
  const [rows, setRows] = useState([])
  const [category, setCategory] = useState('内存')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [query, setQuery] = useState('')

  function load(cat) {
    setLoading(true)
    setError('')
    const q = cat ? `?category=${encodeURIComponent(cat)}` : ''
    api
      .get(`/inventory/allocatable-summary${q}`)
      .then(setRows)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    load(category)
  }, [category])

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

  return (
    <div className="as-page">
      <header className="as-header">
        <div>
          <h2>可调余量</h2>
          <p className="muted">
            在库 ∩ 本单位信息中心 ∩ 通用可调 · 按规格跨型号聚合
          </p>
        </div>
        <div className="as-controls">
          <label className="as-field">
            <span>品类</span>
            <select value={category} onChange={(e) => setCategory(e.target.value)}>
              <option value="内存">内存</option>
            </select>
          </label>
          <button
            type="button"
            className="secondary"
            onClick={() => load(category)}
            disabled={loading}
          >
            {loading ? '刷新中…' : '刷新'}
          </button>
        </div>
      </header>

      {error && <div className="error">{error}</div>}

      <section className="as-kpi" aria-label="汇总">
        <div className="as-kpi-card">
          <div className="as-kpi-value">{chart.total}</div>
          <div className="as-kpi-label">可调总数</div>
        </div>
        <div className="as-kpi-card">
          <div className="as-kpi-value">{chart.specs}</div>
          <div className="as-kpi-label">规格组数</div>
        </div>
        <div className="as-kpi-card">
          <div className="as-kpi-value">{category}</div>
          <div className="as-kpi-label">当前品类</div>
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
            <h3>规格分布</h3>
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
                    key={`${r.category}-${r.capacity_gb}-${r.ddr_gen}`}
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
            <h3>明细</h3>
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
                {visible.map((r, i) => {
                  const count = r.allocatable_count || 0
                  const share = chart.total ? (count / chart.total) * 100 : 0
                  const color = BAR_COLORS[i % BAR_COLORS.length]
                  return (
                    <tr key={`${r.category}-${r.capacity_gb}-${r.ddr_gen}`}>
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
        </section>
      </div>
    </div>
  )
}
