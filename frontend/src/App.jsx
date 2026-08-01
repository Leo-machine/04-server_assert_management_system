import { NavLink, Route, Routes, useLocation } from 'react-router-dom'
import { useEffect, useState } from 'react'
import { api, getOperatorId, setOperatorId } from './api'
import Dashboard from './pages/Dashboard'
import PartsList from './pages/PartsList'
import Inbound from './pages/Inbound'
import PartModels from './pages/PartModels'
import Install from './pages/Install'
import Uninstall from './pages/Uninstall'
import Loan from './pages/Loan'
import Transfer from './pages/Transfer'
import Scrap from './pages/Scrap'
import Damage from './pages/Damage'
import Approvals from './pages/Approvals'
import ReturnPart from './pages/ReturnPart'
import History from './pages/History'
import Servers from './pages/Servers'
import Brands from './pages/Brands'
import Suppliers from './pages/Suppliers'
import AllocatableSummary from './pages/AllocatableSummary'
import Locations from './pages/Locations'
import StocktakeList from './pages/StocktakeList'
import StocktakeDetail from './pages/StocktakeDetail'

const NAV_GROUPS = [
  {
    label: null,
    items: [{ to: '/dashboard', label: '首页概览', icon: '▣' }],
  },
  {
    label: '配件管理',
    items: [
      { to: '/', label: '配件列表', icon: '📋' },
      { to: '/inbound', label: '分类入库', icon: '📥' },
      { to: '/part-models', label: '型号管理', icon: '⚙' },
      { to: '/brands', label: '品牌管理', icon: '🏷' },
      { to: '/suppliers', label: '供应商', icon: '🏭' },
      { to: '/allocatable', label: '可调余量', icon: '📊' },
    ],
  },
  {
    label: '业务操作',
    items: [
      { to: '/approvals', label: '审批中心', icon: '✅' },
    ],
  },
  {
    label: '运营管理',
    items: [
      { to: '/stocktakes', label: '盘点管理', icon: '🔍' },
      { to: '/servers', label: '服务器管理', icon: '🖥' },
      { to: '/locations', label: '存放位置', icon: '📍' },
    ],
  },
]

export default function App() {
  const [users, setUsers] = useState([])
  const [operatorId, setOp] = useState(getOperatorId())
  const location = useLocation()

  useEffect(() => {
    api.get('/users').then(setUsers).catch(console.error)
  }, [])

  function onOperatorChange(e) {
    const id = Number(e.target.value)
    setOperatorId(id)
    setOp(id)
  }

  // 查找当前页面标题用于顶栏面包屑
  const allItems = NAV_GROUPS.flatMap((g) => g.items)
  const currentItem = allItems.find((i) => {
    if (i.to === '/') return location.pathname === '/'
    return location.pathname.startsWith(i.to)
  })

  return (
    <div className="app-shell">
      {/* ---------- 侧边栏 ---------- */}
      <aside className="sidebar">
        <div className="sidebar-brand">
          <img src="/logo.webp" alt="Logo" className="brand-logo" />
          <span className="brand-text">配件资产管理</span>
        </div>

        <nav className="sidebar-nav">
          {NAV_GROUPS.map((group, gi) => (
            <div key={gi} className="nav-group">
              {group.label && <div className="nav-group-label">{group.label}</div>}
              {group.items.map((item) => (
                <NavLink
                  key={item.to}
                  to={item.to}
                  end={item.to === '/' ? true : false}
                  className={({ isActive }) =>
                    `nav-item${isActive ? ' active' : ''}`
                  }
                >
                  <span className="nav-icon">{item.icon}</span>
                  {item.label}
                </NavLink>
              ))}
            </div>
          ))}
        </nav>
      </aside>

      {/* ---------- 右侧主区域 ---------- */}
      <div className="app-main">
        {/* 顶栏 */}
        <header className="topbar">
          <div className="topbar-left">
            <span className="topbar-title">服务器配件资产管理系统</span>
            {currentItem && (
              <>
                <span className="topbar-sep">/</span>
                <span className="topbar-breadcrumb">{currentItem.label}</span>
              </>
            )}
          </div>
          <div className="topbar-right">
            <span className="topbar-op-label">操作人</span>
            <select value={operatorId} onChange={onOperatorChange}>
              {users.map((u) => (
                <option key={u.id} value={u.id}>
                  {u.name}（{u.role_label || '用户'}）
                </option>
              ))}
            </select>
          </div>
        </header>

        {/* 内容区 */}
        <main className="main-content">
          <Routes>
            <Route path="/dashboard" element={<Dashboard />} />
            <Route path="/" element={<PartsList />} />
            <Route path="/inbound" element={<Inbound />} />
            <Route path="/part-models" element={<PartModels />} />
            <Route path="/brands" element={<Brands />} />
            <Route path="/suppliers" element={<Suppliers />} />
            <Route path="/allocatable" element={<AllocatableSummary />} />
            <Route path="/parts/:id/install" element={<Install />} />
            <Route path="/parts/:id/uninstall" element={<Uninstall />} />
            <Route path="/parts/:id/loan" element={<Loan />} />
            <Route path="/parts/:id/transfer" element={<Transfer />} />
            <Route path="/parts/:id/scrap" element={<Scrap />} />
            <Route path="/parts/:id/damage" element={<Damage />} />
            <Route path="/parts/:id/return" element={<ReturnPart />} />
            <Route path="/parts/:id/history" element={<History />} />
            <Route path="/approvals" element={<Approvals />} />
            <Route path="/stocktakes" element={<StocktakeList />} />
            <Route path="/stocktakes/:id" element={<StocktakeDetail />} />
            <Route path="/servers" element={<Servers />} />
            <Route path="/locations" element={<Locations />} />
          </Routes>
        </main>
      </div>
    </div>
  )
}
