import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { api } from '../api'

export default function History() {
  const { id } = useParams()
  const nav = useNavigate()
  const [part, setPart] = useState(null)
  const [moves, setMoves] = useState([])
  const [replay, setReplay] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    Promise.all([
      api.get(`/parts/${id}`),
      api.get(`/parts/${id}/movements`),
      api.get(`/parts/${id}/projected-from-log`),
    ])
      .then(([p, m, r]) => {
        setPart(p)
        setMoves(m)
        setReplay(r)
      })
      .catch((e) => setError(e.message))
  }, [id])

  return (
    <div className="panel">
      <button type="button" className="back-link" onClick={() => nav('/')}>
        返回配件列表
      </button>
      <h2>配件履历</h2>
      {part && (
        <p className="muted">
          {part.fixed_asset_no} · 缓存状态 {part.current_status} / {part.current_loc_kind}#
          {part.current_loc_id}
        </p>
      )}
      {replay && (
        <p className={replay.matches_cache ? 'muted' : 'error'}>
          履历重放：{replay.current_status} / {replay.current_loc_kind}#{replay.current_loc_id}
          {replay.matches_cache ? '（与缓存一致）' : '（与缓存不一致！）'}
        </p>
      )}
      {error && <div className="error">{error}</div>}
      <ul className="timeline">
        {moves.map((m) => (
          <li key={m.id}>
            <strong>{m.event_type}</strong> {m.status_from || '∅'} → {m.status_to}
            <div className="muted">
              {m.occurred_at} · 操作人#{m.operator_id}
              {m.loc_from_kind || m.loc_to_kind
                ? ` · ${m.loc_from_kind || '∅'}#${m.loc_from_id ?? '-'} → ${m.loc_to_kind || '∅'}#${m.loc_to_id ?? '-'}`
                : ''}
              {m.approval_id ? ` · 审批#${m.approval_id}` : ''}
              {m.expected_return_date ? ` · 预期归还 ${m.expected_return_date}` : ''}
              {m.remark ? ` · ${m.remark}` : ''}
            </div>
          </li>
        ))}
      </ul>
    </div>
  )
}
