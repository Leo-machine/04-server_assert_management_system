import { useEffect, useMemo, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { api } from '../api'
import HeaderFilter from '../components/HeaderFilter'
import ListToolbar from '../components/ListToolbar'
import { useSelection } from '../hooks/useSelection'
import { filterByQuery } from '../lib/fuzzy'

const CATEGORY_ORDER = [
  '内存',
  '机械硬盘',
  '固态硬盘',
  'RAID卡',
  '光模块',
  '网卡',
  'HBA卡',
  '算力卡',
]

const CATEGORY_META = {
  内存: { color: '#005a9c' },
  机械硬盘: { color: '#0a7ea4' },
  固态硬盘: { color: '#0891b2' },
  RAID卡: { color: '#1d4ed8' },
  光模块: { color: '#0284c7' },
  网卡: { color: '#0369a1' },
  HBA卡: { color: '#1e3a8a' },
  算力卡: { color: '#b91c1c' },
}

const STATUS_META = {
  在库: { color: '#0f766e' },
  在用: { color: '#0369a1' },
  借出: { color: '#c2410c' },
  已调拨: { color: '#7c3aed' },
  损坏: { color: '#b91c1c' },
  报废: { color: '#64748b' },
}

const ALLOC_OPTIONS = ['通用可调', '保留']
const LOC_KIND_OPTIONS = ['库位', '服务器', '外单位', '无']

function locLabel(part, servers, locs, orgs) {
  if (!part.current_loc_kind) return '-'
  if (part.current_loc_kind === '库位') {
    const loc = locs.find((l) => l.id === part.current_loc_id)
    return loc ? `${loc.warehouse}/${loc.slot}` : `库位#${part.current_loc_id}`
  }
  if (part.current_loc_kind === '服务器') {
    const s = servers.find((x) => x.id === part.current_loc_id)
    return s ? `${s.asset_no}（${s.run_status}）` : `服务器#${part.current_loc_id}`
  }
  if (part.current_loc_kind === '外单位') {
    const o = orgs.find((x) => x.id === part.current_loc_id)
    return o ? o.org_name : `外单位#${part.current_loc_id}`
  }
  return part.current_loc_kind
}

function statusBadgeClass(status, overdue) {
  if (overdue) return 'pl-badge pl-badge-danger'
  if (status === '在库') return 'pl-badge pl-badge-ok'
  if (status === '在用') return 'pl-badge pl-badge-info'
  if (status === '借出') return 'pl-badge pl-badge-warn'
  if (status === '已调拨') return 'pl-badge pl-badge-xfer'
  if (status === '损坏') return 'pl-badge pl-badge-danger'
  return 'pl-badge'
}

export default function PartsList() {
  const nav = useNavigate()
  const [params, setParams] = useSearchParams()
  const filterCat = params.get('category') || ''
  const filterStatus = params.get('status') || ''
  const filterAlloc = params.get('alloc') || ''
  const filterLocKind = params.get('loc') || ''

  const [parts, setParts] = useState([])
  const [servers, setServers] = useState([])
  const [locs, setLocs] = useState([])
  const [orgs, setOrgs] = useState([])
  const [error, setError] = useState('')
  const [ok, setOk] = useState('')
  const [busyId, setBusyId] = useState(null)
  const [batchBusy, setBatchBusy] = useState(false)
  const [query, setQuery] = useState('')
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(10)
  const [openFilter, setOpenFilter] = useState('') // status | alloc | loc | ''

  function reload() {
    return Promise.all([
      api.get('/parts'),
      api.get('/servers'),
      api.get('/storage-locations'),
      api.get('/external-orgs'),
    ]).then(([p, s, l, o]) => {
      setParts(p)
      setServers(s)
      setLocs(l)
      setOrgs(o)
    })
  }

  useEffect(() => {
    reload().catch((e) => setError(e.message))
  }, [])

  const categoryStats = useMemo(() => {
    const map = {}
    for (const cat of CATEGORY_ORDER) {
      map[cat] = { total: 0, byStatus: {} }
    }
    for (const p of parts) {
      const cat = p.model?.category || '未分类'
      if (!map[cat]) map[cat] = { total: 0, byStatus: {} }
      map[cat].total += 1
      const st = p.current_status || '未知'
      map[cat].byStatus[st] = (map[cat].byStatus[st] || 0) + 1
    }
    return map
  }, [parts])

  // 表头筛选项计数：受其它已选条件约束（不含本列自身），避免「在库 8」下仍显示可调配 808
  const scopedParts = useMemo(() => {
    const base = parts.filter((p) => {
      if (filterCat && (p.model?.category || '') !== filterCat) return false
      return true
    })
    return filterByQuery(base, query, (p) => [
      p.fixed_asset_no,
      p.serial_no,
      p.owner_unit,
      p.allocatable_flag,
      p.current_status,
      p.model?.category,
      p.model?.model_name,
      p.model?.brand,
      p.model?.pn,
      p.supplier,
      p.project,
      locLabel(p, servers, locs, orgs),
    ])
  }, [parts, filterCat, query, servers, locs, orgs])

  function applyOtherFilters(list, { skip } = {}) {
    return list.filter((p) => {
      if (skip !== 'status' && filterStatus && p.current_status !== filterStatus) return false
      if (skip !== 'alloc' && filterAlloc && (p.allocatable_flag || '') !== filterAlloc) return false
      if (skip !== 'loc' && filterLocKind) {
        const kind = p.current_loc_kind || '无'
        if (kind !== filterLocKind) return false
      }
      return true
    })
  }

  const statusTotals = useMemo(() => {
    const t = {}
    for (const p of applyOtherFilters(scopedParts, { skip: 'status' })) {
      const st = p.current_status || '未知'
      t[st] = (t[st] || 0) + 1
    }
    return t
  }, [scopedParts, filterAlloc, filterLocKind])

  const allocTotals = useMemo(() => {
    const t = {}
    for (const p of applyOtherFilters(scopedParts, { skip: 'alloc' })) {
      const a = p.allocatable_flag || '未知'
      t[a] = (t[a] || 0) + 1
    }
    return t
  }, [scopedParts, filterStatus, filterLocKind])

  const locKindTotals = useMemo(() => {
    const t = {}
    for (const p of applyOtherFilters(scopedParts, { skip: 'loc' })) {
      const k = p.current_loc_kind || '无'
      t[k] = (t[k] || 0) + 1
    }
    return t
  }, [scopedParts, filterStatus, filterAlloc])

  const visible = useMemo(
    () => applyOtherFilters(scopedParts),
    [scopedParts, filterStatus, filterAlloc, filterLocKind],
  )

  const visibleIds = useMemo(() => visible.map((p) => p.id), [visible])
  const sel = useSelection(visibleIds)

  const totalPages = Math.max(1, Math.ceil(visible.length / pageSize))
  const safePage = Math.min(page, totalPages)
  const paged = useMemo(
    () => visible.slice((safePage - 1) * pageSize, safePage * pageSize),
    [visible, safePage, pageSize],
  )
  useEffect(() => {
    setPage(1)
  }, [filterCat, filterStatus, filterAlloc, filterLocKind, query, pageSize])

  const populatedCats = useMemo(
    () => CATEGORY_ORDER.filter((c) => (categoryStats[c]?.total || 0) > 0),
    [categoryStats],
  )

  const hasFilters = !!(filterCat || filterStatus || filterAlloc || filterLocKind || query)

  function setFilter(patch = {}) {
    const next = {}
    const cat = patch.category === undefined ? filterCat : patch.category
    const st = patch.status === undefined ? filterStatus : patch.status
    const alloc = patch.alloc === undefined ? filterAlloc : patch.alloc
    const loc = patch.loc === undefined ? filterLocKind : patch.loc
    if (cat) next.category = cat
    if (st) next.status = st
    if (alloc) next.alloc = alloc
    if (loc) next.loc = loc
    setParams(next)
    sel.clear()
  }

  async function toggleAlloc(part, e) {
    e?.stopPropagation?.()
    if (part.current_status !== '在库') return
    const next = part.allocatable_flag === '通用可调' ? '保留' : '通用可调'
    setBusyId(part.id)
    setError('')
    setOk('')
    try {
      await api.patch(`/parts/${part.id}`, { allocatable_flag: next })
      await reload()
    } catch (err) {
      setError(err.message)
    } finally {
      setBusyId(null)
    }
  }

  async function batchSetAlloc(flag) {
    const targets = visible.filter(
      (p) => sel.isSelected(p.id) && p.current_status === '在库',
    )
    if (!targets.length) {
      setError('所选配件中没有「在库」项，无法批量改可调配')
      return
    }
    if (!window.confirm(`将 ${targets.length} 件在库配件设为「${flag}」？`)) return
    setBatchBusy(true)
    setError('')
    setOk('')
    let okN = 0
    const errors = []
    for (const p of targets) {
      try {
        await api.patch(`/parts/${p.id}`, { allocatable_flag: flag })
        okN += 1
      } catch (e) {
        errors.push(`${p.fixed_asset_no}: ${e.message}`)
      }
    }
    await reload()
    sel.clear()
    setBatchBusy(false)
    if (errors.length) setError(errors.slice(0, 3).join('；'))
    if (okN > 0) setOk(`已更新 ${okN} 件为「${flag}」`)
  }

  function openDetail(id) {
    nav(`/parts/${id}`)
  }

  return (
    <div className="pl-page">
      <header className="pl-header">
        <div>
          <h2>配件列表</h2>
          <p className="muted">
            共 {parts.length} 件 · 点击资产编号查看详情 · 表头可筛选状态 / 可调配 / 位置
          </p>
        </div>
        {hasFilters && (
          <button
            type="button"
            className="secondary pl-clear"
            onClick={() => {
              setParams({})
              setQuery('')
              sel.clear()
            }}
          >
            清除筛选
          </button>
        )}
      </header>

      {error && <div className="error">{error}</div>}
      {ok && <div className="ok-msg">{ok}</div>}

      <section className="pl-overview" aria-label="分类概览">
        {populatedCats.map((cat) => {
          const meta = CATEGORY_META[cat]
          const stat = categoryStats[cat]
          const active = filterCat === cat
          const statuses = Object.keys(STATUS_META).filter((s) => stat.byStatus[s])
          return (
            <button
              key={cat}
              type="button"
              className={`pl-cat ${active ? 'is-active' : ''}`}
              style={{ '--cat': meta.color }}
              onClick={() => setFilter({ category: active ? '' : cat })}
            >
              <div className="pl-cat-top">
                <span className="pl-cat-name">{cat}</span>
                <span className="pl-cat-n">{stat.total}</span>
              </div>
              <div className="pl-cat-bar" aria-hidden>
                {statuses.map((s) => (
                  <span
                    key={s}
                    style={{
                      flex: stat.byStatus[s],
                      background: STATUS_META[s].color,
                    }}
                    title={`${s} ${stat.byStatus[s]}`}
                  />
                ))}
              </div>
              <div className="pl-cat-foot">
                {statuses.map((s) => (
                  <span key={s}>
                    {s} {stat.byStatus[s]}
                  </span>
                ))}
              </div>
            </button>
          )
        })}
        {!populatedCats.length && <p className="muted">暂无配件数据</p>}
      </section>

      <ListToolbar
        query={query}
        onQueryChange={(q) => {
          setQuery(q)
          sel.clear()
        }}
        placeholder="搜索资产编号 / 型号 / 品牌 / 位置 / 产权…"
        resultText={
          <>
            显示 <strong>{visible.length}</strong>
            {filterCat ? ` · ${filterCat}` : ''}
            {filterStatus ? ` · ${filterStatus}` : ''}
            {filterAlloc ? ` · ${filterAlloc}` : ''}
            {filterLocKind ? ` · ${filterLocKind}` : ''}
          </>
        }
        selectedCount={sel.selectedCount}
        onClearSelection={sel.clear}
        batchActions={
          <>
            <button
              type="button"
              disabled={batchBusy}
              onClick={() => batchSetAlloc('通用可调')}
            >
              批量·通用可调
            </button>
            <button
              type="button"
              className="secondary"
              disabled={batchBusy}
              onClick={() => batchSetAlloc('保留')}
            >
              批量·保留
            </button>
          </>
        }
      />

      <div className="pl-table-wrap">
        <table className="pl-table">
          <thead>
            <tr>
              <th className="lt-check-col">
                <input
                  type="checkbox"
                  checked={sel.allVisibleSelected}
                  ref={(el) => {
                    if (el) el.indeterminate = sel.someVisibleSelected
                  }}
                  onChange={sel.toggleAllVisible}
                  aria-label="全选当前列表"
                />
              </th>
              <th>资产编号</th>
              <th>类型 / 型号</th>
              <HeaderFilter
                label="状态"
                value={filterStatus}
                options={Object.keys(STATUS_META)}
                totals={statusTotals}
                open={openFilter === 'status'}
                onToggle={(v) => setOpenFilter(v ? 'status' : '')}
                onSelect={(v) => setFilter({ status: v })}
              />
              <HeaderFilter
                label="可调配"
                value={filterAlloc}
                options={ALLOC_OPTIONS}
                totals={allocTotals}
                open={openFilter === 'alloc'}
                onToggle={(v) => setOpenFilter(v ? 'alloc' : '')}
                onSelect={(v) => setFilter({ alloc: v })}
              />
              <HeaderFilter
                label="位置"
                value={filterLocKind}
                options={LOC_KIND_OPTIONS}
                totals={locKindTotals}
                open={openFilter === 'loc'}
                onToggle={(v) => setOpenFilter(v ? 'loc' : '')}
                onSelect={(v) => setFilter({ loc: v })}
              />
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            {paged.map((p) => {
              const canToggleAlloc = p.current_status === '在库'
              const isGeneral = p.allocatable_flag === '通用可调'
              return (
                <tr
                  key={p.id}
                  className={`pl-row-click ${sel.isSelected(p.id) ? 'is-selected' : ''}`}
                  onClick={(e) => {
                    if (e.target.closest('a,button,input,label')) return
                    openDetail(p.id)
                  }}
                >
                  <td className="lt-check-col" onClick={(e) => e.stopPropagation()}>
                    <input
                      type="checkbox"
                      checked={sel.isSelected(p.id)}
                      onChange={() => sel.toggle(p.id)}
                      aria-label={`选择 ${p.fixed_asset_no}`}
                    />
                  </td>
                  <td>
                    <Link
                      className="pl-asset-link"
                      to={`/parts/${p.id}`}
                      onClick={(e) => e.stopPropagation()}
                    >
                      {p.fixed_asset_no}
                    </Link>
                    <div className="pl-sub">{p.owner_unit || '—'}</div>
                  </td>
                  <td>
                    <div className="pl-model-row">
                      <span
                        className="pl-cat-tag"
                        style={{
                          '--cat': CATEGORY_META[p.model?.category]?.color || '#64748b',
                        }}
                      >
                        {p.model?.category || '—'}
                      </span>
                      <span className="pl-model-name">
                        {p.model?.model_name || `#${p.model_id}`}
                      </span>
                    </div>
                    {p.model?.brand && (
                      <div className="pl-sub">{p.model.brand}</div>
                    )}
                  </td>
                  <td>
                    <span className={statusBadgeClass(p.current_status, p.is_overdue)}>
                      {p.current_status}
                      {p.is_overdue ? ' · 超期' : ''}
                    </span>
                  </td>
                  <td onClick={(e) => e.stopPropagation()}>
                    {canToggleAlloc ? (
                      <button
                        type="button"
                        className={`pl-alloc ${isGeneral ? 'is-general' : 'is-reserved'}`}
                        disabled={busyId === p.id}
                        onClick={(e) => toggleAlloc(p, e)}
                        title="点击切换：通用可调 / 保留（仅在库）"
                      >
                        {p.allocatable_flag || '—'}
                      </button>
                    ) : (
                      <span
                        className="pl-alloc-ro"
                        title="非在库状态不可调整可调配标记"
                      >
                        {p.allocatable_flag || '—'}
                      </span>
                    )}
                  </td>
                  <td className="pl-loc">{locLabel(p, servers, locs, orgs)}</td>
                  <td onClick={(e) => e.stopPropagation()}>
                    <div className="pl-actions">
                      <Link to={`/parts/${p.id}`}>详情</Link>
                      <Link to={`/parts/${p.id}/history`}>履历</Link>
                      {p.current_status === '在库' && (
                        <>
                          <Link to={`/parts/${p.id}/install`}>装机</Link>
                          <Link to={`/parts/${p.id}/loan`}>借出</Link>
                          <Link to={`/parts/${p.id}/transfer`}>调拨</Link>
                          <Link to={`/parts/${p.id}/scrap`}>报废</Link>
                          <Link to={`/parts/${p.id}/damage`}>报损</Link>
                        </>
                      )}
                      {p.current_status === '在用' && (
                        <Link to={`/parts/${p.id}/uninstall`}>拆下</Link>
                      )}
                      {p.current_status === '损坏' && (
                        <Link to={`/parts/${p.id}/scrap`}>报废</Link>
                      )}
                      {p.current_status === '借出' && (
                        <Link to={`/parts/${p.id}/return`}>归还</Link>
                      )}
                    </div>
                  </td>
                </tr>
              )
            })}
            {!paged.length && (
              <tr>
                <td colSpan={7} className="pl-empty">当前筛选下暂无配件</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      <div className="pl-pager">
        <span className="muted">
          共 {visible.length} 条 · 第 {safePage}/{totalPages} 页
        </span>
        <div className="pl-pager-btns">
          <button
            type="button"
            className="secondary"
            disabled={safePage <= 1}
            onClick={() => setPage(safePage - 1)}
          >
            上一页
          </button>
          {Array.from({ length: totalPages }, (_, i) => i + 1)
            .filter((n) => n === 1 || n === totalPages || Math.abs(n - safePage) <= 2)
            .reduce((acc, n, i, arr) => {
              if (i > 0 && n - arr[i - 1] > 1) acc.push('…')
              acc.push(n)
              return acc
            }, [])
            .map((n, i) =>
              n === '…' ? (
                <span key={`gap-${i}`} className="muted">…</span>
              ) : (
                <button
                  key={n}
                  type="button"
                  className={n === safePage ? '' : 'secondary'}
                  onClick={() => setPage(n)}
                >
                  {n}
                </button>
              ),
            )}
          <button
            type="button"
            className="secondary"
            disabled={safePage >= totalPages}
            onClick={() => setPage(safePage + 1)}
          >
            下一页
          </button>
        </div>
        <select
          value={pageSize}
          onChange={(e) => setPageSize(Number(e.target.value))}
          aria-label="每页条数"
        >
          <option value={10}>10 条/页</option>
          <option value={20}>20 条/页</option>
          <option value={50}>50 条/页</option>
        </select>
      </div>
    </div>
  )
}
