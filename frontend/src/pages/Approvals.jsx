import { useEffect, useMemo, useState } from 'react'
import { api, getOperatorId } from '../api'
import ListToolbar from '../components/ListToolbar'
import { filterByQuery } from '../lib/fuzzy'

export default function Approvals() {
  const [list, setList] = useState([])
  const [error, setError] = useState('')
  const [msg, setMsg] = useState('')
  const [query, setQuery] = useState('')
  const operatorId = getOperatorId()

  function load() {
    return api.get('/approvals').then(setList).catch((e) => setError(e.message))
  }

  useEffect(() => {
    load()
  }, [])

  const visible = useMemo(
    () =>
      filterByQuery(list, query, (a) => [
        a.id,
        a.action_type,
        a.overall_status,
        a.part_id,
        a.applicant?.name,
        a.dest_org?.org_name,
        a.reason_code,
        a.expected_return_date,
        ...(a.steps || []).flatMap((s) => [s.approver?.name, s.step_status, s.opinion]),
      ]),
    [list, query],
  )

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

  async function withdraw(approval) {
    setError('')
    setMsg('')
    try {
      await api.post(`/approvals/${approval.id}/withdraw`)
      setMsg(`审批单 #${approval.id} 已撤回`)
      await load()
    } catch (err) {
      setError(err.message)
    }
  }

  return (
    <div className="panel">
      <h2>审批中心</h2>
      <p className="muted">
        当前操作人 ID={operatorId}。只有本级指定审批人用对应身份切换后才能点通过/驳回；申请人可撤回审批中的单子。
        审批动作按级指定人执行，不提供批量通过/驳回。
      </p>
      {error && <div className="error">{error}</div>}
      {msg && <div className="ok-msg">{msg}</div>}

      <ListToolbar
        query={query}
        onQueryChange={setQuery}
        placeholder="搜索单号 / 类型 / 状态 / 申请人 / 审批人…"
        resultText={
          <>
            显示 <strong>{visible.length}</strong> / {list.length}
          </>
        }
      />

      {visible.map((a) => {
        const currentStep = a.steps.find((s) => s.level === a.current_level)
        const canDecide =
          a.overall_status === '审批中' &&
          currentStep &&
          currentStep.approver_id === operatorId
        const canWithdraw =
          a.overall_status === '审批中' && a.applicant_id === operatorId
        return (
          <div key={a.id} className="panel" style={{ marginTop: '0.75rem' }}>
            <strong>#{a.id}</strong> {a.action_type} · 配件 #{a.part_id} · {a.overall_status}
            <div className="muted">
              申请人 {a.applicant?.name}
              {a.dest_org ? ` · 外单位 ${a.dest_org.org_name}` : ''}
              {a.expected_return_date ? ` · 预期归还 ${a.expected_return_date}` : ''}
              {a.reason_code ? ` · 缘由 ${a.reason_code}` : ''}
              {a.attachment_ref ? ` · 影像证据 ${a.attachment_ref}` : ''}
              {' '}· 当前第 {a.current_level} 级
            </div>
            <ul className="timeline">
              {a.steps.map((s) => (
                <li key={s.id}>
                  L{s.level} {s.approver?.name} — {s.step_status}
                  {s.opinion ? `（${s.opinion}）` : ''}
                </li>
              ))}
            </ul>
            {(canDecide || canWithdraw) && (
              <div className="row-actions">
                {canDecide && (
                  <>
                    <button type="button" onClick={() => decide(a, true)}>通过</button>
                    <button type="button" className="secondary" onClick={() => decide(a, false)}>
                      驳回
                    </button>
                  </>
                )}
                {canWithdraw && (
                  <button type="button" className="secondary" onClick={() => withdraw(a)}>
                    撤回
                  </button>
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
