import { useEffect, useState } from 'react'
import { getOperatorId } from '../api'
import { APPROVER_ROLES } from '../lib/roles'

function approverCandidates(users, operatorId) {
  return users
    .filter((u) => u.id !== operatorId && APPROVER_ROLES.has(u.role || ''))
    .sort((a, b) => (a.id || 0) - (b.id || 0))
}

// 三级审批人三连选：仅领导可担任审批人
export default function ApproverSelects({ users, value, onChange }) {
  const operatorId = getOperatorId()
  const candidates = approverCandidates(users, operatorId)
  const [a1, a2, a3] = value

  function setAt(idx, v) {
    const next = [a1, a2, a3]
    next[idx] = v
    onChange(next)
  }

  return (
    <>
      {['一级审批人', '二级审批人', '三级审批人'].map((label, idx) => (
        <label key={label}>
          {label}
          <select
            value={[a1, a2, a3][idx]}
            onChange={(e) => setAt(idx, e.target.value)}
            required
          >
            {candidates.length === 0 && (
              <option value="">暂无可用领导审批人</option>
            )}
            {candidates.map((u) => (
              <option key={u.id} value={u.id}>
                {u.name}（{u.role_label || u.role}）
              </option>
            ))}
          </select>
        </label>
      ))}
    </>
  )
}

export function useDefaultApprovers(users) {
  const [approvers, setApprovers] = useState(['', '', ''])
  useEffect(() => {
    const op = getOperatorId()
    const others = approverCandidates(users, op)
    setApprovers([
      String(others[0]?.id || ''),
      String(others[1]?.id || ''),
      String(others[2]?.id || ''),
    ])
  }, [users])
  return [approvers, setApprovers]
}
