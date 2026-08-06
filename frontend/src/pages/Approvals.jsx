import { useEffect, useMemo, useState } from 'react'
import { api, getOperatorId, getStoredUser } from '../api'
import { isLeader as userIsLeader } from '../lib/roles'
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
  const [tab, setTab] = useState('biz') // biz=业务审批 reg=注册审批
  const [regs, setRegs] = useState([])
  const operatorId = getOperatorId()
  const isLeader = userIsLeader(getStoredUser())

  function load() {
    return api.get('/approvals').then(setList).catch((e) => setError(e.message))
  }

  function loadRegs() {
    return api.get('/auth/registrations').then(setRegs).catch((e) => setError(e.message))
  }

  useEffect(() => { load() }, [])
  useEffect(() => {
    if (tab === 'reg' && isLeader) loadRegs()
  }, [tab, isLeader])

  async function approveReg(u) {
    if (!window.confirm(`通过 ${u.name}（${u.username}）的注册？角色将设为「${u.applied_role}」。`)) return
    setError(''); setMsg('')
    try {
      await api.post(`/auth/registrations/${u.id}/approve`)
      setMsg(`已通过 ${u.name}（${u.username}）的注册，角色：${u.applied_role}`)
      await loadRegs()
    } catch (e) { setError(e.message) }
  }

  async function rejectReg(u) {
    const reason = window.prompt(`驳回 ${u.name}（${u.username}）的注册申请，请填写理由：`)
    if (reason === null) return
    if (!reason.trim()) { setError('驳回必须填写理由'); return }
    setError(''); setMsg('')
    try {
      await api.post(`/auth/registrations/${u.id}/reject`, { reason: reason.trim() })
      setMsg(`已驳回 ${u.name} 的注册申请`)
      await loadRegs()
    } catch (e) { setError(e.message) }
  }

  const visible = useMemo(() =>
    filterByQuery(list, query, (a) => [
      String(a.id), a.action_type, a.overall_status, String(a.part_id),
      a.applicant?.name, a.dest_org?.org_name, a.reason_code, a.expected_return_date,
      ...(a.steps || []).flatMap((s) => [s.approver?.name, s.step_status, s.opinion]),
    ]),
  [list, query])

  async function decide(approval, approve) {
    let opinion = approve ? '同意' : ''
    if (approve) {
      if (!window.confirm(`确认通过审批单 #${approval.id} 第 ${approval.current_level} 级？`)) return
    } else {
      const reason = window.prompt(`驳回审批单 #${approval.id}，请填写意见：`)
      if (reason === null) return
      if (!reason.trim()) { setError('驳回必须填写意见'); return }
      opinion = reason.trim()
    }
    setError(''); setMsg('')
    try {
      await api.post(`/approvals/${approval.id}/decide`, {
        level: approval.current_level,
        approve,
        opinion,
      })
      setMsg(approve ? `#${approval.id} 已通过本级` : `#${approval.id} 已驳回`)
      await load()
    } catch (err) { setError(err.message) }
  }

  async function withdraw(approval) {
    if (!window.confirm(`确认撤回审批单 #${approval.id}？`)) return
    setError(''); setMsg('')
    try {
      await api.post(`/approvals/${approval.id}/withdraw`)
      setMsg(`#${approval.id} 已撤回`); await load()
    } catch (err) { setError(err.message) }
  }

  return (
    <div className="panel">
      <h2>审批中心</h2>
      <p className="muted">仅领导可审批；主业/外委可发起与撤回本人单据。</p>

      <div className="pl-filters" style={{ marginBottom: '0.75rem' }}>
        <button type="button" className={`pl-pill ${tab === 'biz' ? 'is-on' : ''}`} onClick={() => setTab('biz')}>
          业务审批
        </button>
        {isLeader && (
          <button type="button" className={`pl-pill ${tab === 'reg' ? 'is-on' : ''}`} onClick={() => setTab('reg')}>
            注册审批
          </button>
        )}
      </div>

      {error && <div className="error">{error}</div>}
      {msg && <div className="ok-msg">{msg}</div>}

      {tab === 'reg' && isLeader && (
        <table>
          <thead>
            <tr>
              <th>姓名</th>
              <th>用户名</th>
              <th>申请角色</th>
              <th>申请理由</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            {regs.map((u) => (
              <tr key={u.id}>
                <td>{u.name}</td>
                <td>{u.username}</td>
                <td><span className="badge warn">{u.applied_role}</span></td>
                <td>{u.apply_reason}</td>
                <td>
                  <div className="row-actions">
                    <button type="button" onClick={() => approveReg(u)}>✓ 通过</button>
                    <button type="button" className="secondary" onClick={() => rejectReg(u)}>✗ 驳回</button>
                  </div>
                </td>
              </tr>
            ))}
            {!regs.length && (
              <tr><td colSpan={5} className="muted" style={{ textAlign: 'center', padding: '1.5rem' }}>暂无待审核的注册申请</td></tr>
            )}
          </tbody>
        </table>
      )}

      {tab === 'biz' && <ListToolbar query={query} onQueryChange={setQuery}
        placeholder="搜索单号 / 类型 / 状态 / 申请人…"
        resultText={<span>共 <strong>{list.length}</strong> 单，显示 <strong>{visible.length}</strong></span>}
      />}

      {tab === 'biz' && visible.map((a) => {
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
      {tab === 'biz' && !visible.length && <p className="muted">{list.length ? '无匹配审批单' : '暂无审批单'}</p>}
    </div>
  )
}
