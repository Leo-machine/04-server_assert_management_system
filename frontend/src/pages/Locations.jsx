import { useEffect, useMemo, useState } from 'react'
import { api, getStoredUser } from '../api'
import { isLeader } from '../lib/roles'
import { ALL_MANAGED_CATEGORIES } from '../lib/categories'
import ListToolbar from '../components/ListToolbar'
import Pagination from '../components/Pagination'
import { usePagination } from '../hooks/usePagination'
import { filterByQuery } from '../lib/fuzzy'

const LOCATION_TYPES = ['库房货架', '机房备件柜', '数据中心机柜', '其他']

const TYPE_ICONS = {
  '库房货架': '🏭',
  '机房备件柜': '🗄',
  '数据中心机柜': '🏢',
  '其他': '📍',
}

const STATUS_COLORS = {
  '在库': '#0f766e',
  '损坏': '#b91c1c',
}

const emptyForm = { warehouse: '', slot: '', location_type: '', allowed_categories: [] }

export default function Locations() {
  const [locations, setLocations] = useState([])
  const [distribution, setDistribution] = useState([])
  const [form, setForm] = useState(emptyForm)
  const [editingId, setEditingId] = useState(null)
  const [error, setError] = useState('')
  const [ok, setOk] = useState('')
  const [query, setQuery] = useState('')
  const [typeFilter, setTypeFilter] = useState('')
  const [showForm, setShowForm] = useState(false)
  const isAdmin = isLeader(getStoredUser())

  async function load() {
    const [locs, dist] = await Promise.all([
      api.get('/storage-locations'),
      api.get('/storage-locations/distribution'),
    ])
    setLocations(locs)
    setDistribution(dist)
  }

  useEffect(() => {
    load().catch((e) => setError(e.message))
  }, [])

  const maxCount = useMemo(
    () => Math.max(1, ...distribution.map((d) => d.part_count)),
    [distribution],
  )
  const visibleLocations = useMemo(() => filterByQuery(
    typeFilter ? locations.filter((loc) => (loc.location_type || '通用') === typeFilter) : locations,
    query,
    (loc) => [loc.warehouse, loc.slot, loc.location_type, ...(loc.allowed_categories || [])],
  ), [locations, query, typeFilter])
  const visibleDistribution = useMemo(() => typeFilter ? distribution.filter((item) => (item.location_type || '通用') === typeFilter) : distribution, [distribution, typeFilter])
  const locationStats = useMemo(() => ({
    totalParts: locations.reduce((sum, loc) => sum + (loc.part_count || 0), 0),
    used: locations.filter((loc) => (loc.part_count || 0) > 0).length,
    empty: locations.filter((loc) => !(loc.part_count || 0)).length,
  }), [locations])
  const pagination = usePagination(visibleLocations)

  function resetForm() {
    setEditingId(null)
    setForm(emptyForm)
    setShowForm(false)
  }

  function openCreate() {
    setEditingId(null)
    setForm({ ...emptyForm, location_type: typeFilter === '通用' ? '' : typeFilter })
    setShowForm(true)
  }

  function toggleCat(cat) {
    setForm((f) => ({
      ...f,
      allowed_categories: f.allowed_categories.includes(cat)
        ? f.allowed_categories.filter((c) => c !== cat)
        : [...f.allowed_categories, cat],
    }))
  }

  function startEdit(loc) {
    setEditingId(loc.id)
    setForm({
      warehouse: loc.warehouse,
      slot: loc.slot,
      location_type: loc.location_type || '',
      allowed_categories: [...(loc.allowed_categories || [])],
    })
    setError('')
    setOk('')
    setShowForm(true)
  }

  async function onSubmit(e) {
    e.preventDefault()
    setError('')
    setOk('')
    const body = {
      warehouse: form.warehouse,
      slot: form.slot,
      location_type: form.location_type || null,
      allowed_categories: form.allowed_categories.length ? form.allowed_categories : null,
    }
    try {
      if (editingId) {
        await api.put(`/storage-locations/${editingId}`, body)
        setOk(`已更新 #${editingId}`)
      } else {
        await api.post('/storage-locations', body)
        setOk(`已新增：${form.warehouse}/${form.slot}`)
      }
      await load()
      resetForm()
    } catch (err) {
      setError(err.message)
    }
  }

  async function onDelete(loc) {
    const label = `${loc.warehouse}/${loc.slot}`
    if (!window.confirm(`确认删除「${label}」？有配件存放的不可删。`)) return
    setError('')
    setOk('')
    try {
      await api.delete(`/storage-locations/${loc.id}`)
      setOk(`已删除 #${loc.id}`)
      await load()
    } catch (err) {
      setError(err.message)
    }
  }

  return (
    <div className="panel location-workbench">
      <header className="location-header">
        <div><span className="location-kicker">空间资源 · LOCATION OPERATIONS</span><h2>存放位管理</h2><p className="muted">统一管理库房、机房和数据中心的物理库位与入库范围。</p></div>
        {isAdmin ? <button type="button" className="location-add-button" onClick={openCreate}>+ 新增存放位置</button> : <div className="location-readonly"><span>只读视图</span><strong>增删改需领导权限</strong></div>}
      </header>
      {error && <div className="error">{error}</div>}{ok && <div className="ok-msg">{ok}</div>}

      <section className="location-stats" aria-label="库位统计">
        <div><span className="location-stat-icon">▦</span><p><strong>{locations.length}</strong><small>库位总数</small></p></div>
        <div><span className="location-stat-icon is-parts">▣</span><p><strong>{locationStats.totalParts}</strong><small>存放配件</small></p></div>
        <div><span className="location-stat-icon is-used">●</span><p><strong>{locationStats.used}</strong><small>使用中库位</small></p></div>
        <div><span className="location-stat-icon is-empty">○</span><p><strong>{locationStats.empty}</strong><small>空闲库位</small></p></div>
      </section>

      <section className="location-type-browser">
        <div className="location-section-head"><div><span>01</span><h3>按位置类型查看</h3></div><p>选择类型后，分布图和列表将同步筛选</p></div>
        <div className="location-type-cards">
          <button type="button" className={!typeFilter ? 'active' : ''} onClick={() => setTypeFilter('')}><span className="location-type-icon">全</span><p><strong>全部位置</strong><small>{locations.length} 个库位</small></p></button>
          {[...LOCATION_TYPES, '通用'].map((type) => { const count = locations.filter((loc) => (loc.location_type || '通用') === type).length; return <button key={type} type="button" className={typeFilter === type ? 'active' : ''} onClick={() => setTypeFilter(type)}><span className="location-type-icon">{TYPE_ICONS[type] || '◇'}</span><p><strong>{type}</strong><small>{count} 个库位</small></p></button> })}
        </div>
      </section>

      <section className="location-distribution-card">
        <div className="location-section-head"><div><span>02</span><h3>配件空间分布</h3></div><div className="loc-legend">{Object.entries(STATUS_COLORS).map(([status, color]) => <span key={status} className="loc-legend-item"><i style={{ background: color }} />{status}</span>)}</div></div>
        {visibleDistribution.length ? <div className="loc-bars">{visibleDistribution.map((item) => {
          const pct = Math.round((item.part_count / maxCount) * 100)
          return <div key={item.id} className="loc-bar-col"><div className="loc-bar-value">{item.part_count}<small>件</small></div><div className="loc-bar-track"><div className="loc-bar-fill" style={{ height: `${pct}%` }}>{Object.entries(item.parts_by_status || {}).map(([status, count]) => <div key={status} className="loc-bar-seg" style={{ height: `${item.part_count ? Math.round((count / item.part_count) * 100) : 0}%`, background: STATUS_COLORS[status] || '#94a3b8' }} title={`${status}: ${count}`} />)}</div></div><div className="loc-bar-label"><span>{TYPE_ICONS[item.location_type] || '◇'} {item.warehouse}</span><small>{item.slot}</small></div></div>
        })}</div> : <div className="location-empty"><span>◇</span><strong>当前类型暂无库位数据</strong></div>}
      </section>

      <section className="location-list-card">
        <div className="location-section-head"><div><span>03</span><h3>{typeFilter ? `${typeFilter}位置列表` : '全部位置列表'}</h3></div><p>已存放配件的库位不可删除</p></div>
        <ListToolbar query={query} onQueryChange={setQuery} placeholder="搜索区域 / 位置 / 类型 / 允许配件…" resultText={<> 显示 <strong>{visibleLocations.length}</strong> / {locations.length}</>} />
        <div className="location-table-wrap"><table className="location-table">
          <thead><tr><th>库位信息</th><th>位置类型</th><th>允许入库配件</th><th>当前库存</th><th>使用状态</th>{isAdmin && <th>操作</th>}</tr></thead>
          <tbody>{pagination.pageItems.map((loc) => <tr key={loc.id}><td><div className="location-name-cell"><span>{TYPE_ICONS[loc.location_type] || '◇'}</span><div><strong>{loc.warehouse}</strong><small>{loc.slot} · 编号 #{loc.id}</small></div></div></td><td><span className="location-type-badge">{loc.location_type || '通用'}</span></td><td><div className="location-category-tags">{loc.allowed_categories?.length ? loc.allowed_categories.slice(0, 4).map((cat) => <span key={cat}>{cat}</span>) : <span className="is-universal">全部类型</span>}{loc.allowed_categories?.length > 4 && <em>+{loc.allowed_categories.length - 4}</em>}</div></td><td><strong className="location-count">{loc.part_count || 0}</strong><small className="location-count-unit"> 件</small></td><td><span className={`location-usage ${loc.part_count ? 'is-used' : 'is-empty'}`}><i />{loc.part_count ? '使用中' : '空闲'}</span></td>{isAdmin && <td><div className="row-actions location-row-actions"><button type="button" className="secondary" onClick={() => startEdit(loc)}>编辑</button><button type="button" className="secondary danger-outline" disabled={(loc.part_count || 0) > 0} title={loc.part_count ? '已存放配件，不可删除' : '删除库位'} onClick={() => onDelete(loc)}>删除</button></div></td>}</tr>)}
          {!visibleLocations.length && <tr><td colSpan={isAdmin ? 6 : 5}><div className="location-empty"><span>◇</span><strong>暂无匹配位置</strong></div></td></tr>}
          </tbody>
        </table></div>
        <Pagination pagination={pagination} />
      </section>

      {showForm && <div className="location-modal-overlay" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) resetForm() }}><form className="location-modal" onSubmit={onSubmit}>
        <div className="location-modal-head"><div><span>{editingId ? '编辑库位' : '新增库位'}</span><h3>{editingId ? `修改位置 #${editingId}` : '建立物理存放位置'}</h3></div><button type="button" onClick={resetForm} aria-label="关闭">×</button></div>
        <div className="location-form-grid"><label>区域名称 *<input value={form.warehouse} onChange={(e) => setForm({ ...form, warehouse: e.target.value })} required autoFocus placeholder="如：一号库房 / A栋数据中心" /></label><label>具体位置 *<input value={form.slot} onChange={(e) => setForm({ ...form, slot: e.target.value })} required placeholder="如：A-01 / Rack-B-03" /></label></div>
        <div className="location-form-section"><div><strong>位置类型</strong><small>用于库位分类、查询和分布统计</small></div><div className="location-form-types"><button type="button" className={!form.location_type ? 'active' : ''} onClick={() => setForm({ ...form, location_type: '' })}>◇ 通用</button>{LOCATION_TYPES.map((type) => <button key={type} type="button" className={form.location_type === type ? 'active' : ''} onClick={() => setForm({ ...form, location_type: type })}>{TYPE_ICONS[type]} {type}</button>)}</div></div>
        <div className="location-form-section"><div><strong>允许入库的配件类型</strong><small>不选择代表所有类型均可入库</small></div><div className="location-form-categories">{ALL_MANAGED_CATEGORIES.map((cat) => <button key={cat} type="button" className={form.allowed_categories.includes(cat) ? 'active' : ''} onClick={() => toggleCat(cat)}><span>{form.allowed_categories.includes(cat) ? '✓' : '+'}</span>{cat}</button>)}</div></div>
        <div className="location-form-summary"><span>当前规则</span><strong>{form.location_type || '通用位置'} · {form.allowed_categories.length ? `允许 ${form.allowed_categories.length} 类配件` : '允许全部配件'}</strong></div>
        <div className="location-modal-actions"><button type="button" className="secondary" onClick={resetForm}>取消</button><button type="submit">{editingId ? '保存修改' : '创建位置'}</button></div>
      </form></div>}
    </div>
  )
}
