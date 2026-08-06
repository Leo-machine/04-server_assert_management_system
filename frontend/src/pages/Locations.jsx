import { useEffect, useMemo, useState } from 'react'
import { api, getStoredUser } from '../api'
import { isLeader } from '../lib/roles'
import { ALL_MANAGED_CATEGORIES } from '../lib/categories'

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

  function resetForm() {
    setEditingId(null)
    setForm(emptyForm)
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
    <div className="panel">
      <h2>存放位置管理</h2>
      <p className="muted">
        管理配件的物理存放位置（库房 / 机房 / 数据中心），可按配件类型限制入库范围。
      </p>
      {error && <div className="error">{error}</div>}
      {ok && <div className="ok-msg">{ok}</div>}

      {/* 分布柱状图 */}
      <div className="loc-dist-section">
        <h3>配件分布</h3>
        {distribution.length ? (
          <div className="loc-bars">
            {distribution.map((d) => {
              const pct = Math.round((d.part_count / maxCount) * 100)
              const typeIcon = TYPE_ICONS[d.location_type] || ''
              return (
                <div key={d.id} className="loc-bar-col">
                  <div className="loc-bar-value">{d.part_count}</div>
                  <div className="loc-bar-track">
                    <div className="loc-bar-fill" style={{ height: `${pct}%` }}>
                      {Object.entries(d.parts_by_status || {}).map(([st, n]) => {
                        const spct = d.part_count ? Math.round((n / d.part_count) * 100) : 0
                        return (
                          <div
                            key={st}
                            className="loc-bar-seg"
                            style={{
                              height: `${spct}%`,
                              background: STATUS_COLORS[st] || '#94a3b8',
                            }}
                            title={`${st}: ${n}`}
                          />
                        )
                      })}
                    </div>
                  </div>
                  <div className="loc-bar-label" title={`${d.location_type || '通用'}`}>
                    <span>{typeIcon} {d.warehouse}</span>
                    <span className="muted">{d.slot}</span>
                  </div>
                </div>
              )
            })}
          </div>
        ) : (
          <p className="muted">暂无数据</p>
        )}
        <div className="loc-legend">
          {Object.entries(STATUS_COLORS).map(([st, color]) => (
            <span key={st} className="loc-legend-item">
              <i style={{ background: color }} />
              {st}
            </span>
          ))}
        </div>
      </div>

      <div className="split-layout" style={{ marginTop: '1.25rem' }}>
        {isAdmin ? (
          <form onSubmit={onSubmit}>
            <fieldset>
              <legend>{editingId ? `编辑 #${editingId}` : '新增存放位置'}</legend>
              <label>
                区域 *
                <input
                  value={form.warehouse}
                  onChange={(e) => setForm({ ...form, warehouse: e.target.value })}
                  required
                  placeholder="如：一号库房 / A栋数据中心"
                />
              </label>
              <label>
                位置 *
                <input
                  value={form.slot}
                  onChange={(e) => setForm({ ...form, slot: e.target.value })}
                  required
                  placeholder="如：A-01 / Rack-B-03"
                />
              </label>
              <label>
                位置类型
                <select
                  value={form.location_type}
                  onChange={(e) => setForm({ ...form, location_type: e.target.value })}
                >
                  <option value="">— 通用（不区分） —</option>
                  {LOCATION_TYPES.map((t) => (
                    <option key={t} value={t}>{TYPE_ICONS[t]} {t}</option>
                  ))}
                </select>
              </label>
              <div>
                <div className="muted" style={{ marginBottom: 6 }}>
                  允许入库的配件类型（不选 = 通用，所有类型可入）
                </div>
                <div className="chip-row" style={{ margin: '0 0 0.5rem' }}>
                  {ALL_MANAGED_CATEGORIES.map((cat) => (
                    <button
                      key={cat}
                      type="button"
                      className={`chip ${form.allowed_categories.includes(cat) ? 'active' : ''}`}
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
        ) : (
          <p className="muted">库位增删改仅领导可操作；下方为只读列表与分布。</p>
        )}

        <div>
          <h3 style={{ marginTop: 0 }}>位置列表（{locations.length}）</h3>
          <table>
            <thead>
              <tr>
                <th>区域</th>
                <th>位置</th>
                <th>类型</th>
                <th>允许配件</th>
                <th>存放数</th>
                {isAdmin && <th>操作</th>}
              </tr>
            </thead>
            <tbody>
              {locations.map((loc) => (
                <tr key={loc.id}>
                  <td><strong>{loc.warehouse}</strong></td>
                  <td>{loc.slot}</td>
                  <td>
                    <span className="badge">
                      {TYPE_ICONS[loc.location_type] || ''} {loc.location_type || '通用'}
                    </span>
                  </td>
                  <td className="muted">
                    {loc.allowed_categories?.length ? loc.allowed_categories.join('、') : '通用'}
                  </td>
                  <td><span className="badge ok">{loc.part_count || 0}</span></td>
                  {isAdmin && (
                    <td>
                      <div className="row-actions">
                        <button type="button" className="secondary" onClick={() => startEdit(loc)}>
                          编辑
                        </button>
                        <button
                          type="button"
                          className="secondary"
                          disabled={(loc.part_count || 0) > 0}
                          onClick={() => onDelete(loc)}
                        >
                          删除
                        </button>
                      </div>
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
