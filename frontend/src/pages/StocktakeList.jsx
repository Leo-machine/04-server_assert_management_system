import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, getStoredUser } from '../api'
import ListToolbar from '../components/ListToolbar'
import Pagination from '../components/Pagination'
import { filterByQuery } from '../lib/fuzzy'
import { usePagination } from '../hooks/usePagination'
import { OPS_ROLES, hasRole } from '../lib/roles'
import { PART_CATEGORIES, RESPONSIBLE_GROUPS } from '../lib/categories'

const SCOPE_KINDS = ['全盘', '按机房', '按责任组', '按配件类型', '指定清单']
const emptyForm = { scope_kind: '全盘', location_id: '', responsible_group: RESPONSIBLE_GROUPS[0], category: PART_CATEGORIES[0], asset_nos: '' }

function scopeLabel(task, locations) {
  const value = task.scope_value || {}
  if (task.scope_kind === '按机房') {
    const location = locations.find((item) => item.id === value.location_id)
    return location ? `${location.warehouse}/${location.slot}` : `库位 #${value.location_id || '—'}`
  }
  if (task.scope_kind === '按责任组') return value.responsible_group || '—'
  if (task.scope_kind === '按配件类型') return value.category || '—'
  if (task.scope_kind === '指定清单') return `${value.asset_nos?.length || value.part_ids?.length || 0} 件指定配件`
  return '全部在册配件'
}

function dateText(value) {
  if (!value) return '—'
  return new Date(value).toLocaleString('zh-CN', { hour12: false })
}

export default function StocktakeList() {
  const [list, setList] = useState([])
  const [locations, setLocations] = useState([])
  const [error, setError] = useState('')
  const [msg, setMsg] = useState('')
  const [query, setQuery] = useState('')
  const [statusFilter, setStatusFilter] = useState('')
  const [showCreate, setShowCreate] = useState(false)
  const [form, setForm] = useState(emptyForm)
  const [busy, setBusy] = useState(false)
  const canManage = hasRole(getStoredUser(), OPS_ROLES)

  async function load() {
    const [tasks, locs] = await Promise.all([api.get('/stocktakes'), api.get('/storage-locations')])
    setList(tasks)
    setLocations(locs)
  }

  useEffect(() => { load().catch((e) => setError(e.message)) }, [])

  const stats = useMemo(() => ({
    running: list.filter((task) => task.status === '进行中').length,
    completed: list.filter((task) => task.status === '已完成').length,
    differences: list.reduce((sum, task) => sum + (task.summary?.['盘亏'] || 0) + (task.summary?.['盘盈'] || 0) + (task.summary?.['错位'] || 0), 0),
  }), [list])
  const visible = useMemo(() => {
    const scoped = statusFilter ? list.filter((task) => task.status === statusFilter) : list
    return filterByQuery(scoped, query, (task) => [task.id, task.scope_kind, scopeLabel(task, locations), task.status, task.initiator_name])
  }, [list, locations, query, statusFilter])
  const pagination = usePagination(visible)

  function closeCreate() { setShowCreate(false); setForm(emptyForm) }

  async function createTask(event) {
    event.preventDefault()
    setBusy(true); setError(''); setMsg('')
    let scopeValue = null
    if (form.scope_kind === '按机房') scopeValue = { location_id: Number(form.location_id) }
    if (form.scope_kind === '按责任组') scopeValue = { responsible_group: form.responsible_group }
    if (form.scope_kind === '按配件类型') scopeValue = { category: form.category }
    if (form.scope_kind === '指定清单') scopeValue = { asset_nos: form.asset_nos.split(/[,，、\s]+/).map((item) => item.trim()).filter(Boolean) }
    try {
      const task = await api.post('/stocktakes', { scope_kind: form.scope_kind, scope_value: scopeValue })
      setMsg(`已发起${form.scope_kind} #${task.id}，冻结 ${task.items?.length || 0} 条盘点明细`)
      await load(); closeCreate()
    } catch (e) { setError(e.message) }
    finally { setBusy(false) }
  }

  return (
    <div className="panel stocktake-workbench">
      <header className="stocktake-header"><div><span className="stocktake-kicker">资产盘点 · STOCKTAKE OPERATIONS</span><h2>盘点管理</h2><p className="muted">基于冻结快照发现盘亏、盘盈与错位，不直接改写资产状态和履历。</p></div>{canManage ? <button type="button" className="stocktake-add-button" onClick={() => setShowCreate(true)}>+ 发起盘点</button> : <div className="stocktake-readonly"><span>只读视图</span><strong>当前角色不可发起或结案</strong></div>}</header>
      {error && <div className="error">{error}</div>}{msg && <div className="ok-msg">{msg}</div>}

      <section className="stocktake-stats">
        <button type="button" className={!statusFilter ? 'active' : ''} onClick={() => setStatusFilter('')}><span>▣</span><p><strong>{list.length}</strong><small>盘点任务</small></p></button>
        <button type="button" className={statusFilter === '进行中' ? 'active' : ''} onClick={() => setStatusFilter('进行中')}><span className="is-running">◷</span><p><strong>{stats.running}</strong><small>进行中</small></p></button>
        <button type="button" className={statusFilter === '已完成' ? 'active' : ''} onClick={() => setStatusFilter('已完成')}><span className="is-done">✓</span><p><strong>{stats.completed}</strong><small>已完成</small></p></button>
        <div><span className="is-diff">!</span><p><strong>{stats.differences}</strong><small>累计差异</small></p></div>
      </section>

      <section className="stocktake-list-card">
        <div className="stocktake-section-head"><div><span>01</span><h3>{statusFilter ? `${statusFilter}任务` : '全部盘点任务'}</h3></div><p>点击“进入盘点”开展扫码、函证与差异处理</p></div>
        <ListToolbar query={query} onQueryChange={setQuery} placeholder="搜索单号 / 范围 / 责任人 / 状态…" resultText={<> 显示 <strong>{visible.length}</strong> / {list.length}</>} />
        <div className="stocktake-table-wrap"><table className="stocktake-table">
          <thead><tr><th>盘点任务</th><th>盘点范围</th><th>执行进度</th><th>差异</th><th>发起人 / 时间</th><th>状态</th><th>操作</th></tr></thead>
          <tbody>{pagination.pageItems.map((task) => {
            const pending = task.summary?.['待复核'] || 0
            const checked = Math.max(0, (task.item_count || 0) - pending)
            const progress = task.item_count ? Math.round(checked / task.item_count * 100) : 0
            const differences = (task.summary?.['盘亏'] || 0) + (task.summary?.['盘盈'] || 0) + (task.summary?.['错位'] || 0)
            return <tr key={task.id}><td><div className="stocktake-id"><span>#</span><div><strong>盘点单 {task.id}</strong><small>{task.scope_kind}</small></div></div></td><td><strong className="stocktake-scope">{scopeLabel(task, locations)}</strong></td><td><div className="stocktake-progress"><div><i style={{ width: `${progress}%` }} /></div><span>{checked}/{task.item_count || 0} · {progress}%</span></div></td><td><span className={`stocktake-diff ${differences ? 'has-diff' : ''}`}>{differences}</span></td><td><div className="stocktake-initiator"><strong>{task.initiator_name || `用户 #${task.initiator_id}`}</strong><small>{dateText(task.initiated_at)}</small></div></td><td><span className={`stocktake-status ${task.status === '进行中' ? 'is-running' : 'is-done'}`}><i />{task.status}</span></td><td><Link className="stocktake-enter" to={`/stocktakes/${task.id}`}>进入盘点 →</Link></td></tr>
          })}{!visible.length && <tr><td colSpan={7}><div className="stocktake-empty"><span>◇</span><strong>{list.length ? '暂无匹配盘点任务' : '尚未发起盘点任务'}</strong></div></td></tr>}</tbody>
        </table></div><Pagination pagination={pagination} />
      </section>

      {showCreate && <div className="stocktake-modal-overlay" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) closeCreate() }}><form className="stocktake-modal" onSubmit={createTask}>
        <div className="stocktake-modal-head"><div><span>新建任务</span><h3>选择盘点范围</h3></div><button type="button" onClick={closeCreate} aria-label="关闭">×</button></div>
        <div className="stocktake-scope-options">{SCOPE_KINDS.map((kind) => <button key={kind} type="button" className={form.scope_kind === kind ? 'active' : ''} onClick={() => setForm({ ...form, scope_kind: kind })}><span>{kind === '全盘' ? '全' : kind.slice(1, 2)}</span><strong>{kind}</strong></button>)}</div>
        <div className="stocktake-scope-field">
          {form.scope_kind === '全盘' && <div className="stocktake-full-tip"><strong>将冻结全部在册配件</strong><span>适合周期性全面盘点</span></div>}
          {form.scope_kind === '按机房' && <label>选择存放位置 *<select value={form.location_id} onChange={(e) => setForm({ ...form, location_id: e.target.value })} required><option value="">— 请选择 —</option>{locations.map((loc) => <option key={loc.id} value={loc.id}>{loc.warehouse}/{loc.slot}</option>)}</select></label>}
          {form.scope_kind === '按责任组' && <label>选择责任组 *<select value={form.responsible_group} onChange={(e) => setForm({ ...form, responsible_group: e.target.value })}>{RESPONSIBLE_GROUPS.map((group) => <option key={group}>{group}</option>)}</select></label>}
          {form.scope_kind === '按配件类型' && <label>选择配件类型 *<select value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value })}>{PART_CATEGORIES.map((category) => <option key={category}>{category}</option>)}</select></label>}
          {form.scope_kind === '指定清单' && <label>固定资产编号 *<textarea value={form.asset_nos} onChange={(e) => setForm({ ...form, asset_nos: e.target.value })} required rows={4} placeholder="输入资产编号，可用逗号、空格或换行分隔" /></label>}
        </div>
        <div className="stocktake-modal-note"><strong>安全说明</strong><span>盘点仅生成冻结快照和差异记录，不会直接修改实时资产状态。</span></div>
        <div className="stocktake-modal-actions"><button type="button" className="secondary" onClick={closeCreate}>取消</button><button type="submit" disabled={busy}>{busy ? '创建中…' : '确认发起盘点'}</button></div>
      </form></div>}
    </div>
  )
}
