import { useEffect, useState } from 'react'
import { api, getOperatorId } from '../api'

export default function Approvals() {
  const [list, setList] = useState([])
  const [error, setError] = useState('')
  const [msg, setMsg] = useState('')
  const operatorId = getOperatorId()

  function load() {
    return api.get('/approvals').then(setList).catch((e) => setError(e.message))
  }

  useEffect(() => {
    load()
  }, [])

  async function decide(approval, approve) {
    setError('')
    setMsg('')
    try {
      await api.post(`/approvals/${approval.id}/decide`, {
        level: approval.current_level,
        approve,
        opinion: approve ? '同意' : '驳回',
      })
      setMsg(approve ? `审批单 #${approval.id} 已通过本级` : `审批单 #${approval.id} 已驳回`)
      await load()
    } catch (err) {
      setError(err.message)
    }
  }

  return (
    <div className="panel">
      <h2>审批中心</h2>
      <p className="muted">
        当前操作人 ID={operatorId}。只有本级指定审批人用对应身份切换后才能点通过/驳回。
      </p>
      {error && <div className="error">{error}</div>}
      {msg && <div className="ok-msg">{msg}</div>}
      {list.map((a) => {
        const currentStep = a.steps.find((s) => s.level === a.current_level)
        const canDecide =
          a.overall_status === '审批中' &&
          currentStep &&
          currentStep.approver_id === operatorId
        return (
          <div key={a.id} className="panel" style={{ marginTop: '0.75rem' }}>
            <strong>#{a.id}</strong> 借出 · 配件 #{a.part_id} · {a.overall_status}
            <div className="muted">
              申请人 {a.applicant?.name} · 外单位 {a.dest_org?.org_name} · 预期归还{' '}
              {a.expected_return_date} · 当前第 {a.current_level} 级
            </div>
            <ul className="timeline">
              {a.steps.map((s) => (
                <li key={s.id}>
                  L{s.level} {s.approver?.name} — {s.step_status}
                  {s.opinion ? `（${s.opinion}）` : ''}
                </li>
              ))}
            </ul>
            {canDecide && (
              <div className="row-actions">
                <button type="button" onClick={() => decide(a, true)}>通过</button>
                <button type="button" className="secondary" onClick={() => decide(a, false)}>
                  驳回
                </button>
              </div>
            )}
          </div>
        )
      })}
      {!list.length && <p className="muted">暂无审批单</p>}
    </div>
  )
}
