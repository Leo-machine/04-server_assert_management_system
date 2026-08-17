import { useEffect, useMemo, useState } from 'react'
import { api } from '../api'
import { ALL_MANAGED_CATEGORIES } from '../lib/categories'
import ListToolbar from '../components/ListToolbar'
import { useSelection } from '../hooks/useSelection'
import { filterByQuery } from '../lib/fuzzy'
import AssetScopePicker from '../components/AssetScopePicker'
import { assetScopeLabel, level2Categories } from '../lib/assetScopes'
import Pagination from '../components/Pagination'
import { usePagination } from '../hooks/usePagination'

const ALL_CATEGORIES = ALL_MANAGED_CATEGORIES
const emptyForm = { name: '', categories: [], asset_category_ids: [] }

function catsLabel(cats) {
  return cats?.length ? cats.join('、') : '通用（全部类型）'
}

function TagList({ values, emptyLabel, tone = '' }) {
  const visible = values.slice(0, 3)
  return (
    <div className="brand-tags">
      {!values.length && <span className={`brand-tag is-universal ${tone}`}>{emptyLabel}</span>}
      {visible.map((value) => <span key={value} className={`brand-tag ${tone}`}>{value}</span>)}
      {values.length > 3 && <span className="brand-tag is-more">+{values.length - 3}</span>}
    </div>
  )
}

function BrandTable({ rows, sel, onEdit, onDelete, tree }) {
  return (
    <div className="brand-table-wrap">
      <table className="brand-table">
        <thead>
          <tr>
            <th className="lt-check-col">
              <input
                type="checkbox"
                checked={sel.allVisibleSelected}
                ref={(el) => { if (el) el.indeterminate = sel.someVisibleSelected }}
                onChange={sel.toggleAllVisible}
                aria-label="全选"
              />
            </th>
            <th>品牌名称</th><th>适用具体类型</th><th>适用专业 / 设备类别</th><th>操作</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((brand) => {
            const scopes = brand.asset_category_ids?.length
              ? assetScopeLabel(brand.asset_category_ids, tree).split('、')
              : []
            return (
              <tr key={brand.id} className={sel.isSelected(brand.id) ? 'is-selected' : ''}>
                <td className="lt-check-col"><input type="checkbox" checked={sel.isSelected(brand.id)} onChange={() => sel.toggle(brand.id)} aria-label={`选择 ${brand.name}`} /></td>
                <td>
                  <div className="brand-name-cell">
                    <span className="brand-avatar">{brand.name.trim().slice(0, 1).toUpperCase()}</span>
                    <div><strong>{brand.name}</strong><small>品牌编号 #{brand.id}</small></div>
                  </div>
                </td>
                <td><TagList values={brand.categories || []} emptyLabel="全部类型" /></td>
                <td><TagList values={scopes} emptyLabel="全部专业与类别" tone="is-scope" /></td>
                <td><div className="row-actions brand-row-actions"><button type="button" className="secondary" onClick={() => onEdit(brand)}>编辑</button><button type="button" className="secondary danger-outline" onClick={() => onDelete(brand)}>删除</button></div></td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

export default function Brands() {
  const [brands, setBrands] = useState([])
  const [assetTree, setAssetTree] = useState([])
  const [domainFilter, setDomainFilter] = useState('')
  const [scopeFilter, setScopeFilter] = useState('')
  const [filterCat, setFilterCat] = useState('')
  const [form, setForm] = useState(emptyForm)
  const [editingId, setEditingId] = useState(null)
  const [showForm, setShowForm] = useState(false)
  const [error, setError] = useState('')
  const [ok, setOk] = useState('')
  const [query, setQuery] = useState('')
  const [batchBusy, setBatchBusy] = useState(false)

  async function loadBrands() { setBrands(await api.get('/brands')) }

  useEffect(() => {
    let cancelled = false
    Promise.all([api.get('/brands'), api.get('/asset-categories?tree=true')])
      .then(([list, tree]) => {
        if (!cancelled) { setBrands(list); setAssetTree(tree) }
      })
      .catch((e) => { if (!cancelled) setError(e.message) })
    return () => { cancelled = true }
  }, [])

  const allScopes = useMemo(() => level2Categories(assetTree), [assetTree])
  const activeDomain = useMemo(() => assetTree.find((root) => String(root.id) === String(domainFilter)), [assetTree, domainFilter])
  const domainScopes = useMemo(
    () => domainFilter ? allScopes.filter((item) => String(item.parentId) === String(domainFilter)) : allScopes,
    [allScopes, domainFilter],
  )
  const selectedScope = useMemo(() => allScopes.find((item) => String(item.id) === String(scopeFilter)), [allScopes, scopeFilter])

  const filtered = useMemo(() => {
    const domainScopeIds = new Set(domainScopes.map((item) => Number(item.id)))
    const scoped = brands.filter((brand) => {
      const brandScopes = brand.asset_category_ids || []
      const categoryMatch = !filterCat || !(brand.categories || []).length || brand.categories.includes(filterCat)
      const scopeMatch = !scopeFilter || !brandScopes.length || brandScopes.includes(Number(scopeFilter))
      const domainMatch = !domainFilter || !brandScopes.length || brandScopes.some((id) => domainScopeIds.has(Number(id)))
      return categoryMatch && scopeMatch && domainMatch
    })
    return filterByQuery(scoped, query, (brand) => [brand.name, ...(brand.categories || []), catsLabel(brand.categories), assetScopeLabel(brand.asset_category_ids, assetTree)])
  }, [assetTree, brands, domainFilter, domainScopes, filterCat, query, scopeFilter])

  const pagination = usePagination(filtered)
  const visibleIds = useMemo(() => pagination.pageItems.map((brand) => brand.id), [pagination.pageItems])
  const sel = useSelection(visibleIds)
  const universalCount = useMemo(() => brands.filter((brand) => !(brand.categories || []).length && !(brand.asset_category_ids || []).length).length, [brands])
  const brandCountForScope = (id) => brands.filter((brand) => !(brand.asset_category_ids || []).length || brand.asset_category_ids.includes(Number(id))).length
  const brandCountForType = (category) => brands.filter((brand) => !(brand.categories || []).length || brand.categories.includes(category)).length

  function closeForm() { setShowForm(false); setEditingId(null); setForm(emptyForm) }
  function openCreate() {
    setEditingId(null)
    setForm({ ...emptyForm, categories: filterCat ? [filterCat] : [], asset_category_ids: scopeFilter ? [Number(scopeFilter)] : [] })
    setShowForm(true)
  }
  function toggleCat(cat) {
    setForm((current) => ({ ...current, categories: current.categories.includes(cat) ? current.categories.filter((item) => item !== cat) : [...current.categories, cat] }))
  }
  function startEdit(brand) {
    setEditingId(brand.id)
    setForm({ name: brand.name, categories: [...(brand.categories || [])], asset_category_ids: [...(brand.asset_category_ids || [])] })
    setShowForm(true)
  }

  async function onSubmit(e) {
    e.preventDefault(); setError(''); setOk('')
    const body = { name: form.name, categories: form.categories, asset_category_ids: form.asset_category_ids }
    try {
      if (editingId) { await api.put(`/brands/${editingId}`, body); setOk(`已更新品牌「${form.name}」`) }
      else { await api.post('/brands', body); setOk(`已新增品牌「${form.name}」`) }
      await loadBrands(); closeForm()
    } catch (err) { setError(err.message) }
  }

  async function onDelete(brand) {
    if (!window.confirm(`确认删除品牌「${brand.name}」？已有型号引用的品牌不可删除。`)) return
    setError(''); setOk('')
    try { await api.delete(`/brands/${brand.id}`); setOk(`已删除品牌「${brand.name}」`); await loadBrands(); sel.clear() }
    catch (err) { setError(err.message) }
  }

  async function batchDelete() {
    const targets = filtered.filter((brand) => sel.isSelected(brand.id))
    if (!targets.length || !window.confirm(`尝试删除选中的 ${targets.length} 个品牌？已被型号引用的品牌将跳过。`)) return
    setBatchBusy(true); setError(''); setOk('')
    let deletedCount = 0; const errors = []
    for (const brand of targets) {
      try { await api.delete(`/brands/${brand.id}`); deletedCount += 1 }
      catch (e) { errors.push(`${brand.name}: ${e.message}`) }
    }
    await loadBrands(); sel.clear(); setBatchBusy(false)
    if (errors.length) setError(errors.slice(0, 3).join('；'))
    if (deletedCount) setOk(`已删除 ${deletedCount} 个品牌`)
  }

  function chooseDomain(id) { setDomainFilter(id); setScopeFilter(''); sel.clear() }
  const listTitle = selectedScope ? `${selectedScope.domain} / ${selectedScope.name} · 可用品牌` : activeDomain ? `${activeDomain.name} · 可用品牌` : filterCat ? `${filterCat} · 可用品牌` : '全部品牌'

  return (
    <div className="panel brand-page">
      <div className="brand-page-head">
        <div><span className="brand-page-kicker">基础数据 · 品牌资产库</span><h2>品牌管理</h2><p className="muted">按资产专业、设备类别和具体类型统一维护品牌适用范围。</p></div>
        <div className="brand-page-actions">
          <div className="brand-page-stats" aria-label="品牌统计"><div><strong>{brands.length}</strong><span>品牌总数</span></div><div><strong>{universalCount}</strong><span>全局通用</span></div><div><strong>{allScopes.length}</strong><span>设备类别</span></div></div>
          <button type="button" className="brand-add-button" onClick={openCreate}>+ 新增品牌</button>
        </div>
      </div>
      {error && <div className="error">{error}</div>}{ok && <div className="ok-msg">{ok}</div>}

      <section className="brand-catalog-browser" aria-label="品牌目录筛选">
        <div className="brand-filter-step">
          <div className="brand-step-label"><span>01</span><strong>选择资产专业</strong></div>
          <div className="brand-domain-tabs">
            <button type="button" className={!domainFilter ? 'active' : ''} onClick={() => chooseDomain('')}><strong>全部专业</strong><small>{brands.length} 个品牌</small></button>
            {assetTree.map((root) => {
              const ids = new Set((root.children || []).map((child) => Number(child.id)))
              const count = brands.filter((brand) => !(brand.asset_category_ids || []).length || brand.asset_category_ids.some((id) => ids.has(Number(id)))).length
              return <button key={root.id} type="button" className={String(domainFilter) === String(root.id) ? 'active' : ''} onClick={() => chooseDomain(String(root.id))}><strong>{root.name}</strong><small>{count} 个可用品牌</small></button>
            })}
          </div>
        </div>

        <div className="brand-filter-step">
          <div className="brand-step-label"><span>02</span><strong>选择设备类别</strong></div>
          <div className="brand-scope-grid">
            <button type="button" className={!scopeFilter ? 'active' : ''} onClick={() => { setScopeFilter(''); sel.clear() }}><span className="brand-scope-icon">全</span><span><strong>全部类别</strong><small>{activeDomain ? activeDomain.name : '所有专业'}</small></span></button>
            {domainScopes.map((scope) => <button key={scope.id} type="button" className={String(scopeFilter) === String(scope.id) ? 'active' : ''} onClick={() => { setDomainFilter(String(scope.parentId)); setScopeFilter(String(scope.id)); sel.clear() }}><span className="brand-scope-icon">{scope.name.slice(0, 1)}</span><span><strong>{scope.name}</strong><small>{brandCountForScope(scope.id)} 个可用品牌</small></span></button>)}
          </div>
        </div>

        <div className="brand-filter-step is-last">
          <div className="brand-step-label"><span>03</span><strong>细分具体类型</strong></div>
          <div className="brand-type-tabs">
            <button type="button" className={!filterCat ? 'active' : ''} onClick={() => { setFilterCat(''); sel.clear() }}>全部类型 <em>{brands.length}</em></button>
            {ALL_CATEGORIES.map((category) => <button key={category} type="button" className={filterCat === category ? 'active' : ''} onClick={() => { setFilterCat(category); sel.clear() }}>{category} <em>{brandCountForType(category)}</em></button>)}
          </div>
        </div>
      </section>

      <section className="brand-list-card">
        <div className="brand-list-heading"><div><span className="brand-list-eyebrow">品牌目录</span><h3>{listTitle}</h3></div><p>通用品牌会自动出现在各个适用目录中</p></div>
        <ListToolbar query={query} onQueryChange={(value) => { setQuery(value); sel.clear() }} placeholder="搜索品牌名、具体类型或资产目录…" resultText={<> 显示 <strong>{filtered.length}</strong> 个品牌</>} selectedCount={sel.selectedCount} onClearSelection={sel.clear} batchActions={<button type="button" className="secondary danger-outline" disabled={batchBusy} onClick={batchDelete}>批量删除</button>} />
        {filtered.length ? <BrandTable rows={pagination.pageItems} sel={sel} onEdit={startEdit} onDelete={onDelete} tree={assetTree} /> : <div className="brand-empty-state"><span>◇</span><strong>暂无匹配品牌</strong><p>调整筛选条件，或新增适用于当前目录的品牌。</p></div>}
        <Pagination pagination={pagination} />
      </section>

      {showForm && (
        <div className="brand-modal-overlay" role="presentation" onMouseDown={(e) => { if (e.target === e.currentTarget) closeForm() }}>
          <form className="brand-modal" onSubmit={onSubmit}>
            <div className="brand-modal-head"><div><span>{editingId ? '编辑品牌' : '新增品牌'}</span><h3>{editingId ? `修改品牌 #${editingId}` : '建立品牌适用范围'}</h3></div><button type="button" className="brand-modal-close" onClick={closeForm} aria-label="关闭">×</button></div>
            <div className="brand-form-section">
              <div className="brand-form-section-title"><span>01</span><div><strong>基本信息</strong><small>品牌名称将用于型号管理和设备档案</small></div></div>
              <label>品牌名称 *<input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} required autoFocus placeholder="如：华为、NVIDIA、三星" /></label>
            </div>
            <div className="brand-form-section">
              <div className="brand-form-section-title"><span>02</span><div><strong>适用具体类型</strong><small>不选择代表全部具体类型均可使用</small></div></div>
              <div className="brand-form-chips">{ALL_CATEGORIES.map((category) => <button key={category} type="button" className={form.categories.includes(category) ? 'active' : ''} onClick={() => toggleCat(category)}><span>{form.categories.includes(category) ? '✓' : '+'}</span>{category}</button>)}</div>
            </div>
            <div className="brand-form-section">
              <div className="brand-form-section-title"><span>03</span><div><strong>适用专业与设备类别</strong><small>不选择代表所有专业与设备类别均可使用</small></div></div>
              <AssetScopePicker tree={assetTree} value={form.asset_category_ids} onChange={(ids) => setForm({ ...form, asset_category_ids: ids })} />
            </div>
            <div className="brand-scope-summary"><span>当前适用范围</span><strong>{catsLabel(form.categories)} · {assetScopeLabel(form.asset_category_ids, assetTree)}</strong></div>
            <div className="brand-modal-actions"><button type="button" className="secondary" onClick={closeForm}>取消</button><button type="submit">{editingId ? '保存修改' : '创建品牌'}</button></div>
          </form>
        </div>
      )}
    </div>
  )
}
