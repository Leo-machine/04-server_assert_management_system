import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { api } from '../api'

export default function Install() {
  const { id } = useParams()
  const nav = useNavigate()
  const [part, setPart] = useState(null)
  const [servers, setServers] = useState([])
  const [serverId, setServerId] = useState('')
  const [slot, setSlot] = useState('')
  const [error, setError] = useState('')

  useEffect(() => {
    Promise.all([api.get(`/parts/${id}`), api.get('/servers')]).then(([p, s]) => {
      setPart(p)
      setServers(s)
      const idle = s.find((x) => x.run_status === '未投运')
      const target = idle || s[0]
      setServerId(String(target?.id || ''))
      if (!idle && s.length > 0) {
        setError('注意：当前无「未投运」服务器，如选投运服务器则装机后无法拆下。')
      }
    }).catch((e) => setError(e.message))
  }, [id])

  async function onSubmit(e) {
    e.preventDefault()
    setError('')
    try {
      await api.post(`/parts/${id}/install`, {
        server_id: Number(serverId),
        slot: slot || null,
      })
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
      <h2>装机</h2>
      {part && (
        <p className="muted">
          {part.fixed_asset_no} · 当前状态 {part.current_status}
        </p>
      )}
      {error && <div className="error">{error}</div>}
      <form onSubmit={onSubmit}>
        <label>
          目标服务器
          <select value={serverId} onChange={(e) => setServerId(e.target.value)} required>
            {servers.map((s) => (
              <option key={s.id} value={s.id}>
                {s.asset_no}（{s.run_status}）
              </option>
            ))}
          </select>
        </label>
        <label>
          槽位（可选）
          <input value={slot} onChange={(e) => setSlot(e.target.value)} />
        </label>
        <button type="submit">确认装机</button>
      </form>
    </div>
  )
}
