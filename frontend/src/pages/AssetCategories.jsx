import { useEffect, useMemo, useState } from 'react'
import { api } from '../api'
import { PART_CATEGORIES } from '../lib/categories'

const emptyForm = {
  name: '',
  code: '',
  parent_id: '',
  sort_order: 0,
  enabled: true,
  business_category: '',
}

export default function AssetCategories() {
  const [rows, setRows] = useState([])
  const [form, setForm] = useState(emptyForm)
  const [editingId, setEditingId] = useState(null)
  const [expandedIds, setExpandedIds] = useState(null)
  const [error, setError] = useState('')
  const [ok, setOk] = useState('')

  const byParent = useMemo(() => {
    const map = new Map()
    for (const row of rows) {
      const key = row.parent_id || 0
      if (!map.has(key)) map.set(key, [])
      map.get(key).push(row)
    }
    return map
  }, [rows])

  const parentOptions = useMemo(
    () => rows.filter((row) => row.level < 3 && row.id !== editingId),
    [rows, editingId],
  )
  const selectedParent = rows.find((row) => String(row.id) === String(form.parent_id))
  const targetLevel = selectedParent ? selectedParent.level + 1 : 1

  async function load() {
    const data = await api.get('/asset-categories')
    setRows(data)
    setExpandedIds((current) => current ?? new Set(data.filter((row) => row.level < 3).map((row) => row.id)))
  }

  useEffect(() => {
    load().catch((e) => setError(e.message))
  }, [])

  function reset() {
    setEditingId(null)
    setForm(emptyForm)
  }

  function startEdit(row) {
    setEditingId(row.id)
    setForm({
      name: row.name,
      code: row.code || '',
      parent_id: row.parent_id ? String(row.parent_id) : '',
      sort_order: row.sort_order || 0,
      enabled: row.enabled,
      business_category: row.business_category || '',
    })
    setError('')
    setOk('')
  }

  function startAddChild(row) {
    if (row.level >= 3) return
    setEditingId(null)
    setForm({
      ...emptyForm,
      parent_id: String(row.id),
      sort_order: ((byParent.get(row.id)?.length || 0) + 1) * 10,
    })
    setExpandedIds((current) => new Set([...(current || []), row.id]))
    setError('')
    setOk(`将在「${row.name}」下新增${row.level + 1}级类别`)
  }

  async function onSubmit(e) {
    e.preventDefault()
    setError('')
    setOk('')
    const body = {
      ...form,
      parent_id: form.parent_id ? Number(form.parent_id) : null,
      sort_order: Number(form.sort_order) || 0,
      code: form.code || null,
      business_category: targetLevel === 3 ? (form.business_category || null) : null,
    }
    try {
      if (editingId) {
        await api.put(`/asset-categories/${editingId}`, body)
        setOk(`已更新资产类别「${body.name}」`)
      } else {
        await api.post('/asset-categories', body)
        setOk(`已新增${targetLevel}级资产类别「${body.name}」`)
      }
      reset()
      await load()
    } catch (err) {
      setError(err.message)
    }
  }

  async function onDelete(row) {
    if (!window.confirm(`确认删除资产类别「${row.name}」？`)) return
    setError('')
    setOk('')
    try {
      await api.delete(`/asset-categories/${row.id}`)
      if (editingId === row.id) reset()
      setOk(`已删除「${row.name}」`)
      await load()
    } catch (err) {
      setError(err.message)
    }
  }

  function toggleNode(id) {
    setExpandedIds((current) => {
      const next = new Set(current || [])
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  function setAllExpanded(expanded) {
    setExpandedIds(new Set(expanded ? rows.filter((row) => row.level < 3).map((row) => row.id) : []))
  }

  function renderNode(row) {
    const children = byParent.get(row.id) || []
    const hasChildren = children.length > 0
    const isExpanded = expandedIds?.has(row.id)
    return (
      <div className={`ac-node ac-level-${row.level}`} key={row.id}>
        <div className="ac-node-main">
          {hasChildren ? (
            <button type="button" className={`ac-expand-btn ${isExpanded ? 'is-open' : ''}`} onClick={() => toggleNode(row.id)} aria-label={isExpanded ? `收起${row.name}` : `展开${row.name}`} aria-expanded={isExpanded}>›</button>
          ) : <span className="ac-expand-placeholder" />}
          <span className="ac-level-badge">L{row.level}</span>
          <span className="ac-node-copy">
            <strong>{row.name}</strong>
            <small>{row.code || '未设置编码'}</small>
          </span>
          {row.business_category ? (
            <span className="ac-state is-ready">已接入库</span>
          ) : row.level === 3 ? (
            <span className="ac-state">待扩展</span>
          ) : null}
          {!row.enabled && <span className="ac-state is-off">已停用</span>}
          <span className="ac-node-actions">
            {row.level < 3 && <button type="button" className="secondary ac-add-child" onClick={() => startAddChild(row)}>＋ 新增下级</button>}
            <button type="button" className="secondary" onClick={() => startEdit(row)}>编辑</button>
            <button type="button" className="secondary danger-outline" onClick={() => onDelete(row)}>删除</button>
          </span>
        </div>
        {hasChildren && isExpanded && <div className="ac-children">{children.map(renderNode)}</div>}
      </div>
    )
  }

  return (
    <div className="panel ac-page">
      <div className="ac-header">
        <div>
          <h2>资产类别管理</h2>
          <p className="muted">统一管理专业域、资产大类和具体类别；三级类别可逐步关联已落地的入库能力。</p>
        </div>
        <div className="ac-summary">
          <strong>{rows.length}</strong><span>个目录节点</span>
        </div>
      </div>
      {error && <div className="error">{error}</div>}
      {ok && <div className="ok-msg">{ok}</div>}

      <div className="ac-layout">
        <section className="ac-tree" aria-label="资产类别目录">
          <div className="ac-section-head">
            <h3>三级目录</h3>
            <span className="ac-tree-controls">
              <button type="button" className="linkish" onClick={() => setAllExpanded(true)}>全部展开</button>
              <i />
              <button type="button" className="linkish" onClick={() => setAllExpanded(false)}>全部收起</button>
            </span>
          </div>
          {(byParent.get(0) || []).map(renderNode)}
        </section>

        <form className="ac-form" onSubmit={onSubmit}>
          <div className="ac-section-head"><h3>{editingId ? '编辑类别' : '新增类别'}</h3><span className="ac-target-level">L{targetLevel}</span></div>
          {!editingId && selectedParent && <div className="ac-parent-tip"><span>新增位置</span><strong>{selectedParent.name}</strong><i>›</i><b>L{targetLevel}</b></div>}
          <label>上级目录
            <select value={form.parent_id} onChange={(e) => setForm({...form, parent_id: e.target.value, business_category: ''})}>
              <option value="">无（新增一级目录）</option>
              {parentOptions.map((row) => <option key={row.id} value={row.id}>{'　'.repeat(row.level - 1)}L{row.level} · {row.name}</option>)}
            </select>
          </label>
          <label>类别名称 *
            <input required value={form.name} onChange={(e) => setForm({...form, name: e.target.value})} placeholder="如：保护设备类" />
          </label>
          <div className="ac-auto-code">
            <span>类别编码</span>
            <strong>{editingId && form.code ? form.code : '保存后由系统自动生成'}</strong>
            <small>编码根据上级目录自动递增，无需手工填写</small>
          </div>
          <label>排序值
            <input type="number" value={form.sort_order} onChange={(e) => setForm({...form, sort_order: e.target.value})} />
          </label>
          {targetLevel === 3 && (
            <label>关联已落地入库品类
              <select value={form.business_category} onChange={(e) => setForm({...form, business_category: e.target.value})}>
                <option value="">暂不关联（待扩展）</option>
                {PART_CATEGORIES.map((cat) => <option key={cat} value={cat}>{cat}</option>)}
              </select>
            </label>
          )}
          <label className="ac-enable-setting">
            <span className="ac-enable-copy"><strong>启用该类别</strong><small>启用后可在设备管理、型号管理和入库中选择；停用后保留历史数据但不再提供选择。</small></span>
            <input type="checkbox" checked={form.enabled} onChange={(e) => setForm({...form, enabled: e.target.checked})} />
            <i aria-hidden="true" />
          </label>
          <div className="row-actions">
            <button type="submit">{editingId ? '保存修改' : '新增类别'}</button>
            {editingId && <button type="button" className="secondary" onClick={reset}>取消</button>}
          </div>
        </form>
      </div>
    </div>
  )
}
