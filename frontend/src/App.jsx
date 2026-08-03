import { Navigate, NavLink, Route, Routes, useLocation, useNavigate } from 'react-router-dom'
import { useEffect, useState } from 'react'
import { api, clearToken, getStoredUser, getToken, setStoredUser } from './api'
import Dashboard from './pages/Dashboard'
import PartsList from './pages/PartsList'
import PartDetail from './pages/PartDetail'
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
import Locations from './pages/Locations'
import AllocatableSummary from './pages/AllocatableSummary'
import StocktakeList from './pages/StocktakeList'
import StocktakeDetail from './pages/StocktakeDetail'
import Login from './pages/Login'

const ALL_NAV_GROUPS = [
  {
    label: null,
    roles: null,
    items: [{ to: '/dashboard', label: '首页概览', icon: '▣' }],
  },
  {
    label: '总览与库位',
    roles: null,
    items: [
      { to: '/allocatable', label: '可调余量', icon: '📊' },
      { to: '/locations', label: '存放位置', icon: '📍' },
    ],
  },
  {
    label: '出入库与流转',
    roles: null,
    items: [
      { to: '/', label: '配件列表', icon: '📋' },
      { to: '/inbound', label: '分类入库', icon: '📥' },
      { to: '/approvals', label: '审批中心', icon: '✅' },
      { to: '/stocktakes', label: '盘点管理', icon: '🔍' },
      { to: '/servers', label: '服务器管理', icon: '🖥' },
    ],
  },
  {
    label: '基础数据',
    roles: ['管理员'],
    items: [
      { to: '/part-models', label: '型号管理', icon: '⚙' },
      { to: '/brands', label: '品牌管理', icon: '🏷' },
      { to: '/suppliers', label: '供应商', icon: '🏭' },
    ],
  },
]

function AuthGuard({ children }) {
  const user = getStoredUser()
  if (!user || !getToken()) {
    return <Navigate to="/login" replace />
  }
  return children
}

export default function App() {
  const user = getStoredUser()
  const nav = useNavigate()
  const [collapsed, setCollapsed] = useState({})
  const location = useLocation()

  // 登录页不渲染侧边栏
  if (location.pathname === '/login') {
    return (
      <Routes>
        <Route path="/login" element={<Login />} />
      </Routes>
    )
  }

  // 未登录跳转
  if (!user || !getToken()) {
    return <Navigate to="/login" replace />
  }

  // 按角色过滤导航
  const role = user.role
  const navGroups = ALL_NAV_GROUPS.filter((g) => {
    if (!g.roles) return true
    return g.roles.includes(role)
  })

  function toggleGroup(gi) {
    setCollapsed((prev) => ({ ...prev, [gi]: !prev[gi] }))
  }

  function handleLogout() {
    clearToken()
    nav('/login', { replace: true })
  }

  const allItems = navGroups.flatMap((g) => g.items)
  const currentItem = allItems.find((i) => {
    if (i.to === '/') return location.pathname === '/'
    return location.pathname.startsWith(i.to)
  })

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="sidebar-brand">
          <img src="/logo.webp" alt="Logo" className="brand-logo" />
          <span className="brand-text">配件资产管理</span>
        </div>

        <nav className="sidebar-nav">
          {navGroups.map((group, gi) => (
            <div key={gi} className="nav-group">
              {group.label ? (
                <button
                  type="button"
                  className={`nav-group-toggle ${collapsed[gi] ? 'is-folded' : ''}`}
                  onClick={() => toggleGroup(gi)}
                >
                  <span className="nav-group-arrow">▾</span>
                  {group.label}
                </button>
              ) : null}
              <div className={`nav-group-items ${collapsed[gi] ? 'is-folded' : ''}`}>
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
            </div>
          ))}
        </nav>
      </aside>

      <div className="app-main">
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
            <span className="topbar-user">
              {user.name}（{user.role}）
            </span>
            <button type="button" className="topbar-logout" onClick={handleLogout}>
              退出
            </button>
          </div>
        </header>

        <main className="main-content">
          <AuthGuard>
            <Routes>
              <Route path="/dashboard" element={<Dashboard />} />
              <Route path="/" element={<PartsList />} />
              <Route path="/inbound" element={<Inbound />} />
              <Route path="/part-models" element={<PartModels />} />
              <Route path="/brands" element={<Brands />} />
              <Route path="/suppliers" element={<Suppliers />} />
              <Route path="/parts/:id/install" element={<Install />} />
              <Route path="/parts/:id/uninstall" element={<Uninstall />} />
              <Route path="/parts/:id/loan" element={<Loan />} />
              <Route path="/parts/:id/transfer" element={<Transfer />} />
              <Route path="/parts/:id/scrap" element={<Scrap />} />
              <Route path="/parts/:id/damage" element={<Damage />} />
              <Route path="/parts/:id/return" element={<ReturnPart />} />
              <Route path="/parts/:id/history" element={<History />} />
              <Route path="/parts/:id" element={<PartDetail />} />
              <Route path="/approvals" element={<Approvals />} />
              <Route path="/stocktakes" element={<StocktakeList />} />
              <Route path="/stocktakes/:id" element={<StocktakeDetail />} />
              <Route path="/servers" element={<Servers />} />
              <Route path="/locations" element={<Locations />} />
              <Route path="/allocatable" element={<AllocatableSummary />} />
              <Route path="/login" element={<Login />} />
            </Routes>
          </AuthGuard>
        </main>
      </div>
    </div>
  )
}
