import { useEffect, useState } from 'react'
import { api } from '../api'

export default function Servers() {
  const [servers, setServers] = useState([])
  const [error, setError] = useState('')
  const [msg, setMsg] = useState('')

  function load() {
    return api.get('/servers').then(setServers).catch((e) => setError(e.message))
  }

  useEffect(() => {
    load()
  }, [])

  async function toggle(server) {
    setError('')
    setMsg('')
    const next = server.run_status === '投运' ? '未投运' : '投运'
    try {
      await api.patch(`/servers/${server.id}/run-status`, { run_status: next })
      setMsg(`${server.asset_no} → ${next}`)
      await load()
    } catch (err) {
      setError(err.message)
    }
  }

  return (
    <div className="panel">
      <h2>服务器</h2>
      <p className="muted">可在「未投运 / 投运」间切换，用于演示投运锁拆。退役不可通过本页设置。</p>
      {error && <div className="error">{error}</div>}
      {msg && <div className="ok-msg">{msg}</div>}
      <table>
        <thead>
          <tr>
            <th>资产编号</th>
            <th>型号</th>
            <th>机房/机柜</th>
            <th>运行状态</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          {servers.map((s) => (
            <tr key={s.id}>
              <td>{s.asset_no}</td>
              <td>{s.model}</td>
              <td>{s.room} / {s.rack}</td>
              <td>
                <span className={`badge ${s.run_status === '投运' ? 'warn' : 'ok'}`}>
                  {s.run_status}
                </span>
              </td>
              <td>
                {s.run_status !== '退役' && (
                  <button type="button" className="secondary" onClick={() => toggle(s)}>
                    切换为{s.run_status === '投运' ? '未投运' : '投运'}
                  </button>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
