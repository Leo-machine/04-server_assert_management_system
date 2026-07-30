import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { api } from '../api'

export default function Uninstall() {
  const { id } = useParams()
  const nav = useNavigate()
  const [part, setPart] = useState(null)
  const [server, setServer] = useState(null)
  const [locs, setLocs] = useState([])
  const [locId, setLocId] = useState('')
  const [error, setError] = useState('')

  useEffect(() => {
    Promise.all([
      api.get(`/parts/${id}`),
      api.get('/servers'),
      api.get('/storage-locations'),
    ]).then(([p, servers, locs]) => {
      setPart(p)
      setLocs(locs)
      setLocId(String(locs[0]?.id || ''))
      const s = servers.find((x) => x.id === p.current_loc_id)
      setServer(s || null)
    }).catch((e) => setError(e.message))
  }, [id])

  async function onSubmit(e) {
    e.preventDefault()
    setError('')
    try {
      await api.post(`/parts/${id}/uninstall`, {
        storage_location_id: Number(locId),
      })
      nav('/')
    } catch (err) {
      setError(err.message)
    }
  }

  return (
    <div className="panel">
      <h2>拆下</h2>
      {part && (
        <p className="muted">
          {part.fixed_asset_no} · 当前状态 {part.current_status}
          {server && ` · 所在服务器 ${server.asset_no}（${server.run_status}）`}
        </p>
      )}
      {server?.run_status === '投运' && (
        <div className="error">
          该服务器处于「投运」，拆下将被拒绝。请先到「服务器」页切到「未投运」。
        </div>
      )}
      {error && <div className="error">{error}</div>}
      <form onSubmit={onSubmit}>
        <label>
          回库库位
          <select value={locId} onChange={(e) => setLocId(e.target.value)} required>
            {locs.map((l) => (
              <option key={l.id} value={l.id}>
                {l.warehouse} / {l.slot}
              </option>
            ))}
          </select>
        </label>
        <button type="submit">确认拆下</button>
      </form>
    </div>
  )
}
