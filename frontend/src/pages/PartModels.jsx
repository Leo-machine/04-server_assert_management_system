import { useEffect, useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { api } from '../api'
import ListToolbar from '../components/ListToolbar'
import SpecFields, { formatSpec } from '../components/SpecFields'
import { useSelection } from '../hooks/useSelection'
import { filterByQuery } from '../lib/fuzzy'
import { assetScopeLabel, level2Categories } from '../lib/assetScopes'

/** 按类别从品牌+规格自动拼接型号名称 */
const NAME_TEMPLATES = {
  内存: (brand, spec) =>
    [brand, spec['容量GB'] ? `${spec['容量GB']}GB` : '', spec['内存类型'], spec['频率MHz'] ? `${spec['频率MHz']}MHz` : ''].filter(Boolean).join(' '),
  机械硬盘: (brand, spec) =>
    [brand, spec['容量TB'] ? `${spec['容量TB']}TB` : '', spec['接口'], spec['转速'] ? `${spec['转速']}RPM` : ''].filter(Boolean).join(' '),
  固态硬盘: (brand, spec) =>
    [brand, spec['容量GB'] ? `${spec['容量GB']}GB` : '', spec['接口协议'], spec['形态']].filter(Boolean).join(' '),
  RAID卡: (brand, spec) =>
    [brand, spec['通道数'] ? `${spec['通道数']}通道` : '', spec['缓存MB'] ? `${spec['缓存MB']}MB` : '', 'RAID卡'].filter(Boolean).join(' '),
  光模块: (brand, spec) =>
    [brand, spec['速率'], spec['类型'], '光模块'].filter(Boolean).join(' '),
  网卡: (brand, spec) =>
    [brand, spec['速率'], spec['口型'], spec['端口数'] ? `${spec['端口数']}口` : '', '网卡'].filter(Boolean).join(' '),
  HBA卡: (brand, spec) =>
    [brand, spec['子类型'], spec['速率'], spec['端口数'] ? `${spec['端口数']}口` : ''].filter(Boolean).join(' '),
  算力卡: (brand, spec) =>
    [brand, spec['显存GB'] ? `${spec['显存GB']}GB` : '', spec['封装'], spec['架构']].filter(Boolean).join(' '),
  服务器: (brand, spec) =>
    [brand, spec['机型高度U'] ? `${spec['机型高度U']}U` : '', spec['CPU型号'], '服务器'].filter(Boolean).join(' '),
}

const emptyForm = {
  category: '',
  model_name: '',
  brand: '',
  pn: '',
  spec: {},
  asset_category_id: '',
}

export default function PartModels() {
  const [params, setParams] = useSearchParams()
  const filterCat = params.get('category') || ''

  const [schemas, setSchemas] = useState([])
  const [models, setModels] = useState([])
  const [brands, setBrands] = useState([])
  const [form, setForm] = useState(emptyForm)
  const [editingId, setEditingId] = useState(null)
  const [error, setError] = useState('')
  const [ok, setOk] = useState('')
  const [query, setQuery] = useState('')
  const [batchBusy, setBatchBusy] = useState(false)
  const [assetTree, setAssetTree] = useState([])
  const [scopeFilter, setScopeFilter] = useState('')
  const [domainFilter, setDomainFilter] = useState('')

  const allScopes = useMemo(() => level2Categories(assetTree), [assetTree])
  const categories = useMemo(
    () => schemas.map((s) => s.category),
    [schemas],
  )
  const selectedScope = allScopes.find((item) => String(item.id) === scopeFilter)
  const activeDomain = assetTree.find((root) => String(root.id) === domainFilter)
  const domainScopes = useMemo(
    () => (activeDomain?.children || []).filter((item) => item.enabled),
    [activeDomain],
  )
  const formScope = allScopes.find((item) => String(item.id) === String(form.asset_category_id))
  const formDomain = assetTree.find((root) => root.id === formScope?.domainId)
  const typesForScopes = (scopes) => [...new Set(scopes.flatMap((scope) => [
    ...(scope.code === 'DIGITAL_SERVER' ? ['服务器'] : []),
    ...(scope.children || []).map((item) => item.business_category).filter(Boolean),
  ]))]
  const scopeTypes = selectedScope
    ? typesForScopes([selectedScope])
    : domainFilter
      ? typesForScopes(domainScopes)
      : categories

  const schema = useMemo(
    () => schemas.find((s) => s.category === form.category),
    [schemas, form.category],
  )

  const visible = useMemo(() => {
    const domainScopeIds = new Set(domainScopes.map((item) => item.id))
    const scoped = scopeFilter
      ? models.filter((m) => String(m.asset_category_id || '') === scopeFilter)
      : domainFilter
        ? models.filter((m) => domainScopeIds.has(m.asset_category_id))
        : models
    const byCat = filterCat ? scoped.filter((m) => m.category === filterCat) : scoped
    return filterByQuery(byCat, query, (m) => [
      m.category,
      m.model_name,
      m.brand,
      m.pn,
      JSON.stringify(m.spec || {}),
      m.capacity_gb,
      m.ddr_gen,
    ])
  }, [models, filterCat, query, scopeFilter, domainFilter, domainScopes])

  const visibleIds = useMemo(() => visible.map((m) => m.id), [visible])
  const sel = useSelection(visibleIds)

  const categoryBrands = useMemo(() => {
    const scopeId = Number(form.asset_category_id || 0)
    return brands.filter((b) => {
      const scopes = b.asset_category_ids || []
      if (scopes.length && (!scopeId || !scopes.includes(scopeId))) return false
      const cats = b.categories || []
      if (!cats.length) return true
      return cats.includes(form.category)
    })
  }, [brands, form.category, form.asset_category_id])

  async function load() {
    const [cats, ms, brs, tree] = await Promise.all([
      api.get('/categories'),
      api.get('/part-models'),
      api.get('/brands'),
      api.get('/asset-categories?tree=true'),
    ])
    setSchemas(cats)
    setModels(ms)
    setBrands(brs)
    setAssetTree(tree)
    const serverScope = level2Categories(tree).find((item) => item.code === 'DIGITAL_SERVER')
    const serverDomain = tree.find((root) => (root.children || []).some((item) => item.id === serverScope?.id))
    setDomainFilter((current) => current || (serverDomain ? String(serverDomain.id) : String(tree[0]?.id || '')))
    setScopeFilter((current) => current || (serverScope ? String(serverScope.id) : ''))
    setForm((f) => ({
      ...f,
      category: f.category || filterCat || cats[0]?.category || '',
      asset_category_id: f.asset_category_id || (serverScope ? String(serverScope.id) : ''),
    }))
  }

  useEffect(() => {
    load().catch((e) => setError(e.message))
  }, [])

  // 新增模式下根据品牌+规格自动拼接型号名称（编辑模式下不覆盖）
  useEffect(() => {
    if (editingId) return
    const fn = NAME_TEMPLATES[form.category]
    if (!fn) return
    const generated = fn(form.brand, form.spec)
    if (generated.trim()) {
      setForm((f) => ({ ...f, model_name: generated }))
    }
  }, [form.brand, form.spec, form.category, editingId])

  function resetForm(cat) {
    setEditingId(null)
    setForm({
      ...emptyForm,
      category: cat || filterCat || categories[0] || '',
      spec: {},
      asset_category_id: form.asset_category_id || '',
    })
  }

  function fillCreateForm(scope, preferredType = '') {
    if (!scope || editingId) return
    const availableTypes = typesForScopes([scope])
    const nextType = availableTypes.includes(preferredType)
      ? preferredType
      : availableTypes[0] || categories[0] || ''
    setForm((current) => ({
      ...(current.asset_category_id === String(scope.id) && current.category === nextType
        ? current
        : emptyForm),
      asset_category_id: String(scope.id),
      category: nextType,
    }))
  }

  function chooseDomain(root) {
    const firstScope = (root.children || []).find((item) => item.enabled)
    setDomainFilter(String(root.id))
    setScopeFilter(firstScope ? String(firstScope.id) : '')
    setParams({})
    sel.clear()
    if (firstScope) fillCreateForm({ ...firstScope, domainId: root.id, domain: root.name })
  }

  function chooseScope(scope) {
    setScopeFilter(String(scope.id))
    setDomainFilter(String(scope.domainId || activeDomain?.id || ''))
    setParams({})
    sel.clear()
    fillCreateForm(scope)
  }

  function chooseType(cat) {
    setParams({ category: cat })
    if (!editingId) {
      const scope = selectedScope || allScopes.find((item) => String(item.id) === String(form.asset_category_id))
      if (scope) fillCreateForm(scope, cat)
      else setForm((current) => ({ ...current, category: cat, brand: '', spec: {} }))
    }
  }

  function onSpecChange(key, value) {
    setForm((f) => ({ ...f, spec: { ...f.spec, [key]: value } }))
  }

  function startEdit(m) {
    setEditingId(m.id)
    setForm({
      category: m.category,
      model_name: m.model_name,
      brand: m.brand || '',
      pn: m.pn || '',
      spec: { ...(m.spec || {}) },
      asset_category_id: m.asset_category_id ? String(m.asset_category_id) : '',
    })
    setParams({ category: m.category })
    setError('')
    setOk('')
  }

  async function onSubmit(e) {
    e.preventDefault()
    setError('')
    setOk('')
    if (!form.asset_category_id) {
      setError('请选择所属资产专业与二级类别')
      return
    }
    const body = {
      category: form.category,
      model_name: form.model_name,
      brand: form.brand || null,
      pn: form.pn || null,
      spec: form.spec,
      asset_category_id: form.asset_category_id ? Number(form.asset_category_id) : null,
    }
    const savedCat = form.category
    try {
      if (editingId) {
        await api.put(`/part-models/${editingId}`, body)
        setOk(`已更新型号 #${editingId}`)
      } else {
        const created = await api.post('/part-models', body)
        setOk(`已新增型号：${created.model_name}`)
      }
      setParams(savedCat ? { category: savedCat } : {})
      await load()
      resetForm(savedCat)
    } catch (err) {
      setError(err.message)
    }
  }

  async function onDelete(m) {
    if (!window.confirm(`确认删除型号「${m.model_name}」？已有实物的型号不可删。`)) return
    setError('')
    setOk('')
    try {
      await api.delete(`/part-models/${m.id}`)
      setOk(`已删除型号 #${m.id}`)
      if (editingId === m.id) resetForm(m.category)
      await load()
      sel.clear()
    } catch (err) {
      setError(err.message)
    }
  }

  async function batchDelete() {
    const targets = visible.filter((m) => sel.isSelected(m.id))
    if (!targets.length) return
    if (!window.confirm(`尝试删除选中的 ${targets.length} 个型号？已被实物引用的将跳过失败。`)) return
    setBatchBusy(true)
    setError('')
    setOk('')
    let okN = 0
    const errors = []
    for (const m of targets) {
      try {
        await api.delete(`/part-models/${m.id}`)
        okN += 1
      } catch (e) {
        errors.push(`${m.model_name}: ${e.message}`)
      }
    }
    await load()
    sel.clear()
    setBatchBusy(false)
    if (errors.length) setError(errors.slice(0, 3).join('；'))
    if (okN) setOk(`已删除 ${okN} 个型号`)
  }

  return (
    <div className="panel">
      <div className="model-page-head">
        <div><h2>型号管理</h2><p className="muted">沿资产目录逐级定位型号，统一维护品牌、料号和规格参数。</p></div>
        <div className="model-stats"><span><strong>{models.length}</strong>型号总数</span><span><strong>{brands.length}</strong>品牌</span><span><strong>{allScopes.length}</strong>设备类别</span></div>
      </div>
      {error && <div className="error">{error}</div>}
      {ok && <div className="ok-msg">{ok}</div>}

      <div className="model-catalog-browser">
        <div className="model-browser-step"><span>01</span><strong>选择专业</strong></div>
        <div className="model-domain-row">
          <button type="button" className={!domainFilter ? 'is-active' : ''} onClick={() => { setDomainFilter(''); setScopeFilter(''); setParams({}); sel.clear() }}>全部专业</button>
          {assetTree.filter((root) => root.enabled).map((root) => <button key={root.id} type="button" className={domainFilter === String(root.id) ? 'is-active' : ''} onClick={() => chooseDomain(root)}>{root.name}<small>{(root.children || []).filter((item) => item.enabled).length}</small></button>)}
        </div>
        <div className="model-browser-step"><span>02</span><strong>选择设备类别</strong></div>
        <div className="model-scope-grid">
          {(domainFilter ? domainScopes : allScopes).map((item) => {
            const count = models.filter((model) => model.asset_category_id === item.id).length
            return <button key={item.id} type="button" className={scopeFilter === String(item.id) ? 'is-active' : ''} onClick={() => chooseScope(item)}><span><strong>{item.name}</strong><small>{item.code || '未设置编码'}</small></span><em>{count}</em></button>
          })}
          {!(domainFilter ? domainScopes : allScopes).length && <p className="muted">该专业暂无二级设备类别</p>}
        </div>
        <div className="model-browser-step"><span>03</span><strong>具体型号类型</strong></div>
        <div className="model-type-row">
          <button type="button" className={!filterCat ? 'is-active' : ''} onClick={() => setParams({})}>全部类型</button>
          {scopeTypes.map((cat) => <button key={cat} type="button" className={filterCat === cat ? 'is-active' : ''} onClick={() => chooseType(cat)}>{cat}<small>{models.filter((m) => (!scopeFilter || String(m.asset_category_id) === scopeFilter) && m.category === cat).length}</small></button>)}
          {!scopeTypes.length && <span className="model-types-empty">该目录尚未配置具体型号类型</span>}
        </div>
      </div>

      <div className="split-layout model-workspace">
        <form className="inbound-form" onSubmit={onSubmit}>
          <fieldset>
            <legend>{editingId ? `编辑型号 #${editingId}` : '新增型号'}</legend>
            <div className="model-form-path"><span>{formDomain?.name || '请选择专业'}</span><i>›</i><strong>{formScope?.name || '请选择设备类别'}</strong></div>
            <label>所属专业 *
              <select value={formDomain?.id || ''} onChange={(e) => { const root = assetTree.find((item) => String(item.id) === e.target.value); const first = (root?.children || []).find((item) => item.enabled); if (first) fillCreateForm({...first, domainId: root.id, domain: root.name}); else setForm({...form, asset_category_id: '', brand: ''}) }} required>
                <option value="">— 请选择专业 —</option>{assetTree.filter((root) => root.enabled).map((root) => <option key={root.id} value={root.id}>{root.name}</option>)}
              </select>
            </label>
            <label>设备类别 *
              <select value={form.asset_category_id} onChange={(e) => { const scope = allScopes.find((item) => String(item.id) === e.target.value); if (scope) fillCreateForm(scope) }} required>
                <option value="">— 请选择二级类别 —</option>{(formDomain?.children || []).filter((item) => item.enabled).map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
              </select>
            </label>
            <label>
              配件类型 *
              <select
                value={form.category}
                onChange={(e) =>
                  setForm({
                    ...form,
                    category: e.target.value,
                    brand: '',
                    spec: {},
                  })
                }
                required
                disabled={!!editingId}
              >
                {categories.map((c) => (
                  <option key={c} value={c}>{c}</option>
                ))}
              </select>
            </label>
            <label>
              型号名称 *
              <input
                value={form.model_name}
                onChange={(e) => setForm({ ...form, model_name: e.target.value })}
                required
                placeholder="自动拼接，可手动修改"
              />
              <span className="muted" style={{ fontSize: '0.75rem' }}>
                {editingId ? '手动输入' : '根据品牌 + 规格自动拼接，可覆盖'}
              </span>
            </label>
            <label>
              品牌
              <select
                value={form.brand}
                onChange={(e) => setForm({ ...form, brand: e.target.value })}
              >
                <option value="">— 请选择品牌 —</option>
                {categoryBrands.map((b) => (
                  <option key={b.id} value={b.name}>{b.name}</option>
                ))}
              </select>
            </label>
            <label>
              厂商料号 PN
              <input
                value={form.pn}
                onChange={(e) => setForm({ ...form, pn: e.target.value })}
                placeholder="型号料号（非实物 SN）"
              />
            </label>
          </fieldset>

          <fieldset>
            <legend>{form.category || '规格'}字段</legend>
            <SpecFields
              fields={schema?.fields || []}
              values={form.spec}
              onChange={onSpecChange}
            />
          </fieldset>

          <div className="row-actions">
            <button type="submit">{editingId ? '保存修改' : '新增型号'}</button>
            {editingId && (
              <button type="button" className="secondary" onClick={() => resetForm(form.category)}>
                取消编辑
              </button>
            )}
          </div>
        </form>

        <div>
          <h3 style={{ marginTop: 0 }}>
            {filterCat ? `${filterCat} · ` : ''}型号列表
          </h3>
          <ListToolbar
            query={query}
            onQueryChange={(q) => {
              setQuery(q)
              sel.clear()
            }}
            placeholder="搜索型号 / 品牌 / PN / 规格…"
            resultText={
              <>
                显示 <strong>{visible.length}</strong>
              </>
            }
            selectedCount={sel.selectedCount}
            onClearSelection={sel.clear}
            batchActions={
              <button
                type="button"
                className="secondary"
                disabled={batchBusy}
                onClick={batchDelete}
              >
                批量删除
              </button>
            }
          />
          <table>
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
                    aria-label="全选"
                  />
                </th>
                <th>资产专业 / 类别</th>
                <th>具体类型</th>
                <th>型号</th>
                <th>规格</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              {visible.map((m) => (
                <tr key={m.id} className={sel.isSelected(m.id) ? 'is-selected' : ''}>
                  <td className="lt-check-col">
                    <input
                      type="checkbox"
                      checked={sel.isSelected(m.id)}
                      onChange={() => sel.toggle(m.id)}
                      aria-label={`选择 ${m.model_name}`}
                    />
                  </td>
                  <td className="muted">{assetScopeLabel(m.asset_category_id ? [m.asset_category_id] : [], assetTree)}</td>
                  <td><span className="badge">{m.category}</span></td>
                  <td>
                    <div>{m.model_name}</div>
                    <div className="muted">
                      {[m.brand, m.pn].filter(Boolean).join(' · ') || '—'}
                    </div>
                  </td>
                  <td className="spec-cell">
                    {formatSpec(m.spec)}
                    {m.category === '内存' && (m.capacity_gb != null || m.ddr_gen) && (
                      <div className="muted">
                        聚合列：{[m.capacity_gb != null ? `${m.capacity_gb}GB` : null, m.ddr_gen]
                          .filter(Boolean)
                          .join(' · ')}
                      </div>
                    )}
                  </td>
                  <td>
                    <div className="row-actions">
                      <button type="button" className="secondary" onClick={() => startEdit(m)}>
                        编辑
                      </button>
                      <button type="button" className="secondary" onClick={() => onDelete(m)}>
                        删除
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {!visible.length && <p className="muted">暂无型号，请在左侧新增或调整搜索。</p>}
        </div>
      </div>
    </div>
  )
}
