import { useEffect, useMemo, useState } from 'react'
import { api } from '../api'
import ListToolbar from '../components/ListToolbar'
import { useSelection } from '../hooks/useSelection'
import { filterByQuery } from '../lib/fuzzy'

export default function Servers() {
  const [servers, setServers] = useState([])
  const [error, setError] = useState('')
  const [msg, setMsg] = useState('')
  const [query, setQuery] = useState('')
  const [batchBusy, setBatchBusy] = useState(false)

  function load() {
    return api.get('/servers').then(setServers).catch((e) => setError(e.message))
  }

  useEffect(() => {
    load()
  }, [])

  const visible = useMemo(
    () =>
      filterByQuery(servers, query, (s) => [
        s.asset_no,
        s.model,
        s.room,
        s.rack,
        s.u_position,
        s.run_status,
        s.responsible_group,
      ]),
    [servers, query],
  )
  const visibleIds = useMemo(() => visible.map((s) => s.id), [visible])
  const sel = useSelection(visibleIds)

  async function toggle(server) {
    setError('')
    setMsg('')
    const next = server.run_status === '投运' ? '未投运' : '投运'
    try {
      await api.patch(`/servers/${server.id}/run-status`, { run_status: next })
      setMsg(`${server.asset_no} → ${next}`)
      await load()
    } catch (err) {
      setError(err.message)
    }
  }

  async function batchSetStatus(run_status) {
    const targets = visible.filter(
      (s) => sel.isSelected(s.id) && s.run_status !== '退役' && s.run_status !== run_status,
    )
    if (!targets.length) {
      setError(`所选服务器中没有可切换为「${run_status}」的项`)
      return
    }
    if (!window.confirm(`将 ${targets.length} 台服务器设为「${run_status}」？`)) return
    setBatchBusy(true)
    setError('')
    setMsg('')
    let okN = 0
    const errors = []
    for (const s of targets) {
      try {
        await api.patch(`/servers/${s.id}/run-status`, { run_status })
        okN += 1
      } catch (e) {
        errors.push(`${s.asset_no}: ${e.message}`)
      }
    }
    await load()
    sel.clear()
    setBatchBusy(false)
    if (errors.length) setError(errors.slice(0, 3).join('；'))
    if (okN) setMsg(`已更新 ${okN} 台 → ${run_status}`)
  }

  return (
    <div className="panel">
      <h2>服务器</h2>
      <p className="muted">可在「未投运 / 投运」间切换；支持搜索与批量切换。退役不可通过本页设置。</p>
      {error && <div className="error">{error}</div>}
      {msg && <div className="ok-msg">{msg}</div>}

      <ListToolbar
        query={query}
        onQueryChange={(q) => {
          setQuery(q)
          sel.clear()
        }}
        placeholder="搜索资产编号 / 型号 / 机房 / 状态…"
        resultText={
          <>
            显示 <strong>{visible.length}</strong> / {servers.length}
          </>
        }
        selectedCount={sel.selectedCount}
        onClearSelection={sel.clear}
        batchActions={
          <>
            <button type="button" disabled={batchBusy} onClick={() => batchSetStatus('投运')}>
              批量·投运
            </button>
            <button
              type="button"
              className="secondary"
              disabled={batchBusy}
              onClick={() => batchSetStatus('未投运')}
            >
              批量·未投运
            </button>
          </>
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
            <th>资产编号</th>
            <th>型号</th>
            <th>机房/机柜</th>
            <th>运行状态</th>
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
                  aria-label={`选择 ${s.asset_no}`}
                />
              </td>
              <td>{s.asset_no}</td>
              <td>{s.model}</td>
              <td>{s.room} / {s.rack}</td>
              <td>
                <span className={`badge ${s.run_status === '投运' ? 'warn' : 'ok'}`}>
                  {s.run_status}
                </span>
              </td>
              <td>
                {s.run_status !== '退役' && (
                  <button type="button" className="secondary" onClick={() => toggle(s)}>
                    切换为{s.run_status === '投运' ? '未投运' : '投运'}
                  </button>
                )}
              </td>
            </tr>
          ))}
          {!visible.length && (
            <tr>
              <td colSpan={6} className="muted" style={{ textAlign: 'center', padding: '1.5rem' }}>
                无匹配服务器
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  )
}
