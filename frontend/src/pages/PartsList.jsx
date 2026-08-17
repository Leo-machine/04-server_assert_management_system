import { useEffect, useMemo, useState } from 'react'
import { Link, Navigate, useNavigate, useSearchParams } from 'react-router-dom'
import { api, getStoredUser } from '../api'
import HeaderFilter from '../components/HeaderFilter'
import BatchOpModal from '../components/BatchOpModal'
import ListToolbar from '../components/ListToolbar'
import { useSelection } from '../hooks/useSelection'
import { filterByQuery } from '../lib/fuzzy'
import { OPS_ROLES, hasRole, homePathFor } from '../lib/roles'
import { PART_CATEGORIES } from '../lib/categories'
import { locLabel } from '../lib/locLabel'
import Pagination from '../components/Pagination'
import { usePagination } from '../hooks/usePagination'

const CATEGORY_ORDER = PART_CATEGORIES

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
  const [openFilter, setOpenFilter] = useState('') // status | alloc | loc | ''
  const [batchOp, setBatchOp] = useState(null) // install/loan/transfer/scrap/damage
  const [users, setUsers] = useState([])
  const me = getStoredUser()
  const canInstall = hasRole(me, OPS_ROLES)
  const canLoan = hasRole(me, OPS_ROLES)
  const canViewParts = hasRole(me, OPS_ROLES)

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
    if (!canViewParts) return undefined
    reload().catch((e) => setError(e.message))
  }, [canViewParts])

  // 搜索命中集（不含类型/表头列筛选），供分类卡片与列表共用
  const searchedParts = useMemo(() => {
    const tokens = query.split(/[,，、\s]+/).map((t) => t.trim()).filter(Boolean)
    if (tokens.length > 1) {
      return parts.filter((p) => {
        const hay = [
          p.fixed_asset_no, p.serial_no, p.owner_unit, p.allocatable_flag,
          p.current_status, p.model?.category, p.model?.model_name,
          p.model?.brand, p.model?.pn, p.supplier, p.project,
          locLabel(p, servers, locs, orgs),
        ].filter(Boolean).join(' ').toLowerCase()
        return tokens.some((t) => hay.includes(t.toLowerCase()))
      })
    }
    return filterByQuery(parts, query, (p) => [
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
  }, [parts, query, servers, locs, orgs])

  // 表头筛选项计数：受其它已选条件约束（不含本列自身），避免「在库 8」下仍显示可调配 808
  const scopedParts = useMemo(() => {
    if (!filterCat) return searchedParts
    return searchedParts.filter((p) => (p.model?.category || '') === filterCat)
  }, [searchedParts, filterCat])

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

  // 分类卡片：受状态/可调配/位置/搜索约束，不受当前选中类型约束
  const categoryStats = useMemo(() => {
    const map = {}
    for (const cat of CATEGORY_ORDER) {
      map[cat] = { total: 0, byStatus: {} }
    }
    for (const p of applyOtherFilters(searchedParts)) {
      const cat = p.model?.category || '未分类'
      if (!map[cat]) map[cat] = { total: 0, byStatus: {} }
      map[cat].total += 1
      const st = p.current_status || '未知'
      map[cat].byStatus[st] = (map[cat].byStatus[st] || 0) + 1
    }
    return map
  }, [searchedParts, filterStatus, filterAlloc, filterLocKind])

  const pagination = usePagination(visible)
  const visibleIds = useMemo(() => pagination.pageItems.map((p) => p.id), [pagination.pageItems])
  const sel = useSelection(visibleIds)

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

  function eligibleFor(op) {
    const selected = visible.filter((p) => sel.isSelected(p.id))
    if (op === 'scrap') return selected.filter((p) => ['在库', '损坏'].includes(p.current_status))
    return selected.filter((p) => p.current_status === '在库')
  }

  function openBatchOp(op) {
    setError('')
    const targets = eligibleFor(op)
    if (!targets.length) {
      setError(op === 'scrap'
        ? '所选配件中没有「在库/损坏」项，无法批量报废'
        : '所选配件中没有「在库」项（装机/借出/调拨/报损仅在库可操作）')
      return
    }
    if (!users.length) {
      api.get('/users').then(setUsers).catch(() => {})
    }
    setBatchOp(op)
  }

  async function onBatchDone({ okN, errors, opTitle }) {
    setBatchOp(null)
    setError('')
    setOk('')
    await reload()
    sel.clear()
    if (errors.length) {
      setError(`${opTitle}：成功 ${okN} 件，失败 ${errors.length} 件——${errors.slice(0, 3).join('；')}${errors.length > 3 ? ' 等' : ''}`)
    } else {
      setOk(`${opTitle}：全部成功（${okN} 件）`)
    }
  }

  function openDetail(id) {
    nav(`/parts/${id}`)
  }

  if (!canViewParts) {
    return <Navigate to={homePathFor(me)} replace />
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
        placeholder="搜索资产编号 / 型号 / 品牌…（可用逗号分隔多编号批量显示）"
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
            {canLoan && (
              <>
                <span className="bt-group">
                  <button type="button" disabled={batchBusy} onClick={() => batchSetAlloc('通用可调')}>
                    通用可调
                  </button>
                  <button type="button" disabled={batchBusy} onClick={() => batchSetAlloc('保留')}>
                    保留
                  </button>
                </span>
                <span className="bt-sep" />
              </>
            )}
            {(canInstall || canLoan) && (
              <>
                <span className="bt-group">
                  {canInstall && (
                    <button type="button" className="bt-primary" disabled={batchBusy} onClick={() => openBatchOp('install')}>
                      装机
                    </button>
                  )}
                  {canLoan && (
                    <>
                      <button type="button" disabled={batchBusy} onClick={() => openBatchOp('loan')}>
                        借出
                      </button>
                      <button type="button" disabled={batchBusy} onClick={() => openBatchOp('transfer')}>
                        调拨
                      </button>
                      <button type="button" disabled={batchBusy} onClick={() => openBatchOp('damage')}>
                        报损
                      </button>
                    </>
                  )}
                </span>
                {canLoan && (
                  <>
                    <span className="bt-sep" />
                    <button type="button" className="bt-danger" disabled={batchBusy} onClick={() => openBatchOp('scrap')}>
                      报废
                    </button>
                  </>
                )}
              </>
            )}
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
            {pagination.pageItems.map((p) => {
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
                          {canInstall && <Link to={`/parts/${p.id}/install`}>装机</Link>}
                          {canLoan && (
                            <>
                              <Link to={`/parts/${p.id}/loan`}>借出</Link>
                              <Link to={`/parts/${p.id}/transfer`}>调拨</Link>
                              <Link to={`/parts/${p.id}/scrap`}>报废</Link>
                              <Link to={`/parts/${p.id}/damage`}>报损</Link>
                            </>
                          )}
                        </>
                      )}
                      {p.current_status === '在用' && canInstall && (
                        <Link to={`/parts/${p.id}/uninstall`}>拆下</Link>
                      )}
                      {p.current_status === '损坏' && canLoan && (
                        <Link to={`/parts/${p.id}/scrap`}>报废</Link>
                      )}
                      {p.current_status === '借出' && canLoan && (
                        <Link to={`/parts/${p.id}/return`}>归还</Link>
                      )}
                    </div>
                  </td>
                </tr>
              )
            })}
            {!pagination.pageItems.length && (
              <tr>
                <td colSpan={7} className="pl-empty">当前筛选下暂无配件</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      <Pagination pagination={pagination} />

      {batchOp && (
        <BatchOpModal
          op={batchOp}
          targets={eligibleFor(batchOp)}
          servers={servers}
          orgs={orgs}
          users={users}
          locs={locs}
          onClose={() => setBatchOp(null)}
          onDone={onBatchDone}
        />
      )}
    </div>
  )
}
