import { useEffect, useMemo, useState } from 'react'
import { api } from '../api'
import ListToolbar from '../components/ListToolbar'
import { useSelection } from '../hooks/useSelection'
import { filterByQuery } from '../lib/fuzzy'
import AssetScopePicker from '../components/AssetScopePicker'
import { assetScopeLabel, level2Categories } from '../lib/assetScopes'

const emptyForm = { name: '', contact: '', contact_info: '', remark: '', asset_category_ids: [] }

export default function Suppliers() {
  const [list, setList] = useState([])
  const [form, setForm] = useState(emptyForm)
  const [editingId, setEditingId] = useState(null)
  const [error, setError] = useState('')
  const [ok, setOk] = useState('')
  const [query, setQuery] = useState('')
  const [batchBusy, setBatchBusy] = useState(false)
  const [assetTree, setAssetTree] = useState([])
  const [scopeFilter, setScopeFilter] = useState('')

  async function load() {
    const [rows, tree] = await Promise.all([api.get('/suppliers'), api.get('/asset-categories?tree=true')])
    setList(rows)
    setAssetTree(tree)
  }

  useEffect(() => {
    load().catch((e) => setError(e.message))
  }, [])

  const visible = useMemo(
    () =>
      filterByQuery(scopeFilter ? list.filter((s) => (s.asset_category_ids || []).includes(Number(scopeFilter))) : list, query, (s) => [
        s.name,
        s.contact,
        s.contact_info,
        s.remark,
      ]),
    [list, query, scopeFilter],
  )
  const visibleIds = useMemo(() => visible.map((s) => s.id), [visible])
  const sel = useSelection(visibleIds)

  function resetForm() {
    setEditingId(null)
    setForm(emptyForm)
  }

  function startEdit(s) {
    setEditingId(s.id)
    setForm({
      name: s.name || '',
      contact: s.contact || '',
      contact_info: s.contact_info || '',
      remark: s.remark || '',
      asset_category_ids: [...(s.asset_category_ids || [])],
    })
  }

  async function onSubmit(e) {
    e.preventDefault()
    setError('')
    setOk('')
    const body = {
      name: form.name,
      contact: form.contact || null,
      contact_info: form.contact_info || null,
      remark: form.remark || null,
      asset_category_ids: form.asset_category_ids,
    }
    try {
      if (editingId) {
        await api.put(`/suppliers/${editingId}`, body)
        setOk(`已更新供应商 #${editingId}`)
      } else {
        await api.post('/suppliers', body)
        setOk(`已新增供应商：${form.name}`)
      }
      await load()
      resetForm()
    } catch (err) {
      setError(err.message)
    }
  }

  async function onDelete(s) {
    if (!window.confirm(`确认删除供应商「${s.name}」？已有配件引用的不可删。`)) return
    setError('')
    setOk('')
    try {
      await api.delete(`/suppliers/${s.id}`)
      setOk(`已删除供应商 #${s.id}`)
      await load()
      sel.clear()
    } catch (err) {
      setError(err.message)
    }
  }

  async function batchDelete() {
    const targets = visible.filter((s) => sel.isSelected(s.id))
    if (!targets.length) return
    if (!window.confirm(`尝试删除选中的 ${targets.length} 个供应商？已被引用的将跳过。`)) return
    setBatchBusy(true)
    setError('')
    setOk('')
    let okN = 0
    const errors = []
    for (const s of targets) {
      try {
        await api.delete(`/suppliers/${s.id}`)
        okN += 1
      } catch (e) {
        errors.push(`${s.name}: ${e.message}`)
      }
    }
    await load()
    sel.clear()
    setBatchBusy(false)
    if (errors.length) setError(errors.slice(0, 3).join('；'))
    if (okN) setOk(`已删除 ${okN} 个供应商`)
  }

  return (
    <div className="panel">
      <h2>供应商管理</h2>
      <p className="muted">
        维护入库可选供应商名录。配件上的「供应商」字段引用此处名称；重命名会同步更新已入库配件。
      </p>
      {error && <div className="error">{error}</div>}
      {ok && <div className="ok-msg">{ok}</div>}

      <div className="catalog-scope-filter">
        <span>资产目录</span>
        <select value={scopeFilter} onChange={(e) => { setScopeFilter(e.target.value); sel.clear() }}>
          <option value="">全部专业与类别</option>
          {level2Categories(assetTree).map((item) => <option key={item.id} value={item.id}>{item.domain} / {item.name}</option>)}
        </select>
      </div>

      <div className="split-layout">
        <form onSubmit={onSubmit}>
          <fieldset>
            <legend>{editingId ? `编辑供应商 #${editingId}` : '新增供应商'}</legend>
            <label>
              供应商名称 *
              <input
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                required
                placeholder="如：三星代理商"
              />
            </label>
            <label>
              联系人
              <input
                value={form.contact}
                onChange={(e) => setForm({ ...form, contact: e.target.value })}
              />
            </label>
            <label>
              联系方式
              <input
                value={form.contact_info}
                onChange={(e) => setForm({ ...form, contact_info: e.target.value })}
                placeholder="电话 / 邮箱"
              />
            </label>
            <label>
              备注
              <textarea
                value={form.remark}
                onChange={(e) => setForm({ ...form, remark: e.target.value })}
                rows={2}
              />
            </label>
            <div>
              <div className="muted" style={{ marginBottom: 6 }}>供应资产专业与二级类别（不选 = 通用）</div>
              <AssetScopePicker tree={assetTree} value={form.asset_category_ids} onChange={(ids) => setForm({...form, asset_category_ids: ids})} />
            </div>
            <div className="row-actions">
              <button type="submit">{editingId ? '保存' : '新增'}</button>
              {editingId && (
                <button type="button" className="secondary" onClick={resetForm}>
                  取消
                </button>
              )}
            </div>
          </fieldset>
        </form>

        <div>
          <h3 style={{ marginTop: 0 }}>供应商列表</h3>
          <ListToolbar
            query={query}
            onQueryChange={(q) => {
              setQuery(q)
              sel.clear()
            }}
            placeholder="搜索名称 / 联系人 / 联系方式…"
            resultText={
              <>
                显示 <strong>{visible.length}</strong> / {list.length}
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
                <th>名称</th>
                <th>联系人</th>
                <th>联系方式</th>
                <th>资产专业 / 类别</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              {visible.map((s) => (
                <tr key={s.id} className={sel.isSelected(s.id) ? 'is-selected' : ''}>
                  <td className="lt-check-col">
                    <input
                      type="checkbox"
                      checked={sel.isSelected(s.id)}
                      onChange={() => sel.toggle(s.id)}
                      aria-label={`选择 ${s.name}`}
                    />
                  </td>
                  <td>
                    <strong>{s.name}</strong>
                    {s.remark && <div className="muted">{s.remark}</div>}
                  </td>
                  <td>{s.contact || '—'}</td>
                  <td className="muted">{s.contact_info || '—'}</td>
                  <td className="muted">{assetScopeLabel(s.asset_category_ids, assetTree)}</td>
                  <td>
                    <div className="row-actions">
                      <button type="button" className="secondary" onClick={() => startEdit(s)}>
                        编辑
                      </button>
                      <button type="button" className="secondary" onClick={() => onDelete(s)}>
                        删除
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {!visible.length && (
            <p className="muted">{list.length ? '无匹配供应商' : '暂无供应商，请在左侧新增。'}</p>
          )}
        </div>
      </div>
    </div>
  )
}
