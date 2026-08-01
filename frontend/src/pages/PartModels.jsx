import { useEffect, useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { api } from '../api'
import ListToolbar from '../components/ListToolbar'
import SpecFields, { formatSpec } from '../components/SpecFields'
import { useSelection } from '../hooks/useSelection'
import { filterByQuery } from '../lib/fuzzy'

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
}

const emptyForm = {
  category: '',
  model_name: '',
  brand: '',
  pn: '',
  spec: {},
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

  const schema = useMemo(
    () => schemas.find((s) => s.category === form.category),
    [schemas, form.category],
  )

  const categories = useMemo(
    () => schemas.map((s) => s.category),
    [schemas],
  )

  const visible = useMemo(() => {
    const byCat = filterCat ? models.filter((m) => m.category === filterCat) : models
    return filterByQuery(byCat, query, (m) => [
      m.category,
      m.model_name,
      m.brand,
      m.pn,
      JSON.stringify(m.spec || {}),
      m.capacity_gb,
      m.ddr_gen,
    ])
  }, [models, filterCat, query])

  const visibleIds = useMemo(() => visible.map((m) => m.id), [visible])
  const sel = useSelection(visibleIds)

  const categoryBrands = useMemo(() => {
    if (!form.category) return brands
    return brands.filter((b) => {
      const cats = b.categories || []
      if (!cats.length) return true
      return cats.includes(form.category)
    })
  }, [brands, form.category])

  async function load() {
    const [cats, ms, brs] = await Promise.all([
      api.get('/categories'),
      api.get('/part-models'),
      api.get('/brands'),
    ])
    setSchemas(cats)
    setModels(ms)
    setBrands(brs)
    setForm((f) => ({
      ...f,
      category: f.category || filterCat || cats[0]?.category || '',
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
    })
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
    })
    setParams({ category: m.category })
    setError('')
    setOk('')
  }

  async function onSubmit(e) {
    e.preventDefault()
    setError('')
    setOk('')
    const body = {
      category: form.category,
      model_name: form.model_name,
      brand: form.brand || null,
      pn: form.pn || null,
      spec: form.spec,
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
      <h2>配件型号管理</h2>
      <p className="muted">
        系统管理员在此维护八类配件型号与规格字段。入库时按类型选择型号，规格随型号带入，确保数据可用、有价值。
      </p>
      {error && <div className="error">{error}</div>}
      {ok && <div className="ok-msg">{ok}</div>}

      <div className="chip-row">
        <button
          type="button"
          className={`chip ${!filterCat ? 'active' : ''}`}
          onClick={() => setParams({})}
        >
          全部
        </button>
        {categories.map((cat) => (
          <button
            key={cat}
            type="button"
            className={`chip ${filterCat === cat ? 'active' : ''}`}
            onClick={() => {
              setParams({ category: cat })
              if (!editingId) {
                setForm((f) => ({
                  ...f,
                  category: cat,
                  brand: '',
                  spec: {},
                }))
              }
            }}
          >
            {cat}
          </button>
        ))}
      </div>

      <div className="split-layout">
        <form className="inbound-form" onSubmit={onSubmit}>
          <fieldset>
            <legend>{editingId ? `编辑型号 #${editingId}` : '新增型号'}</legend>
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
                <th>类型</th>
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
