import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api'

export default function StocktakeList() {
  const [list, setList] = useState([])
  const [error, setError] = useState('')
  const [msg, setMsg] = useState('')

  function load() {
    return api.get('/stocktakes').then(setList).catch((e) => setError(e.message))
  }

  useEffect(() => {
    load()
  }, [])

  async function createFull() {
    setError('')
    setMsg('')
    try {
      const st = await api.post('/stocktakes', { scope_kind: '全盘' })
      setMsg(`已发起全盘 #${st.id}，冻结 ${st.items?.length || 0} 条明细`)
      await load()
    } catch (e) {
      setError(e.message)
    }
  }

  return (
    <div className="panel">
      <h2>盘点任务</h2>
      <p className="muted">纯发现层：冻结快照后清点/函证，不改配件状态与履历。</p>
      {error && <div className="error">{error}</div>}
      {msg && <div className="ok-msg">{msg}</div>}
      <button type="button" onClick={createFull}>发起全盘</button>
      <table style={{ marginTop: '1rem' }}>
        <thead>
          <tr>
            <th>单号</th>
            <th>范围</th>
            <th>状态</th>
            <th>发起时间</th>
            <th>快照时间</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {list.map((s) => (
            <tr key={s.id}>
              <td>#{s.id}</td>
              <td>{s.scope_kind}</td>
              <td><span className="badge">{s.status}</span></td>
              <td>{s.initiated_at}</td>
              <td>{s.snapshot_at}</td>
              <td><Link to={`/stocktakes/${s.id}`}>进入</Link></td>
            </tr>
          ))}
        </tbody>
      </table>
      {!list.length && <p className="muted">暂无盘点单</p>}
    </div>
  )
}
