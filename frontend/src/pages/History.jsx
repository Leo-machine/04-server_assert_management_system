import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { api } from '../api'

const EVENT_META = {
  '入库': { icon: '📥', color: '#0f766e' },
  '装机': { icon: '🖥', color: '#0369a1' },
  '拆下': { icon: '🔧', color: '#ca8a04' },
  '借出': { icon: '📤', color: '#c2410c' },
  '归还': { icon: '📥', color: '#0f766e' },
  '调拨': { icon: '🚚', color: '#7c3aed' },
  '报废': { icon: '🗑', color: '#64748b' },
  '校正': { icon: '📝', color: '#475569' },
}

function fmtTime(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')} ${String(d.getHours()).padStart(2,'0')}:${String(d.getMinutes()).padStart(2,'0')}`
}

function locText(kind, id) {
  if (!kind || kind === '无') return '—'
  return `${kind}#${id ?? '-'}`
}

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
      .then(([p, m, r]) => { setPart(p); setMoves(m); setReplay(r) })
      .catch((e) => setError(e.message))
  }, [id])

  return (
    <div>
      <button type="button" className="back-link" onClick={() => nav('/')}>返回配件列表</button>

      {error && <div className="error">{error}</div>}

      {part && (
        <div className="hz-header">
          <div className="hz-header-left">
            <p className="hz-kicker">配件履历</p>
            <h2>{part.fixed_asset_no}</h2>
            <p className="muted">{part.model?.model_name || `型号#${part.model_id}`}</p>
          </div>
          <div className="hz-header-right">
            <span className="badge">{part.current_status}</span>
            {part.current_loc_kind && (
              <span className="muted" style={{ fontSize: '0.85rem' }}>
                当前位置：{locText(part.current_loc_kind, part.current_loc_id)}
              </span>
            )}
          </div>
        </div>
      )}

      {replay && !replay.matches_cache && (
        <div className="error" style={{ marginTop: '0.75rem' }}>
          ⚠ 缓存不一致：履历重放 {replay.current_status}/{replay.current_loc_kind}#{replay.current_loc_id}，
          缓存记录 {part?.current_status}/{part?.current_loc_kind}#{part?.current_loc_id}
        </div>
      )}

      {!moves.length && !error && <p className="muted">暂无履历记录</p>}

      <div className="hz-timeline">
        {moves.map((m, i) => {
          const meta = EVENT_META[m.event_type] || { icon: '●', color: '#94a3b8' }
          const isFirst = i === 0
          return (
            <div key={m.id} className="hz-node-wrap">
              {/* 时间 */}
              <div className="hz-time">{fmtTime(m.occurred_at)}</div>

              {/* 节点 */}
              <div className="hz-node-col">
                <div className="hz-node-dot" style={{ background: meta.color }}>
                  <span>{meta.icon}</span>
                </div>
                {!isFirst && <div className="hz-node-line" />}
              </div>

              {/* 内容卡片 */}
              <div className="hz-card">
                <div className="hz-card-head">
                  <span className="hz-event" style={{ color: meta.color }}>{m.event_type}</span>
                  <span className="hz-operator">操作人 #{m.operator_id}</span>
                </div>

                <div className="hz-flow">
                  <span className={`hz-badge ${m.status_from ? 'hz-badge-from' : 'hz-badge-none'}`}>
                    {m.status_from || '∅'}
                  </span>
                  <span className="hz-arrow">→</span>
                  <span className="hz-badge hz-badge-to">{m.status_to}</span>
                </div>

                {/* 位置变更 */}
                {(m.loc_from_kind || m.loc_to_kind) && (
                  <div className="hz-loc-change">
                    <span className="muted">{locText(m.loc_from_kind, m.loc_from_id)}</span>
                    <span className="hz-arrow muted">→</span>
                    <span className="muted">{locText(m.loc_to_kind, m.loc_to_id)}</span>
                  </div>
                )}

                {/* 附加信息 */}
                <div className="hz-extras">
                  {m.expected_return_date && <span>预期归还：{m.expected_return_date}</span>}
                  {m.approval_id && <span>关联审批 #{m.approval_id}</span>}
                  {m.remark && <span className="hz-remark">「{m.remark}」</span>}
                </div>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
