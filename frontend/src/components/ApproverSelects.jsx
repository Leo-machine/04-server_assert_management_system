import { useEffect, useState } from 'react'
import { getOperatorId } from '../api'

// 三级审批人三连选：默认取除当前操作人外的前三位用户
export default function ApproverSelects({ users, value, onChange }) {
  const operatorId = getOperatorId()
  const candidates = users.filter((u) => u.id !== operatorId)
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
            {candidates.map((u) => (
              <option key={u.id} value={u.id}>
                {u.name}
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
    const others = users.filter((x) => x.id !== op)
    setApprovers([
      String(others[0]?.id || ''),
      String(others[1]?.id || ''),
      String(others[2]?.id || ''),
    ])
  }, [users])
  return [approvers, setApprovers]
}
