import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api'

function locLabel(part, servers, locs, orgs) {
  if (!part.current_loc_kind) return '-'
  if (part.current_loc_kind === '库位') {
    const loc = locs.find((l) => l.id === part.current_loc_id)
    return loc ? `${loc.warehouse}/${loc.slot}` : `库位#${part.current_loc_id}`
  }
  if (part.current_loc_kind === '服务器') {
    const s = servers.find((x) => x.id === part.current_loc_id)
    return s ? `${s.asset_no}（${s.run_status}）` : `服务器#${part.current_loc_id}`
  }
  if (part.current_loc_kind === '外单位') {
    const o = orgs.find((x) => x.id === part.current_loc_id)
    return o ? o.org_name : `外单位#${part.current_loc_id}`
  }
  return part.current_loc_kind
}

export default function PartsList() {
  const [parts, setParts] = useState([])
  const [servers, setServers] = useState([])
  const [locs, setLocs] = useState([])
  const [orgs, setOrgs] = useState([])
  const [error, setError] = useState('')

  useEffect(() => {
    Promise.all([
      api.get('/parts'),
      api.get('/servers'),
      api.get('/storage-locations'),
      api.get('/external-orgs'),
    ])
      .then(([p, s, l, o]) => {
        setParts(p)
        setServers(s)
        setLocs(l)
        setOrgs(o)
      })
      .catch((e) => setError(e.message))
  }, [])

  return (
    <div className="panel">
      <h2>配件列表</h2>
      <p className="muted">主线入口：入库 → 装机 → 拆下 → 借出审批 → 归还；可查看履历。</p>
      {error && <div className="error">{error}</div>}
      <table>
        <thead>
          <tr>
            <th>固定资产编号</th>
            <th>型号</th>
            <th>状态</th>
            <th>位置</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          {parts.map((p) => (
            <tr key={p.id}>
              <td>{p.fixed_asset_no}</td>
              <td>{p.model?.model_name || p.model_id}</td>
              <td>
                <span className={`badge ${p.is_overdue ? 'danger' : ''}`}>
                  {p.current_status}
                  {p.is_overdue ? ' · 超期' : ''}
                </span>
              </td>
              <td>{locLabel(p, servers, locs, orgs)}</td>
              <td>
                <div className="row-actions">
                  <Link to={`/parts/${p.id}/history`}>履历</Link>
                  {p.current_status === '在库' && (
                    <>
                      <Link to={`/parts/${p.id}/install`}>装机</Link>
                      <Link to={`/parts/${p.id}/loan`}>借出</Link>
                    </>
                  )}
                  {p.current_status === '在用' && (
                    <Link to={`/parts/${p.id}/uninstall`}>拆下</Link>
                  )}
                  {p.current_status === '借出' && (
                    <Link to={`/parts/${p.id}/return`}>归还</Link>
                  )}
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
