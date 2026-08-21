import { useEffect, useMemo, useState } from 'react'
import { api } from '../api'
import { ALL_MANAGED_CATEGORIES } from '../lib/categories'
import ListToolbar from '../components/ListToolbar'
import { useSelection } from '../hooks/useSelection'
import { filterByQuery } from '../lib/fuzzy'
import AssetScopePicker from '../components/AssetScopePicker'
import { assetScopeLabel, level2Categories, level2CategoriesForDomain, managedLeafCategoriesForScopes } from '../lib/assetScopes'
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
    <div className="model-table-wrap brand-table-wrap">
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
            <th>品牌名称</th><th>适用配件 / 具体类型</th><th>适用设备类别（二级）</th><th>操作</th>
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
                <td><TagList values={brand.categories || []} emptyLabel={brand.asset_category_ids?.length ? '设备整机' : '全部类型'} /></td>
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
    () => level2CategoriesForDomain(assetTree, domainFilter),
    [assetTree, domainFilter],
  )
  const selectedScope = useMemo(() => allScopes.find((item) => String(item.id) === String(scopeFilter)), [allScopes, scopeFilter])
  const scopeTypes = useMemo(
    () => selectedScope
      ? managedLeafCategoriesForScopes([selectedScope])
      : domainFilter
        ? managedLeafCategoriesForScopes(domainScopes)
        : ALL_CATEGORIES.filter((category) => category !== '服务器'),
    [domainFilter, domainScopes, selectedScope],
  )
  const formScopes = useMemo(() => {
    const selected = new Set((form.asset_category_ids || []).map(Number))
    return allScopes.filter((scope) => selected.has(Number(scope.id)))
  }, [allScopes, form.asset_category_ids])
  const formTypes = useMemo(
    () => formScopes.length ? managedLeafCategoriesForScopes(formScopes) : ALL_CATEGORIES.filter((category) => category !== '服务器'),
    [formScopes],
  )

  const brandsInScope = useMemo(() => {
    const domainScopeIds = new Set(domainScopes.map((item) => Number(item.id)))
    return brands.filter((brand) => {
      const brandScopes = brand.asset_category_ids || []
      const scopeMatch = !scopeFilter || !brandScopes.length || brandScopes.includes(Number(scopeFilter))
      const domainMatch = !domainFilter || !brandScopes.length || brandScopes.some((id) => domainScopeIds.has(Number(id)))
      return scopeMatch && domainMatch
    })
  }, [brands, domainFilter, domainScopes, scopeFilter])

  const filtered = useMemo(() => {
    const scoped = brandsInScope.filter((brand) => {
      if (!filterCat) return true
      const categories = brand.categories || []
      if (categories.length) return categories.includes(filterCat)
      return !(brand.asset_category_ids || []).length
    })
    return filterByQuery(scoped, query, (brand) => [brand.name, ...(brand.categories || []), catsLabel(brand.categories), assetScopeLabel(brand.asset_category_ids, assetTree)])
  }, [assetTree, brandsInScope, filterCat, query])

  const pagination = usePagination(filtered)
  const visibleIds = useMemo(() => pagination.pageItems.map((brand) => brand.id), [pagination.pageItems])
  const sel = useSelection(visibleIds)
  const universalCount = useMemo(() => brands.filter((brand) => !(brand.categories || []).length && !(brand.asset_category_ids || []).length).length, [brands])
  const brandCountForScope = (id) => brands.filter((brand) => !(brand.asset_category_ids || []).length || brand.asset_category_ids.includes(Number(id))).length
  const brandCountForType = (category) => brandsInScope.filter((brand) => {
    const categories = brand.categories || []
    return categories.length ? categories.includes(category) : !(brand.asset_category_ids || []).length
  }).length

  function closeForm() { setShowForm(false); setEditingId(null); setForm(emptyForm) }
  function openCreate() {
    setEditingId(null)
    setForm({ ...emptyForm, categories: filterCat ? [filterCat] : [], asset_category_ids: scopeFilter ? [Number(scopeFilter)] : [] })
    setShowForm(true)
  }
  function toggleCat(cat) {
    setForm((current) => ({ ...current, categories: current.categories.includes(cat) ? current.categories.filter((item) => item !== cat) : [...current.categories, cat] }))
  }
  function changeFormScopes(ids) {
    const selected = new Set(ids.map(Number))
    const scopes = allScopes.filter((scope) => selected.has(Number(scope.id)))
    const allowed = new Set(scopes.length ? managedLeafCategoriesForScopes(scopes) : ALL_CATEGORIES.filter((category) => category !== '服务器'))
    setForm((current) => ({
      ...current,
      asset_category_ids: ids,
      categories: current.categories.filter((category) => allowed.has(category)),
    }))
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

  function chooseDomain(id) { setDomainFilter(id); setScopeFilter(''); setFilterCat(''); sel.clear() }
  const listTitle = filterCat ? `${filterCat} · 品牌列表` : selectedScope ? `${selectedScope.domain} / ${selectedScope.name} · 可用品牌` : activeDomain ? `${activeDomain.name} · 可用品牌` : '全部品牌'

  return (
    <div className="panel brand-page">
      <div className="model-page-head">
        <div><h2>品牌管理</h2><p className="muted">沿资产目录逐级定位品牌，分别管理设备整机与配件具体类型的适用范围。</p></div>
        <div className="model-page-actions">
          <div className="model-stats" aria-label="品牌统计"><span><strong>{brands.length}</strong>品牌总数</span><span><strong>{universalCount}</strong>全局通用</span><span><strong>{allScopes.length}</strong>设备类别</span></div>
          <button type="button" className="model-add-button" onClick={openCreate}>+ 新增品牌</button>
        </div>
      </div>
      {error && <div className="error">{error}</div>}{ok && <div className="ok-msg">{ok}</div>}

      <section className="model-catalog-browser" aria-label="品牌目录筛选">
        <div className="model-browser-step"><span>01</span><strong>选择专业</strong></div>
        <div className="model-domain-row">
          <button type="button" className={!domainFilter ? 'is-active' : ''} onClick={() => chooseDomain('')}>全部专业</button>
          {assetTree.filter((root) => root.enabled).map((root) => <button key={root.id} type="button" className={String(domainFilter) === String(root.id) ? 'is-active' : ''} onClick={() => chooseDomain(String(root.id))}>{root.name}<small>{(root.children || []).filter((item) => item.enabled).length}</small></button>)}
        </div>

        <div className="model-browser-step"><span>02</span><strong>设备整机类别（二级目录）</strong></div>
        <div className="model-scope-grid">
          {(domainFilter ? domainScopes : allScopes).map((scope) => <button key={scope.id} type="button" className={String(scopeFilter) === String(scope.id) ? 'is-active' : ''} onClick={() => { setDomainFilter(String(scope.domainId)); setScopeFilter(String(scope.id)); setFilterCat(''); sel.clear() }}><span><strong>{scope.name}</strong><small>{scope.code || '未设置编码'}</small></span><em>{brandCountForScope(scope.id)}</em></button>)}
          {!(domainFilter ? domainScopes : allScopes).length && <p className="muted">该专业暂无二级设备类别</p>}
        </div>

        <div className="model-browser-step"><span>03</span><strong>品牌对象：设备整机或三级具体类型</strong></div>
        <div className="model-type-row">
          <button type="button" className={!filterCat ? 'is-active' : ''} onClick={() => { setFilterCat(''); sel.clear() }}>全部类型<small>{brandsInScope.length}</small></button>
          {scopeTypes.map((category) => <button key={category} type="button" className={filterCat === category ? 'is-active' : ''} onClick={() => { setFilterCat(category); sel.clear() }}>{category}<small>{brandCountForType(category)}</small></button>)}
          {!scopeTypes.length && <span className="model-types-empty">该设备类别尚未关联已落地的三级具体类型</span>}
        </div>
      </section>

      <section className="model-list-card">
        <div className="model-list-heading"><div><span>品牌目录</span><h3>{listTitle}</h3></div><p>通用品牌会自动出现在各个适用目录中</p></div>
        <ListToolbar query={query} onQueryChange={(value) => { setQuery(value); sel.clear() }} placeholder="搜索品牌名、具体类型或资产目录…" resultText={<> 显示 <strong>{filtered.length}</strong> 个品牌</>} selectedCount={sel.selectedCount} onClearSelection={sel.clear} batchActions={<button type="button" className="secondary danger-outline" disabled={batchBusy} onClick={batchDelete}>批量删除</button>} />
        {filtered.length ? <BrandTable rows={pagination.pageItems} sel={sel} onEdit={startEdit} onDelete={onDelete} tree={assetTree} /> : <div className="model-empty-state"><span>◇</span><strong>暂无匹配品牌</strong><p>调整目录筛选，或点击右上角新增品牌。</p></div>}
        <Pagination pagination={pagination} />
      </section>

      {showForm && (
        <div className="model-modal-overlay" role="presentation" onMouseDown={(e) => { if (e.target === e.currentTarget) closeForm() }}>
          <form className="model-modal" onSubmit={onSubmit}>
            <div className="model-modal-head"><div><span>{editingId ? '编辑品牌' : '新增品牌'}</span><h3>{editingId ? `修改品牌 #${editingId}` : '建立品牌档案'}</h3></div><button type="button" className="model-modal-close" onClick={closeForm} aria-label="关闭">×</button></div>
            <div className="model-modal-body">
              <section className="model-form-section brand-form-section">
                <div className="model-form-section-title"><span>01</span><div><strong>品牌基本信息</strong><small>品牌名称将用于型号管理和设备档案</small></div></div>
                <label>品牌名称 *<input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} required autoFocus placeholder="如：华为、NVIDIA、三星" /></label>
              </section>
              <section className="model-form-section brand-form-section">
                <div className="model-form-section-title"><span>02</span><div><strong>适用设备整机（二级目录）</strong><small>服务器、交换机、存储设备等整机品牌在这里独立维护</small></div></div>
                <AssetScopePicker tree={assetTree} value={form.asset_category_ids} onChange={changeFormScopes} />
              </section>
              <section className="model-form-section brand-form-section">
                <div className="model-form-section-title"><span>03</span><div><strong>适用配件 / 具体类型（三级目录）</strong><small>仅展示所选设备类别下已接入的三级类型</small></div></div>
                <div className="brand-form-chips">{formTypes.map((category) => <button key={category} type="button" className={form.categories.includes(category) ? 'active' : ''} onClick={() => toggleCat(category)}><span>{form.categories.includes(category) ? '✓' : '+'}</span>{category}</button>)}</div>
                {!formTypes.length && <p className="muted brand-form-empty">所选设备类别尚未关联具体类型；品牌仍可作为该二级目录的设备整机品牌。</p>}
              </section>
              <div className="brand-scope-summary"><span>当前适用范围</span><strong>{form.categories.length ? catsLabel(form.categories) : form.asset_category_ids.length ? '设备整机品牌' : '全局通用品牌'} · {assetScopeLabel(form.asset_category_ids, assetTree)}</strong></div>
            </div>
            <div className="model-modal-actions"><button type="button" className="secondary" onClick={closeForm}>取消</button><button type="submit">{editingId ? '保存修改' : '创建品牌'}</button></div>
          </form>
        </div>
      )}
    </div>
  )
}
