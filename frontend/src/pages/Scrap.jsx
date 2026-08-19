import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { api, getStoredUser } from '../api'
import ApproverSelects, { useDefaultApprovers } from '../components/ApproverSelects'
import { SCRAP_REASONS } from '../lib/categories'
import { isSuperAdmin } from '../lib/roles'

const REASON_CODES = SCRAP_REASONS

export default function Scrap() {
  const { id } = useParams()
  const nav = useNavigate()
  const superAdmin = isSuperAdmin(getStoredUser())
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

  const needAttachment = part?.model?.category === '算力卡'

  async function onSubmit(e) {
    e.preventDefault()
    setError('')
    const ids = approvers.map(Number)
    if (!superAdmin && (ids.some((n) => !n) || new Set(ids).size !== 3)) {
      setError('请选择三位互不相同的审批人（须为领导）')
      return
    }
    if (needAttachment && !attachmentRef.trim()) {
      setError('算力卡报废必须填写影像证据引用')
      return
    }
    try {
      await api.post('/approvals/scrap', {
        part_id: Number(id),
        reason_code: reasonCode,
        approver_ids: superAdmin ? [] : ids,
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
      <h2>{superAdmin ? '确认报废（超级管理员免审批）' : '发起报废（三级审批）'}</h2>
      {part && (
        <p className="muted">
          {part.fixed_asset_no} · 当前状态 {part.current_status}
          {part.model?.category ? ` · ${part.model.category}` : ''}
          {part.sensitivity && part.sensitivity !== '无'
            ? ` · ${part.sensitivity}件`
            : ''}
        </p>
      )}
      {superAdmin ? <div className="super-admin-bypass"><strong>超级管理员直通</strong><span>提交后立即报废并写入操作履历；业务校验与高值件影像证据要求仍然生效。</span></div> : <p className="muted">报废一律审批，通过后为终态不可恢复。申请人 = 当前操作人；三级审批人须为领导且互不相同。</p>}
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
          影像证据引用{needAttachment ? '（算力卡必填）' : '（可选）'}
          <input
            value={attachmentRef}
            onChange={(e) => setAttachmentRef(e.target.value)}
            placeholder="如 工单号/影像档案编号"
            required={needAttachment}
          />
        </label>
        {!superAdmin && <ApproverSelects users={users} value={approvers} onChange={setApprovers} />}
        <label>
          备注（可选）
          <input value={remark} onChange={(e) => setRemark(e.target.value)} />
        </label>
        <button type="submit">{superAdmin ? '确认报废' : '提交审批'}</button>
      </form>
    </div>
  )
}
