import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { api } from '../api'

export default function Damage() {
  const { id } = useParams()
  const nav = useNavigate()
  const [part, setPart] = useState(null)
  const [remark, setRemark] = useState('')
  const [error, setError] = useState('')

  useEffect(() => {
    api.get(`/parts/${id}`).then(setPart).catch((e) => setError(e.message))
  }, [id])

  async function onSubmit(e) {
    e.preventDefault()
    setError('')
    try {
      await api.post(`/parts/${id}/damage`, { remark })
      nav('/')
    } catch (err) {
      setError(err.message)
    }
  }

  return (
    <div className="panel">
      <button type="button" className="back-link" onClick={() => nav('/')}>
        返回配件列表
      </button>
      <h2>库内报损</h2>
      {part && (
        <p className="muted">
          {part.fixed_asset_no} · 当前状态 {part.current_status}
        </p>
      )}
      <p className="muted">
        在库件发现损坏时登记，配件转入「损坏」状态，位置不变；后续只能走报废审批。
      </p>
      {error && <div className="error">{error}</div>}
      <form onSubmit={onSubmit}>
        <label>
          损坏情况说明（必填）
          <input
            value={remark}
            onChange={(e) => setRemark(e.target.value)}
            placeholder="如 金手指氧化 / 通电不识别"
            required
          />
        </label>
        <button type="submit">确认报损</button>
      </form>
    </div>
  )
}
