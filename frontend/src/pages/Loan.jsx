import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { api, getOperatorId } from '../api'

export default function Loan() {
  const { id } = useParams()
  const nav = useNavigate()
  const [part, setPart] = useState(null)
  const [orgs, setOrgs] = useState([])
  const [users, setUsers] = useState([])
  const [orgId, setOrgId] = useState('')
  const [date, setDate] = useState('')
  const [a1, setA1] = useState('')
  const [a2, setA2] = useState('')
  const [a3, setA3] = useState('')
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
      const op = getOperatorId()
      const others = u.filter((x) => x.id !== op)
      setA1(String(others[0]?.id || ''))
      setA2(String(others[1]?.id || ''))
      setA3(String(others[2]?.id || ''))
      const d = new Date()
      d.setDate(d.getDate() + 14)
      setDate(d.toISOString().slice(0, 10))
    }).catch((e) => setError(e.message))
  }, [id])

  async function onSubmit(e) {
    e.preventDefault()
    setError('')
    try {
      await api.post('/approvals/loan', {
        part_id: Number(id),
        dest_org_id: Number(orgId),
        expected_return_date: date,
        approver_ids: [Number(a1), Number(a2), Number(a3)],
      })
      nav('/approvals')
    } catch (err) {
      setError(err.message)
    }
  }

  const operatorId = getOperatorId()
  const candidates = users.filter((u) => u.id !== operatorId)

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
      <p className="muted">申请人 = 当前操作人；不得出现在审批人中；三级审批人须互不相同。</p>
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
        <label>
          一级审批人
          <select value={a1} onChange={(e) => setA1(e.target.value)} required>
            {candidates.map((u) => (
              <option key={u.id} value={u.id}>{u.name}</option>
            ))}
          </select>
        </label>
        <label>
          二级审批人
          <select value={a2} onChange={(e) => setA2(e.target.value)} required>
            {candidates.map((u) => (
              <option key={u.id} value={u.id}>{u.name}</option>
            ))}
          </select>
        </label>
        <label>
          三级审批人
          <select value={a3} onChange={(e) => setA3(e.target.value)} required>
            {candidates.map((u) => (
              <option key={u.id} value={u.id}>{u.name}</option>
            ))}
          </select>
        </label>
        <button type="submit">提交审批</button>
      </form>
    </div>
  )
}
