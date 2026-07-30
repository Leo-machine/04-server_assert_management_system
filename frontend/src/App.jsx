import { NavLink, Route, Routes } from 'react-router-dom'
import { useEffect, useState } from 'react'
import { api, getOperatorId, setOperatorId } from './api'
import PartsList from './pages/PartsList'
import Inbound from './pages/Inbound'
import Install from './pages/Install'
import Uninstall from './pages/Uninstall'
import Loan from './pages/Loan'
import Approvals from './pages/Approvals'
import ReturnPart from './pages/ReturnPart'
import History from './pages/History'
import Servers from './pages/Servers'

export default function App() {
  const [users, setUsers] = useState([])
  const [operatorId, setOp] = useState(getOperatorId())

  useEffect(() => {
    api.get('/users').then(setUsers).catch(console.error)
  }, [])

  function onOperatorChange(e) {
    const id = Number(e.target.value)
    setOperatorId(id)
    setOp(id)
  }

  return (
    <div className="layout">
      <header className="topbar">
        <h1>服务器配件资产管理系统 · Demo</h1>
        <nav>
          <NavLink to="/" end>配件</NavLink>
          <NavLink to="/inbound">入库</NavLink>
          <NavLink to="/approvals">审批</NavLink>
          <NavLink to="/servers">服务器</NavLink>
        </nav>
        <div className="operator">
          <span>当前操作人</span>
          <select value={operatorId} onChange={onOperatorChange}>
            {users.map((u) => (
              <option key={u.id} value={u.id}>
                {u.name}（{u.role_label || '用户'}）
              </option>
            ))}
          </select>
        </div>
      </header>
      <main className="main">
        <Routes>
          <Route path="/" element={<PartsList />} />
          <Route path="/inbound" element={<Inbound />} />
          <Route path="/parts/:id/install" element={<Install />} />
          <Route path="/parts/:id/uninstall" element={<Uninstall />} />
          <Route path="/parts/:id/loan" element={<Loan />} />
          <Route path="/parts/:id/return" element={<ReturnPart />} />
          <Route path="/parts/:id/history" element={<History />} />
          <Route path="/approvals" element={<Approvals />} />
          <Route path="/servers" element={<Servers />} />
        </Routes>
      </main>
    </div>
  )
}
