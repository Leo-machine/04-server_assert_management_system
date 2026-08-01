import { useEffect, useMemo, useState } from 'react'
import { api } from '../api'
import ListToolbar from '../components/ListToolbar'
import { useSelection } from '../hooks/useSelection'
import { filterByQuery } from '../lib/fuzzy'

const ALL_CATEGORIES = [
  '内存',
  '机械硬盘',
  '固态硬盘',
  'RAID卡',
  '光模块',
  '网卡',
  'HBA卡',
  '算力卡',
]

const emptyForm = { name: '', categories: [] }

function catsLabel(cats) {
  if (!cats || !cats.length) return '通用（全部类型）'
  return cats.join('、')
}

function BrandTable({ rows, sel, onEdit, onDelete, showSelectAll = true }) {
  return (
    <table>
      <thead>
        <tr>
          <th className="lt-check-col">
            {showSelectAll ? (
              <input
                type="checkbox"
                checked={sel.allVisibleSelected}
                ref={(el) => {
                  if (el) el.indeterminate = sel.someVisibleSelected
                }}
                onChange={sel.toggleAllVisible}
                aria-label="全选"
              />
            ) : null}
          </th>
          <th>品牌名称</th>
          <th>适用类型</th>
          <th>操作</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((b) => (
          <tr key={b.id} className={sel.isSelected(b.id) ? 'is-selected' : ''}>
            <td className="lt-check-col">
              <input
                type="checkbox"
                checked={sel.isSelected(b.id)}
                onChange={() => sel.toggle(b.id)}
                aria-label={`选择 ${b.name}`}
              />
            </td>
            <td><strong>{b.name}</strong></td>
            <td className="muted">{catsLabel(b.categories)}</td>
            <td>
              <div className="row-actions">
                <button type="button" className="secondary" onClick={() => onEdit(b)}>
                  编辑
                </button>
                <button type="button" className="secondary" onClick={() => onDelete(b)}>
                  删除
                </button>
              </div>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

export default function Brands() {
  const [brands, setBrands] = useState([])
  const [filterCat, setFilterCat] = useState('')
  const [form, setForm] = useState(emptyForm)
  const [editingId, setEditingId] = useState(null)
  const [error, setError] = useState('')
  const [ok, setOk] = useState('')
  const [query, setQuery] = useState('')
  const [batchBusy, setBatchBusy] = useState(false)

  async function load() {
    const q = filterCat ? `?category=${encodeURIComponent(filterCat)}` : ''
    const list = await api.get(`/brands${q}`)
    setBrands(list)
  }

  useEffect(() => {
    load().catch((e) => setError(e.message))
  }, [filterCat])

  const filtered = useMemo(
    () =>
      filterByQuery(brands, query, (b) => [
        b.name,
        ...(b.categories || []),
        catsLabel(b.categories),
      ]),
    [brands, query],
  )

  const visibleIds = useMemo(() => filtered.map((b) => b.id), [filtered])
  const sel = useSelection(visibleIds)

  const grouped = useMemo(() => {
    if (filterCat || query) return null
    const map = {}
    for (const cat of ALL_CATEGORIES) map[cat] = []
    map['通用'] = []
    for (const b of filtered) {
      const cats = b.categories || []
      if (!cats.length) {
        map['通用'].push(b)
        continue
      }
      for (const c of cats) {
        if (!map[c]) map[c] = []
        map[c].push(b)
      }
    }
    return map
  }, [filtered, filterCat, query])

  function resetForm() {
    setEditingId(null)
    setForm(emptyForm)
  }

  function toggleCat(cat) {
    setForm((f) => {
      const has = f.categories.includes(cat)
      return {
        ...f,
        categories: has
          ? f.categories.filter((c) => c !== cat)
          : [...f.categories, cat],
      }
    })
  }

  function startEdit(b) {
    setEditingId(b.id)
    setForm({ name: b.name, categories: [...(b.categories || [])] })
  }

  async function onSubmit(e) {
    e.preventDefault()
    setError('')
    setOk('')
    const body = { name: form.name, categories: form.categories }
    try {
      if (editingId) {
        await api.put(`/brands/${editingId}`, body)
        setOk(`已更新品牌 #${editingId}`)
      } else {
        await api.post('/brands', body)
        setOk(`已新增品牌：${form.name}`)
      }
      await load()
      resetForm()
    } catch (err) {
      setError(err.message)
    }
  }

  async function onDelete(b) {
    if (!window.confirm(`确认删除品牌「${b.name}」？已有型号引用的品牌不可删。`)) return
    setError('')
    setOk('')
    try {
      await api.delete(`/brands/${b.id}`)
      setOk(`已删除品牌 #${b.id}`)
      await load()
      sel.clear()
    } catch (err) {
      setError(err.message)
    }
  }

  async function batchDelete() {
    const targets = filtered.filter((b) => sel.isSelected(b.id))
    if (!targets.length) return
    if (!window.confirm(`尝试删除选中的 ${targets.length} 个品牌？已被引用的将失败跳过。`)) return
    setBatchBusy(true)
    setError('')
    setOk('')
    let okN = 0
    const errors = []
    for (const b of targets) {
      try {
        await api.delete(`/brands/${b.id}`)
        okN += 1
      } catch (e) {
        errors.push(`${b.name}: ${e.message}`)
      }
    }
    await load()
    sel.clear()
    setBatchBusy(false)
    if (errors.length) setError(errors.slice(0, 3).join('；'))
    if (okN) setOk(`已删除 ${okN} 个品牌`)
  }

  return (
    <div className="panel">
      <h2>品牌管理</h2>
      <p className="muted">
        按配件类型归类品牌。支持模糊搜索与批量删除（有型号引用的不可删）。
      </p>
      {error && <div className="error">{error}</div>}
      {ok && <div className="ok-msg">{ok}</div>}

      <div className="chip-row">
        <button
          type="button"
          className={`chip ${!filterCat ? 'active' : ''}`}
          onClick={() => {
            setFilterCat('')
            sel.clear()
          }}
        >
          全部 / 分组
        </button>
        {ALL_CATEGORIES.map((cat) => (
          <button
            key={cat}
            type="button"
            className={`chip ${filterCat === cat ? 'active' : ''}`}
            onClick={() => {
              setFilterCat(cat)
              sel.clear()
            }}
          >
            {cat}
          </button>
        ))}
      </div>

      <div className="split-layout">
        <form onSubmit={onSubmit}>
          <fieldset>
            <legend>{editingId ? `编辑品牌 #${editingId}` : '新增品牌'}</legend>
            <label>
              品牌名称 *
              <input
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                required
                placeholder="如：华为、NVIDIA、三星"
              />
            </label>
            <div>
              <div className="muted" style={{ marginBottom: 6 }}>
                适用配件类型（不选 = 通用，各类型可选）
              </div>
              <div className="chip-row">
                {ALL_CATEGORIES.map((cat) => (
                  <button
                    key={cat}
                    type="button"
                    className={`chip ${form.categories.includes(cat) ? 'active' : ''}`}
                    onClick={() => toggleCat(cat)}
                  >
                    {cat}
                  </button>
                ))}
              </div>
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
          <h3 style={{ marginTop: 0 }}>
            {filterCat ? `${filterCat} · 可用品牌` : '品牌列表'}
          </h3>
          <ListToolbar
            query={query}
            onQueryChange={(q) => {
              setQuery(q)
              sel.clear()
            }}
            placeholder="搜索品牌名 / 适用类型…"
            resultText={
              <>
                显示 <strong>{filtered.length}</strong>
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

          {filterCat || query ? (
            <>
              <BrandTable
                rows={filtered}
                sel={sel}
                onEdit={startEdit}
                onDelete={onDelete}
              />
              {!filtered.length && <p className="muted">无匹配品牌</p>}
            </>
          ) : (
            ALL_CATEGORIES.concat(['通用']).map((cat) => {
              const list = grouped?.[cat] || []
              if (!list.length) return null
              return (
                <div key={cat} style={{ marginBottom: '1.25rem' }}>
                  <h4 style={{ margin: '0 0 0.5rem', color: '#003e7e' }}>{cat}</h4>
                  <BrandTable
                    rows={list}
                    sel={sel}
                    onEdit={startEdit}
                    onDelete={onDelete}
                    showSelectAll={false}
                  />
                </div>
              )
            })
          )}
          {!brands.length && <p className="muted">暂无品牌，请在左侧新增。</p>}
        </div>
      </div>
    </div>
  )
}
