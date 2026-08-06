import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { api } from '../api'
import ApproverSelects, { useDefaultApprovers } from '../components/ApproverSelects'

export default function Loan() {
  const { id } = useParams()
  const nav = useNavigate()
  const [part, setPart] = useState(null)
  const [orgs, setOrgs] = useState([])
  const [users, setUsers] = useState([])
  const [approvers, setApprovers] = useDefaultApprovers(users)
  const [orgId, setOrgId] = useState('')
  const [date, setDate] = useState('')
  const [error, setError] = useState('')

  useEffect(() => {
    Promise.all([
      api.get(`/parts/${id}`),
      api.get('/external-orgs'),
      api.get('/users'),
    ]).then(([p, o, u]) => {
      setPart(p)
      setOrgs(o)
      setUsers(u)
      setOrgId(String(o[0]?.id || ''))
      const d = new Date()
      d.setDate(d.getDate() + 14)
      setDate(d.toISOString().slice(0, 10))
    }).catch((e) => setError(e.message))
  }, [id])

  async function onSubmit(e) {
    e.preventDefault()
    setError('')
    const ids = approvers.map(Number)
    if (ids.some((n) => !n) || new Set(ids).size !== 3) {
      setError('请选择三位互不相同的审批人（须为领导）')
      return
    }
    try {
      await api.post('/approvals/loan', {
        part_id: Number(id),
        dest_org_id: Number(orgId),
        expected_return_date: date,
        approver_ids: ids,
      })
      nav('/approvals')
    } catch (err) {
      setError(err.message)
    }
  }

  return (
    <div className="panel">
      <button type="button" className="back-link" onClick={() => nav('/')}>
        返回配件列表
      </button>
      <h2>发起借出（三级审批）</h2>
      {part && (
        <p className="muted">
          {part.fixed_asset_no} · 当前状态 {part.current_status}
        </p>
      )}
      <p className="muted">申请人 = 当前登录用户；不得出现在审批人中；三级审批人须为领导且互不相同。</p>
      {error && <div className="error">{error}</div>}
      <form onSubmit={onSubmit}>
        <label>
          外单位
          <select value={orgId} onChange={(e) => setOrgId(e.target.value)} required>
            {orgs.map((o) => (
              <option key={o.id} value={o.id}>{o.org_name}</option>
            ))}
          </select>
        </label>
        <label>
          预期归还日（必填）
          <input type="date" value={date} onChange={(e) => setDate(e.target.value)} required />
        </label>
        <ApproverSelects users={users} value={approvers} onChange={setApprovers} />
        <button type="submit">提交审批</button>
      </form>
    </div>
  )
}
