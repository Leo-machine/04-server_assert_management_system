import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { api } from '../api'
import ApproverSelects, { useDefaultApprovers } from '../components/ApproverSelects'

const REASON_CODES = ['本单位销毁', '返厂换新']

export default function Scrap() {
  const { id } = useParams()
  const nav = useNavigate()
  const [part, setPart] = useState(null)
  const [users, setUsers] = useState([])
  const [approvers, setApprovers] = useDefaultApprovers(users)
  const [reasonCode, setReasonCode] = useState(REASON_CODES[0])
  const [attachmentRef, setAttachmentRef] = useState('')
  const [remark, setRemark] = useState('')
  const [error, setError] = useState('')

  useEffect(() => {
    Promise.all([api.get(`/parts/${id}`), api.get('/users')])
      .then(([p, u]) => {
        setPart(p)
        setUsers(u)
      })
      .catch((e) => setError(e.message))
  }, [id])

  const sensitive = ["管控", "出口管制"].includes(part?.sensitivity)

  async function onSubmit(e) {
    e.preventDefault()
    setError('')
    try {
      await api.post('/approvals/scrap', {
        part_id: Number(id),
        reason_code: reasonCode,
        approver_ids: approvers.map(Number),
        attachment_ref: attachmentRef || null,
        remark: remark || null,
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
      <h2>发起报废（三级审批）</h2>
      {part && (
        <p className="muted">
          {part.fixed_asset_no} · 当前状态 {part.current_status}
          {part.sensitivity && part.sensitivity !== '无'
            ? ` · ${part.sensitivity}件`
            : ''}
        </p>
      )}
      <p className="muted">
        报废一律审批，通过后为终态不可恢复。申请人 = 当前操作人；三级审批人须互不相同。
      </p>
      {error && <div className="error">{error}</div>}
      <form onSubmit={onSubmit}>
        <label>
          报废缘由
          <select value={reasonCode} onChange={(e) => setReasonCode(e.target.value)} required>
            {REASON_CODES.map((r) => (
              <option key={r} value={r}>{r}</option>
            ))}
          </select>
        </label>
        <label>
          影像证据引用{sensitive ? '（管控/敏感件必填）' : '（可选）'}
          <input
            value={attachmentRef}
            onChange={(e) => setAttachmentRef(e.target.value)}
            placeholder="如 工单号/影像档案编号"
            required={sensitive}
          />
        </label>
        <ApproverSelects users={users} value={approvers} onChange={setApprovers} />
        <label>
          备注（可选）
          <input value={remark} onChange={(e) => setRemark(e.target.value)} />
        </label>
        <button type="submit">提交审批</button>
      </form>
    </div>
  )
}
