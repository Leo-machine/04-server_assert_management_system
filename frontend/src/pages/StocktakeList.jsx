import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, getStoredUser } from '../api'
import ListToolbar from '../components/ListToolbar'
import { filterByQuery } from '../lib/fuzzy'

const CAN_MANAGE = new Set(['审批人', '管理员'])

export default function StocktakeList() {
  const [list, setList] = useState([])
  const [error, setError] = useState('')
  const [msg, setMsg] = useState('')
  const [query, setQuery] = useState('')
  const canManage = CAN_MANAGE.has(getStoredUser()?.role || '')

  function load() {
    return api.get('/stocktakes').then(setList).catch((e) => setError(e.message))
  }

  useEffect(() => {
    load()
  }, [])

  const visible = useMemo(
    () =>
      filterByQuery(list, query, (s) => [
        s.id,
        s.scope_kind,
        s.status,
        s.initiated_at,
        s.snapshot_at,
      ]),
    [list, query],
  )

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
      <p className="muted">
        纯发现层：冻结快照后清点/函证，不改配件状态与履历。
        {!canManage && ' 发起/结案需审批人或管理员账号。'}
      </p>
      {error && <div className="error">{error}</div>}
      {msg && <div className="ok-msg">{msg}</div>}
      {canManage ? (
        <button type="button" onClick={createFull}>发起全盘</button>
      ) : (
        <p className="muted">当前角色不可发起盘点，请使用审批人（如 lizz）登录。</p>
      )}

      <ListToolbar
        query={query}
        onQueryChange={setQuery}
        placeholder="搜索单号 / 范围 / 状态…"
        resultText={
          <>
            显示 <strong>{visible.length}</strong> / {list.length}
          </>
        }
      />

      <table style={{ marginTop: '0.5rem' }}>
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
          {visible.map((s) => (
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
      {!visible.length && (
        <p className="muted">{list.length ? '无匹配盘点单' : '暂无盘点单'}</p>
      )}
    </div>
  )
}
