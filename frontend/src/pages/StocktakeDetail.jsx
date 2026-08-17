import { useEffect, useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api, getStoredUser } from '../api'
import { OPS_ROLES, hasRole } from '../lib/roles'
import Pagination from '../components/Pagination'
import { usePagination } from '../hooks/usePagination'

function locText(kind, id) {
  if (!kind) return '—'
  return `${kind}#${id ?? '-'}`
}

export default function StocktakeDetail() {
  const { id } = useParams()
  const [st, setSt] = useState(null)
  const [locs, setLocs] = useState([])
  const [error, setError] = useState('')
  const [msg, setMsg] = useState('')
  const [scanNo, setScanNo] = useState('')
  const [actualLocId, setActualLocId] = useState('')
  const [feedback, setFeedback] = useState('')
  const canManage = hasRole(getStoredUser(), OPS_ROLES)
  const items = useMemo(() => st?.items || [], [st])
  const discrepancies = useMemo(() => items.filter((item) => item.discrepancy), [items])
  const itemsPagination = usePagination(items)
  const discrepanciesPagination = usePagination(discrepancies)

  async function load() {
    const [detail, locations] = await Promise.all([
      api.get(`/stocktakes/${id}`),
      api.get('/storage-locations'),
    ])
    setSt(detail)
    setLocs(locations)
    if (!actualLocId && locations[0]) setActualLocId(String(locations[0].id))
  }

  useEffect(() => {
    load().catch((e) => setError(e.message))
  }, [id])

  async function run(fn) {
    setError('')
    setMsg('')
    try {
      await fn()
      await load()
    } catch (e) {
      setError(e.message)
    }
  }

  if (!st) {
    return (
      <div className="panel">
        {error ? <div className="error">{error}</div> : <p className="muted">加载中…</p>}
      </div>
    )
  }

  const summary = st.summary || {}
  const inProgress = st.status === '进行中'

  return (
    <div className="panel">
      <Link to="/stocktakes" className="back-link">返回盘点列表</Link>
      <h2>
        盘点单 #{st.id} <span className="badge">{st.status}</span>
      </h2>
      <p className="muted">
        {st.scope_kind} · 快照 {st.snapshot_at}
      </p>
      {error && <div className="error">{error}</div>}
      {msg && <div className="ok-msg">{msg}</div>}

      <div className="row-actions" style={{ marginBottom: '1rem' }}>
        <span className="badge">待复核 {summary['待复核'] || 0}</span>
        <span className="badge ok">相符 {summary['相符'] || 0}</span>
        <span className="badge danger">盘亏 {summary['盘亏'] || 0}</span>
        <span className="badge warn">盘盈 {summary['盘盈'] || 0}</span>
        <span className="badge warn">错位 {summary['错位'] || 0}</span>
      </div>

      {inProgress && (
        <div className="panel">
          <h3 style={{ marginTop: 0 }}>现场清点</h3>
          <p className="muted">录入固定资产编号；位置相符/错位，或勾选找不到报盘亏；系统查无编号则盘盈。</p>
          <form
            onSubmit={(e) => {
              e.preventDefault()
              const missing = e.nativeEvent.submitter?.name === 'missing'
              run(async () => {
                const body = {
                  scanned_asset_no: scanNo,
                  missing,
                }
                if (!missing) {
                  body.actual_loc_kind = '库位'
                  body.actual_loc_id = Number(actualLocId)
                }
                const item = await api.post(`/stocktakes/${id}/check`, body)
                setMsg(`清点结果：${item.result}${item.scanned_asset_no ? `（${item.scanned_asset_no}）` : ''}`)
                setScanNo('')
              })
            }}
          >
            <label>
              固定资产编号
              <input value={scanNo} onChange={(e) => setScanNo(e.target.value)} required />
            </label>
            <label>
              实际库位（相符/错位/盘盈时）
              <select value={actualLocId} onChange={(e) => setActualLocId(e.target.value)}>
                {locs.map((l) => (
                  <option key={l.id} value={l.id}>
                    {l.warehouse}/{l.slot}
                  </option>
                ))}
              </select>
            </label>
            <div className="row-actions">
              <button type="submit" name="present">按库位清点</button>
              <button type="submit" name="missing" className="secondary">找不到（盘亏）</button>
            </div>
          </form>
        </div>
      )}

      <h3>明细</h3>
      <table>
        <thead>
          <tr>
            <th>资产编号</th>
            <th>冻结位置</th>
            <th>派生应在状态</th>
            <th>结果</th>
            <th>实际/函证</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          {itemsPagination.pageItems.map((item) => (
            <tr key={item.id}>
              <td>{item.fixed_asset_no || item.scanned_asset_no || '—'}</td>
              <td>{locText(item.expected_loc_kind, item.expected_loc_id)}</td>
              <td>{item.expected_status_derived || '—'}</td>
              <td>
                <span className={`badge ${item.result === '盘亏' ? 'danger' : item.result === '相符' ? 'ok' : ''}`}>
                  {item.result}
                </span>
              </td>
              <td>
                {item.requires_external_confirm ? (
                  <span className="muted">
                    函证 {item.feedback_source || '未反馈'}
                  </span>
                ) : (
                  locText(item.actual_loc_kind, item.actual_loc_id)
                )}
              </td>
              <td>
                {inProgress && item.requires_external_confirm && item.result === '待复核' && (
                  <div className="row-actions">
                    <input
                      placeholder="反馈来源"
                      value={feedback}
                      onChange={(e) => setFeedback(e.target.value)}
                      style={{ width: '8rem' }}
                    />
                    <button
                      type="button"
                      onClick={() =>
                        run(async () => {
                          await api.post(`/stocktakes/${id}/confirm-external`, {
                            item_id: item.id,
                            present: true,
                            feedback_source: feedback || '外单位确认在',
                          })
                          setMsg(`函证：在 · 明细#${item.id}`)
                        })
                      }
                    >
                      在
                    </button>
                    <button
                      type="button"
                      className="secondary"
                      onClick={() =>
                        run(async () => {
                          await api.post(`/stocktakes/${id}/confirm-external`, {
                            item_id: item.id,
                            present: false,
                            feedback_source: feedback || '外单位反馈不在',
                          })
                          setMsg(`函证：不在 · 明细#${item.id}`)
                        })
                      }
                    >
                      不在
                    </button>
                  </div>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <Pagination pagination={itemsPagination} />

      <h3>差异清单</h3>
      <table>
        <thead>
          <tr>
            <th>差异ID</th>
            <th>明细ID</th>
            <th>类型</th>
            <th>状态</th>
          </tr>
        </thead>
        <tbody>
          {discrepanciesPagination.pageItems.map((i) => (
              <tr key={i.discrepancy.id}>
                <td>#{i.discrepancy.id}</td>
                <td>#{i.id}</td>
                <td>{i.discrepancy.discrepancy_type}</td>
                <td>
                  <span className={`badge ${i.discrepancy.status === '挂起追查' ? 'danger' : ''}`}>
                    {i.discrepancy.status}
                  </span>
                </td>
              </tr>
            ))}
        </tbody>
      </table>
      <Pagination pagination={discrepanciesPagination} />

      {inProgress && canManage && (
        <div style={{ marginTop: '1rem' }}>
          <button
            type="button"
            onClick={() =>
              run(async () => {
                const done = await api.post(`/stocktakes/${id}/complete`, {})
                setMsg(`已结案：${done.status}`)
              })
            }
          >
            标记已完成
          </button>
          <p className="muted">结案前所有明细不得为「待复核」；只改盘点单状态。</p>
        </div>
      )}
      {inProgress && !canManage && (
        <p className="muted" style={{ marginTop: '1rem' }}>
          结案需主业运维或领导账号。
        </p>
      )}
    </div>
  )
}
