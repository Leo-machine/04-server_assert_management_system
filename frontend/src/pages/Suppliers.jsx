import { useEffect, useMemo, useState } from 'react'
import { api } from '../api'
import ListToolbar from '../components/ListToolbar'
import Pagination from '../components/Pagination'
import AssetScopePicker from '../components/AssetScopePicker'
import { useSelection } from '../hooks/useSelection'
import { usePagination } from '../hooks/usePagination'
import { filterByQuery } from '../lib/fuzzy'
import { assetScopeLabel, level2Categories, level2CategoriesForDomain } from '../lib/assetScopes'

const emptyForm = { name: '', contact: '', contact_info: '', remark: '', asset_category_ids: [] }

export default function Suppliers() {
  const [list, setList] = useState([])
  const [assetTree, setAssetTree] = useState([])
  const [form, setForm] = useState(emptyForm)
  const [editingId, setEditingId] = useState(null)
  const [showForm, setShowForm] = useState(false)
  const [error, setError] = useState('')
  const [ok, setOk] = useState('')
  const [query, setQuery] = useState('')
  const [batchBusy, setBatchBusy] = useState(false)
  const [domainFilter, setDomainFilter] = useState('')
  const [scopeFilter, setScopeFilter] = useState('')

  async function load() {
    const [rows, tree] = await Promise.all([api.get('/suppliers'), api.get('/asset-categories?tree=true')])
    setList(rows); setAssetTree(tree)
  }
  useEffect(() => { load().catch((e) => setError(e.message)) }, [])

  const allScopes = useMemo(() => level2Categories(assetTree), [assetTree])
  const domainScopes = useMemo(() => level2CategoriesForDomain(assetTree, domainFilter), [assetTree, domainFilter])
  const activeDomain = assetTree.find((root) => String(root.id) === String(domainFilter))
  const selectedScope = allScopes.find((item) => String(item.id) === String(scopeFilter))
  const visible = useMemo(() => {
    const domainIds = new Set(domainScopes.map((item) => Number(item.id)))
    const scoped = list.filter((supplier) => {
      const ids = supplier.asset_category_ids || []
      const scopeMatch = !scopeFilter || !ids.length || ids.includes(Number(scopeFilter))
      const domainMatch = !domainFilter || !ids.length || ids.some((id) => domainIds.has(Number(id)))
      return scopeMatch && domainMatch
    })
    return filterByQuery(scoped, query, (supplier) => [supplier.name, supplier.contact, supplier.contact_info, supplier.remark, assetScopeLabel(supplier.asset_category_ids, assetTree)])
  }, [assetTree, domainFilter, domainScopes, list, query, scopeFilter])
  const pagination = usePagination(visible)
  const visibleIds = useMemo(() => pagination.pageItems.map((supplier) => supplier.id), [pagination.pageItems])
  const sel = useSelection(visibleIds)
  const stats = useMemo(() => ({
    universal: list.filter((supplier) => !(supplier.asset_category_ids || []).length).length,
    complete: list.filter((supplier) => supplier.contact && supplier.contact_info).length,
    references: list.reduce((sum, supplier) => sum + (supplier.usage_count || 0), 0),
  }), [list])

  function closeForm() { setShowForm(false); setEditingId(null); setForm(emptyForm) }
  function openCreate() { setEditingId(null); setForm({ ...emptyForm, asset_category_ids: scopeFilter ? [Number(scopeFilter)] : [] }); setShowForm(true) }
  function startEdit(supplier) {
    setEditingId(supplier.id)
    setForm({ name: supplier.name || '', contact: supplier.contact || '', contact_info: supplier.contact_info || '', remark: supplier.remark || '', asset_category_ids: [...(supplier.asset_category_ids || [])] })
    setShowForm(true); setError(''); setOk('')
  }

  async function onSubmit(event) {
    event.preventDefault(); setError(''); setOk('')
    const body = { name: form.name, contact: form.contact || null, contact_info: form.contact_info || null, remark: form.remark || null, asset_category_ids: form.asset_category_ids }
    try {
      if (editingId) { await api.put(`/suppliers/${editingId}`, body); setOk(`已更新供应商「${form.name}」`) }
      else { await api.post('/suppliers', body); setOk(`已新增供应商「${form.name}」`) }
      await load(); closeForm()
    } catch (err) { setError(err.message) }
  }

  async function onDelete(supplier) {
    if (!window.confirm(`确认删除供应商「${supplier.name}」？已有配件引用的不可删除。`)) return
    setError(''); setOk('')
    try { await api.delete(`/suppliers/${supplier.id}`); setOk(`已删除供应商「${supplier.name}」`); await load(); sel.clear() }
    catch (err) { setError(err.message) }
  }

  async function batchDelete() {
    const targets = visible.filter((supplier) => sel.isSelected(supplier.id))
    if (!targets.length || !window.confirm(`尝试删除选中的 ${targets.length} 个供应商？已被引用的将跳过。`)) return
    setBatchBusy(true); setError(''); setOk('')
    let deleted = 0; const errors = []
    for (const supplier of targets) {
      try { await api.delete(`/suppliers/${supplier.id}`); deleted += 1 }
      catch (e) { errors.push(`${supplier.name}: ${e.message}`) }
    }
    await load(); sel.clear(); setBatchBusy(false)
    if (errors.length) setError(errors.slice(0, 3).join('；'))
    if (deleted) setOk(`已删除 ${deleted} 个供应商`)
  }

  function chooseDomain(id) { setDomainFilter(id); setScopeFilter(''); sel.clear() }
  const listTitle = selectedScope ? `${selectedScope.domain} / ${selectedScope.name} · 可用供应商` : activeDomain ? `${activeDomain.name} · 可用供应商` : '全部供应商'

  return (
    <div className="panel supplier-workbench">
      <header className="supplier-header"><div><span className="supplier-kicker">供应资源 · SUPPLIER DIRECTORY</span><h2>供应商管理</h2><p className="muted">按资产专业和设备类别维护供应商名录、联系方式与适用范围。</p></div><button type="button" className="supplier-add-button" onClick={openCreate}>+ 新增供应商</button></header>
      {error && <div className="error">{error}</div>}{ok && <div className="ok-msg">{ok}</div>}
      <section className="supplier-stats"><div><span>▣</span><p><strong>{list.length}</strong><small>供应商总数</small></p></div><div><span className="is-universal">全</span><p><strong>{stats.universal}</strong><small>全局通用</small></p></div><div><span className="is-contact">☎</span><p><strong>{stats.complete}</strong><small>联系信息完整</small></p></div><div><span className="is-reference">⇄</span><p><strong>{stats.references}</strong><small>资产引用数</small></p></div></section>

      <section className="supplier-catalog-browser">
        <div className="supplier-filter-row"><div className="supplier-filter-label"><span>01</span><strong>选择资产专业</strong></div><div className="supplier-domain-tabs"><button type="button" className={!domainFilter ? 'active' : ''} onClick={() => chooseDomain('')}>全部专业</button>{assetTree.map((root) => <button key={root.id} type="button" className={String(domainFilter) === String(root.id) ? 'active' : ''} onClick={() => chooseDomain(String(root.id))}>{root.name}</button>)}</div></div>
        <div className="supplier-filter-row is-last"><div className="supplier-filter-label"><span>02</span><strong>选择设备类别</strong></div><div className="supplier-scope-grid"><button type="button" className={!scopeFilter ? 'active' : ''} onClick={() => { setScopeFilter(''); sel.clear() }}><span>全</span><p><strong>全部类别</strong><small>{activeDomain?.name || '所有专业'}</small></p></button>{domainScopes.map((scope) => <button key={scope.id} type="button" className={String(scopeFilter) === String(scope.id) ? 'active' : ''} onClick={() => { setDomainFilter(String(scope.domainId)); setScopeFilter(String(scope.id)); sel.clear() }}><span>{scope.name.slice(0, 1)}</span><p><strong>{scope.name}</strong><small>{scope.domain}</small></p></button>)}</div></div>
      </section>

      <section className="supplier-list-card"><div className="supplier-section-head"><div><span>供应商目录</span><h3>{listTitle}</h3></div><p>通用供应商会自动出现在各适用目录</p></div>
        <ListToolbar query={query} onQueryChange={(value) => { setQuery(value); sel.clear() }} placeholder="搜索名称 / 联系人 / 联系方式 / 资产目录…" resultText={<> 显示 <strong>{visible.length}</strong> / {list.length}</>} selectedCount={sel.selectedCount} onClearSelection={sel.clear} batchActions={<button type="button" className="secondary danger-outline" disabled={batchBusy} onClick={batchDelete}>批量删除</button>} />
        <div className="supplier-table-wrap"><table className="supplier-table"><thead><tr><th className="lt-check-col"><input type="checkbox" checked={sel.allVisibleSelected} ref={(el) => { if (el) el.indeterminate = sel.someVisibleSelected }} onChange={sel.toggleAllVisible} aria-label="全选" /></th><th>供应商</th><th>联系信息</th><th>适用专业 / 设备类别</th><th>资产引用</th><th>操作</th></tr></thead><tbody>
          {pagination.pageItems.map((supplier) => <tr key={supplier.id} className={sel.isSelected(supplier.id) ? 'is-selected' : ''}><td className="lt-check-col"><input type="checkbox" checked={sel.isSelected(supplier.id)} onChange={() => sel.toggle(supplier.id)} aria-label={`选择 ${supplier.name}`} /></td><td><div className="supplier-name-cell"><span>{supplier.name.slice(0, 1)}</span><div><strong>{supplier.name}</strong><small>{supplier.remark || `供应商编号 #${supplier.id}`}</small></div></div></td><td><div className="supplier-contact"><strong>{supplier.contact || '未填写联系人'}</strong><small>{supplier.contact_info || '未填写联系方式'}</small></div></td><td><span className={`supplier-scope-label ${supplier.asset_category_ids?.length ? '' : 'is-universal'}`}>{assetScopeLabel(supplier.asset_category_ids, assetTree)}</span></td><td><span className={`supplier-usage ${supplier.usage_count ? 'is-used' : ''}`}>{supplier.usage_count || 0} 件</span></td><td><div className="row-actions supplier-row-actions"><button type="button" className="secondary" onClick={() => startEdit(supplier)}>编辑</button><button type="button" className="secondary danger-outline" disabled={supplier.usage_count > 0} title={supplier.usage_count ? '已有资产引用，不可删除' : '删除供应商'} onClick={() => onDelete(supplier)}>删除</button></div></td></tr>)}
          {!visible.length && <tr><td colSpan={6}><div className="supplier-empty"><span>◇</span><strong>{list.length ? '暂无匹配供应商' : '暂无供应商'}</strong></div></td></tr>}
        </tbody></table></div><Pagination pagination={pagination} />
      </section>

      {showForm && <div className="supplier-modal-overlay" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) closeForm() }}><form className="supplier-modal" onSubmit={onSubmit}><div className="supplier-modal-head"><div><span>{editingId ? '编辑供应商' : '新增供应商'}</span><h3>{editingId ? `修改供应商 #${editingId}` : '建立供应商档案'}</h3></div><button type="button" onClick={closeForm} aria-label="关闭">×</button></div>
        <div className="supplier-form-grid"><label>供应商名称 *<input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} required autoFocus placeholder="如：华为技术有限公司" /></label><label>联系人<input value={form.contact} onChange={(e) => setForm({ ...form, contact: e.target.value })} placeholder="姓名" /></label><label>联系方式<input value={form.contact_info} onChange={(e) => setForm({ ...form, contact_info: e.target.value })} placeholder="电话 / 邮箱" /></label><label>备注<input value={form.remark} onChange={(e) => setForm({ ...form, remark: e.target.value })} placeholder="代理区域、服务级别等" /></label></div>
        <div className="supplier-form-section"><div><strong>供应资产专业与设备类别</strong><small>不选择表示全部专业与设备类别通用</small></div><AssetScopePicker tree={assetTree} value={form.asset_category_ids} onChange={(ids) => setForm({ ...form, asset_category_ids: ids })} /></div>
        <div className="supplier-form-summary"><span>当前适用范围</span><strong>{assetScopeLabel(form.asset_category_ids, assetTree)}</strong></div><div className="supplier-modal-actions"><button type="button" className="secondary" onClick={closeForm}>取消</button><button type="submit">{editingId ? '保存修改' : '创建供应商'}</button></div></form></div>}
    </div>
  )
}
