import { useEffect, useMemo, useState } from 'react'
import { api, getOperatorId, getStoredUser } from '../api'
import { isLeader as userIsLeader, isSuperAdmin } from '../lib/roles'
import ListToolbar from '../components/ListToolbar'
import { filterByQuery } from '../lib/fuzzy'
import Pagination from '../components/Pagination'
import { usePagination } from '../hooks/usePagination'

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

const ACTION_META = {
  借出: { icon: '↗', tone: 'loan' },
  调拨: { icon: '⇄', tone: 'transfer' },
  报废: { icon: '◇', tone: 'scrap' },
}

export default function Approvals() {
  const [list, setList] = useState([])
  const [error, setError] = useState('')
  const [msg, setMsg] = useState('')
  const [query, setQuery] = useState('')
  const [tab, setTab] = useState('biz') // biz=业务审批 reg=注册审批
  const [regs, setRegs] = useState([])
  const [statusFilter, setStatusFilter] = useState('')
  const [regQuery, setRegQuery] = useState('')
  const operatorId = getOperatorId()
  const currentUser = getStoredUser()
  const isLeader = userIsLeader(currentUser)
  const superAdmin = isSuperAdmin(currentUser)

  function load() {
    return api.get('/approvals').then(setList).catch((e) => setError(e.message))
  }

  function loadRegs() {
    return api.get('/auth/registrations').then(setRegs).catch((e) => setError(e.message))
  }

  useEffect(() => { load() }, [])
  useEffect(() => { if (isLeader) loadRegs() }, [isLeader])

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

  const searched = useMemo(() =>
    filterByQuery(list, query, (a) => [
      String(a.id), a.action_type, a.overall_status, String(a.part_id),
      a.applicant?.name, a.dest_org?.org_name, a.reason_code, a.expected_return_date,
      ...(a.steps || []).flatMap((s) => [s.approver?.name, s.step_status, s.opinion]),
    ]),
  [list, query])
  const visible = useMemo(() => statusFilter ? searched.filter((item) => item.overall_status === statusFilter) : searched, [searched, statusFilter])
  const visibleRegs = useMemo(() => filterByQuery(regs, regQuery, (user) => [user.name, user.username, user.applied_role, user.apply_reason]), [regQuery, regs])
  const statusCounts = useMemo(() => list.reduce((counts, item) => ({ ...counts, [item.overall_status]: (counts[item.overall_status] || 0) + 1 }), {}), [list])
  const myTodoCount = useMemo(() => list.filter((item) => {
    const current = item.steps.find((step) => step.level === item.current_level)
    return item.overall_status === '审批中' && current?.approver_id === operatorId
  }).length, [list, operatorId])
  const businessPagination = usePagination(visible)
  const registrationPagination = usePagination(visibleRegs)

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
    <div className="panel approval-workbench">
      <header className="approval-header">
        <div>
          <span className="approval-kicker">业务流程 · APPROVAL WORKBENCH</span>
          <h2>审批中心</h2>
          <p className="muted">集中处理配件借出、调拨、报废及用户注册申请。</p>
        </div>
        <div className={`approval-role-tip ${superAdmin ? 'is-super-admin' : ''}`}><span>{superAdmin ? '超级管理员视角' : isLeader ? '审批人视角' : '申请人视角'}</span><strong>{superAdmin ? '本人发起的业务自动通过' : isLeader ? '可审批当前待办' : '可查看并撤回本人申请'}</strong></div>
      </header>

      <section className="approval-stats" aria-label="审批统计">
        <button type="button" className={!statusFilter ? 'active' : ''} onClick={() => { setStatusFilter(''); setTab('biz') }}><span className="approval-stat-icon all">▣</span><div><strong>{list.length}</strong><small>全部申请</small></div></button>
        <button type="button" className={statusFilter === '审批中' ? 'active' : ''} onClick={() => { setStatusFilter('审批中'); setTab('biz') }}><span className="approval-stat-icon pending">◷</span><div><strong>{statusCounts['审批中'] || 0}</strong><small>流转中</small></div></button>
        <button type="button" className="todo" onClick={() => { setStatusFilter('审批中'); setTab('biz') }}><span className="approval-stat-icon todo">!</span><div><strong>{myTodoCount}</strong><small>我的待办</small></div></button>
        <button type="button" className={statusFilter === '通过' ? 'active' : ''} onClick={() => { setStatusFilter('通过'); setTab('biz') }}><span className="approval-stat-icon approved">✓</span><div><strong>{statusCounts['通过'] || 0}</strong><small>已通过</small></div></button>
        <button type="button" className={statusFilter === '驳回' ? 'active' : ''} onClick={() => { setStatusFilter('驳回'); setTab('biz') }}><span className="approval-stat-icon rejected">×</span><div><strong>{statusCounts['驳回'] || 0}</strong><small>已驳回</small></div></button>
      </section>

      <nav className="approval-tabs" aria-label="审批类型">
        <button type="button" className={tab === 'biz' ? 'active' : ''} onClick={() => setTab('biz')}><span>业务审批</span><em>{list.length}</em></button>
        {isLeader && <button type="button" className={tab === 'reg' ? 'active' : ''} onClick={() => setTab('reg')}><span>注册审批</span><em className={regs.length ? 'has-pending' : ''}>{regs.length}</em></button>}
      </nav>

      {error && <div className="error">{error}</div>}
      {msg && <div className="ok-msg">{msg}</div>}

      {tab === 'reg' && isLeader && (
        <section className="approval-list-panel">
          <div className="approval-section-head"><div><span>账号准入</span><h3>待审核注册申请</h3></div><p>通过后账号将立即生效</p></div>
          <ListToolbar query={regQuery} onQueryChange={setRegQuery} placeholder="搜索姓名 / 用户名 / 申请角色…" resultText={<span>显示 <strong>{visibleRegs.length}</strong> 条申请</span>} />
          <div className="approval-table-wrap"><table className="approval-registration-table">
            <thead><tr><th>申请人</th><th>登录账号</th><th>申请角色</th><th>申请理由</th><th>操作</th></tr></thead>
            <tbody>
              {registrationPagination.pageItems.map((user) => <tr key={user.id}><td><div className="approval-user"><span>{user.name?.slice(0, 1)}</span><strong>{user.name}</strong></div></td><td><code>{user.username}</code></td><td><span className="approval-role-badge">{user.applied_role}</span></td><td className="approval-reason">{user.apply_reason || '—'}</td><td><div className="row-actions"><button type="button" className="ap-btn-approve" onClick={() => approveReg(user)}>✓ 通过</button><button type="button" className="ap-btn-reject" onClick={() => rejectReg(user)}>驳回</button></div></td></tr>)}
              {!visibleRegs.length && <tr><td colSpan={5}><div className="approval-empty"><span>✓</span><strong>{regs.length ? '无匹配申请' : '暂无待审核注册申请'}</strong></div></td></tr>}
            </tbody>
          </table></div>
          <Pagination pagination={registrationPagination} />
        </section>
      )}

      {tab === 'biz' && (
        <section className="approval-list-panel">
          <div className="approval-section-head"><div><span>业务单据</span><h3>{statusFilter ? `${statusFilter}申请` : '全部审批申请'}</h3></div>{statusFilter && <button type="button" className="linkish" onClick={() => setStatusFilter('')}>清除状态筛选</button>}</div>
          <ListToolbar query={query} onQueryChange={setQuery} placeholder="搜索单号 / 类型 / 申请人 / 外单位…" resultText={<span>共 <strong>{list.length}</strong> 单，显示 <strong>{visible.length}</strong></span>} />

          <div className="approval-card-list">
            {businessPagination.pageItems.map((approval) => {
              const currentStep = approval.steps.find((step) => step.level === approval.current_level)
              const canDecide = approval.overall_status === '审批中' && currentStep?.approver_id === operatorId
              const canWithdraw = approval.overall_status === '审批中' && approval.applicant_id === operatorId
              const actionMeta = ACTION_META[approval.action_type] || { icon: '○', tone: 'default' }
              const passedSteps = approval.steps.filter((step) => step.step_status === '通过').length
              return (
                <article key={approval.id} className={`ap-card is-${actionMeta.tone} ${canDecide ? 'needs-action' : ''}`}>
                  <div className="ap-card-header">
                    <div className={`ap-action-icon is-${actionMeta.tone}`}>{actionMeta.icon}</div>
                    <div className="ap-card-identity"><div className="ap-card-title"><span className="ap-type">{approval.action_type}申请</span><span className="ap-id">单号 #{approval.id}</span><span className={`ap-status ${statusClass(approval.overall_status)}`}>{approval.overall_status}</span>{canDecide && <span className="ap-todo-mark">待我处理</span>}</div><div className="ap-card-meta"><span><small>配件编号</small><strong>#{approval.part_id}</strong></span><span><small>申请人</small><strong>{approval.applicant?.name || '—'}</strong></span>{approval.dest_org?.org_name && <span><small>目标单位</small><strong>{approval.dest_org.org_name}</strong></span>}{approval.reason_code && <span><small>申请缘由</small><strong>{approval.reason_code}</strong></span>}{approval.expected_return_date && <span><small>预期归还</small><strong>{approval.expected_return_date}</strong></span>}</div></div>
                    <div className={`ap-progress-summary ${approval.auto_approved ? 'is-auto-approved' : ''}`}><strong>{approval.auto_approved ? '直通' : `${passedSteps}/${approval.steps.length}`}</strong><span>{approval.auto_approved ? '超级管理员免审批' : '已通过节点'}</span></div>
                  </div>

                  {approval.auto_approved ? <div className="ap-process ap-auto-process"><div className="ap-process-head"><strong>执行方式</strong><span>提交后立即生效</span></div><div className="ap-auto-approved"><i>✓</i><div><strong>超级管理员免审批</strong><span>业务校验通过后已直接落账，操作人和资产履历均已记录。</span></div></div></div> : <div className="ap-process"><div className="ap-process-head"><strong>审批流程</strong><span>{approval.overall_status === '审批中' ? `当前第 ${approval.current_level} 级` : '流程已结束'}</span></div><div className="ap-steps">
                    {approval.steps.map((step, index) => <div key={step.id} className="ap-step-wrap"><div className={`ap-step-dot ${stepDot(step.step_status)} ${step.level === approval.current_level && approval.overall_status === '审批中' ? 'ap-step-current' : ''}`}>{step.step_status === '通过' ? '✓' : step.step_status === '驳回' ? '×' : step.level}</div><div className="ap-step-label">{step.approver?.name || `L${step.level}`}</div><div className="ap-step-status">{step.step_status}</div>{step.opinion && <div className="ap-step-opinion" title={step.opinion}>{step.opinion}</div>}{index < approval.steps.length - 1 && <div className={`ap-step-line ${step.step_status === '通过' ? 'is-done' : ''}`} />}</div>)}
                  </div></div>}

                  {(canDecide || canWithdraw) && <div className="ap-actions"><div><strong>{canDecide ? '请处理当前审批节点' : '此申请正在流转中'}</strong><span>{canDecide ? '处理结果将立即记录到审批履历' : '可在审批完成前撤回本人申请'}</span></div><div className="row-actions">{canDecide && <><button type="button" className="ap-btn-approve" onClick={() => decide(approval, true)}>✓ 通过当前节点</button><button type="button" className="ap-btn-reject" onClick={() => decide(approval, false)}>驳回申请</button></>}{canWithdraw && <button type="button" className="ap-btn-withdraw" onClick={() => withdraw(approval)}>撤回申请</button>}</div></div>}
                </article>
              )
            })}
            {!visible.length && <div className="approval-empty"><span>◇</span><strong>{list.length ? '没有符合当前条件的审批单' : '暂无审批单'}</strong><p>尝试清除筛选条件或更换搜索词。</p></div>}
          </div>
          <Pagination pagination={businessPagination} />
        </section>
      )}
    </div>
  )
}
