import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { api } from '../api'

export default function ReturnPart() {
  const { id } = useParams()
  const nav = useNavigate()
  const [part, setPart] = useState(null)
  const [locs, setLocs] = useState([])
  const [locId, setLocId] = useState('')
  const [error, setError] = useState('')

  useEffect(() => {
    Promise.all([api.get(`/parts/${id}`), api.get('/storage-locations')]).then(
      ([p, l]) => {
        setPart(p)
        setLocs(l)
        setLocId(String(l[0]?.id || ''))
      },
    ).catch((e) => setError(e.message))
  }, [id])

  async function onSubmit(e) {
    e.preventDefault()
    setError('')
    try {
      await api.post(`/parts/${id}/return`, {
        storage_location_id: Number(locId),
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
      <h2>归还（收货确认）</h2>
      {part && (
        <p className="muted">
          {part.fixed_asset_no} · 当前状态 {part.current_status}
          {part.is_overdue ? ' · 已超期' : ''}
        </p>
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
        <button type="submit">确认归还入库</button>
      </form>
    </div>
  )
}
