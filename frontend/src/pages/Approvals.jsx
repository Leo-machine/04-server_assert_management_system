import { useEffect, useMemo, useState } from 'react'
import { api, getOperatorId } from '../api'
import ListToolbar from '../components/ListToolbar'
import { filterByQuery } from '../lib/fuzzy'

function statusClass(s) {
  if (s === '审批中') return 'ap-status-pending'
  if (s === '通过') return 'ap-status-approved'
  if (s === '驳回') return 'ap-status-rejected'
  if (s === '撤回') return 'ap-status-withdrawn'
  return ''
}

function stepDot(s) {
  if (s === '通过') return 'ap-step-ok'
  if (s === '驳回') return 'ap-step-no'
  if (s === '待审') return 'ap-step-wait'
  return 'ap-step-wait'
}

export default function Approvals() {
  const [list, setList] = useState([])
  const [error, setError] = useState('')
  const [msg, setMsg] = useState('')
  const [query, setQuery] = useState('')
  const operatorId = getOperatorId()

  function load() {
    return api.get('/approvals').then(setList).catch((e) => setError(e.message))
  }

  useEffect(() => { load() }, [])

  const visible = useMemo(() =>
    filterByQuery(list, query, (a) => [
      String(a.id), a.action_type, a.overall_status, String(a.part_id),
      a.applicant?.name, a.dest_org?.org_name, a.reason_code, a.expected_return_date,
      ...(a.steps || []).flatMap((s) => [s.approver?.name, s.step_status, s.opinion]),
    ]),
  [list, query])

  async function decide(approval, approve) {
    setError(''); setMsg('')
    try {
      await api.post(`/approvals/${approval.id}/decide`, { level: approval.current_level, approve, opinion: approve ? '同意' : '驳回' })
      setMsg(approve ? `#${approval.id} 已通过本级` : `#${approval.id} 已驳回`)
      await load()
    } catch (err) { setError(err.message) }
  }

  async function withdraw(approval) {
    setError(''); setMsg('')
    try {
      await api.post(`/approvals/${approval.id}/withdraw`)
      setMsg(`#${approval.id} 已撤回`); await load()
    } catch (err) { setError(err.message) }
  }

  return (
    <div className="panel">
      <h2>审批中心</h2>
      <p className="muted">本级审批人可审批对应级别的单据；申请人可撤回审批中的单据。</p>
      {error && <div className="error">{error}</div>}
      {msg && <div className="ok-msg">{msg}</div>}

      <ListToolbar query={query} onQueryChange={setQuery}
        placeholder="搜索单号 / 类型 / 状态 / 申请人…"
        resultText={<span>共 <strong>{list.length}</strong> 单，显示 <strong>{visible.length}</strong></span>}
      />

      {visible.map((a) => {
        const currentStep = a.steps.find((s) => s.level === a.current_level)
        const canDecide = a.overall_status === '审批中' && currentStep?.approver_id === operatorId
        const canWithdraw = a.overall_status === '审批中' && a.applicant_id === operatorId

        return (
          <div key={a.id} className="ap-card">
            {/* 头部 */}
            <div className="ap-card-header">
              <div className="ap-card-title">
                <span className="ap-id">#{a.id}</span>
                <span className="ap-type">{a.action_type}</span>
                <span className={`ap-status ${statusClass(a.overall_status)}`}>{a.overall_status}</span>
              </div>
              <div className="ap-card-meta">
                <span>配件 #{a.part_id}</span>
                <span>申请人：{a.applicant?.name}</span>
                {a.dest_org?.org_name && <span>外单位：{a.dest_org.org_name}</span>}
                {a.reason_code && <span>缘由：{a.reason_code}</span>}
                {a.expected_return_date && <span>预期归还：{a.expected_return_date}</span>}
              </div>
            </div>

            {/* 审批步骤条 */}
            <div className="ap-steps">
              {a.steps.map((s, i) => (
                <div key={s.id} className="ap-step-wrap">
                  <div className={`ap-step-dot ${stepDot(s.step_status)} ${s.level === a.current_level && a.overall_status === '审批中' ? 'ap-step-current' : ''}`}>
                    {s.step_status === '通过' ? '✓' : s.step_status === '驳回' ? '✗' : s.level}
                  </div>
                  <div className="ap-step-label">{s.approver?.name || `L${s.level}`}</div>
                  <div className="ap-step-status">{s.step_status}</div>
                  {s.opinion && <div className="ap-step-opinion">「{s.opinion}」</div>}
                  {i < a.steps.length - 1 && <div className={`ap-step-line ${s.step_status === '通过' ? 'is-done' : ''}`} />}
                </div>
              ))}
            </div>

            {/* 操作区 */}
            {(canDecide || canWithdraw) && (
              <div className="ap-actions">
                {canDecide && (
                  <>
                    <button type="button" className="ap-btn-approve" onClick={() => decide(a, true)}>✓ 通过</button>
                    <button type="button" className="ap-btn-reject" onClick={() => decide(a, false)}>✗ 驳回</button>
                  </>
                )}
                {canWithdraw && (
                  <button type="button" className="ap-btn-withdraw" onClick={() => withdraw(a)}>撤回</button>
                )}
              </div>
            )}
          </div>
        )
      })}
      {!visible.length && <p className="muted">{list.length ? '无匹配审批单' : '暂无审批单'}</p>}
    </div>
  )
}
