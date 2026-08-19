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
import ServerDetail from './pages/ServerDetail'
import Brands from './pages/Brands'
import Suppliers from './pages/Suppliers'
import Locations from './pages/Locations'
import AllocatableSummary from './pages/AllocatableSummary'
import StocktakeList from './pages/StocktakeList'
import StocktakeDetail from './pages/StocktakeDetail'
import Login from './pages/Login'
import Register from './pages/Register'
import Users from './pages/Users'
import AssetCategories from './pages/AssetCategories'
import {
  ROLE_SUPPLIER,
  OPS_ROLES,
  INBOUND_ROLES,
  MASTER_DATA_ROLES,
} from './lib/roles'

const OPS = [...OPS_ROLES]
const INBOUND = [...INBOUND_ROLES]
const MASTER = [...MASTER_DATA_ROLES]
const SERVER_NAV = [...OPS_ROLES, ROLE_SUPPLIER]

const ALL_NAV_GROUPS = [
  {
    label: null,
    roles: OPS,
    items: [{ to: '/dashboard', label: '首页概览', icon: '▣' }],
  },
  {
    label: '总览与库位',
    roles: OPS,
    items: [
      { to: '/allocatable', label: '可调余量', icon: '📊' },
      { to: '/locations', label: '存放位置', icon: '📍' },
    ],
  },
  {
    label: '出入库与流转',
    roles: null,
    items: [
      { to: '/', label: '配件列表', icon: '📋', roles: OPS },
      { to: '/inbound', label: '分类入库', icon: '📥', roles: INBOUND },
      { to: '/approvals', label: '审批中心', icon: '✅', roles: OPS },
      { to: '/stocktakes', label: '盘点管理', icon: '🔍', roles: OPS },
      { to: '/devices', label: '设备管理', icon: '🖥', roles: SERVER_NAV },
    ],
  },
  {
    label: '基础数据',
    roles: MASTER,
    items: [
      { to: '/asset-categories', label: '资产类别管理', icon: '◈' },
      { to: '/part-models', label: '型号管理', icon: '⚙' },
      { to: '/brands', label: '品牌管理', icon: '🏷' },
      { to: '/suppliers', label: '供应商管理', icon: '🏭' },
      { to: '/users', label: '用户管理', icon: '👤' },
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
  const [user, setUser] = useState(() => getStoredUser())
  const nav = useNavigate()
  const [collapsed, setCollapsed] = useState({})
  const [mobileNavOpen, setMobileNavOpen] = useState(false)
  const location = useLocation()

  useEffect(() => {
    setMobileNavOpen(false)
  }, [location.pathname])

  // 启动/聚焦时刷新角色（以服务端为准）
  useEffect(() => {
    if (location.pathname === '/login' || location.pathname === '/register') return undefined
    if (!getToken()) return undefined
    let cancelled = false
    function refresh() {
      api.get('/auth/me')
        .then((me) => {
          if (cancelled) return
          const next = {
            user_id: me.user_id,
            name: me.name,
            username: me.username,
            role: me.role,
            is_super_admin: me.is_super_admin,
          }
          setStoredUser(next)
          setUser(next)
        })
        .catch(() => {
          /* 401 由 api 层清会话跳转 */
        })
    }
    refresh()
    const onFocus = () => refresh()
    window.addEventListener('focus', onFocus)
    return () => {
      cancelled = true
      window.removeEventListener('focus', onFocus)
    }
  }, [location.pathname])

  // 登录页不渲染侧边栏
  if (location.pathname === '/login' || location.pathname === '/register') {
    return (
      <Routes>
        <Route path="/login" element={<Login onLogin={setUser} />} />
        <Route path="/register" element={<Register />} />
      </Routes>
    )
  }

  // 未登录跳转
  if (!user || !getToken()) {
    return <Navigate to="/login" replace />
  }

  // 按角色过滤导航（组级 + 条目级）
  const role = user.role
  const navGroups = ALL_NAV_GROUPS
    .filter((g) => !g.roles || g.roles.includes(role))
    .map((g) => ({
      ...g,
      items: g.items.filter((item) => !item.roles || item.roles.includes(role)),
    }))
    .filter((g) => g.items.length > 0)

  function toggleGroup(gi) {
    setCollapsed((prev) => ({ ...prev, [gi]: !prev[gi] }))
  }

  function handleLogout() {
    clearToken()
    setUser(null)
    nav('/login', { replace: true })
  }

  const allItems = navGroups.flatMap((g) => g.items)
  const currentItem = allItems.find((i) => {
    if (i.to === '/') return location.pathname === '/'
    return location.pathname.startsWith(i.to)
  })

  return (
    <div className={`app-shell ${mobileNavOpen ? 'nav-open' : ''}`}>
      <button
        type="button"
        className="sidebar-scrim"
        aria-label="关闭导航"
        onClick={() => setMobileNavOpen(false)}
      />
      <aside className="sidebar" aria-label="主导航">
        <div className="sidebar-brand">
          <span className="brand-mark"><img src="/logo.webp" alt="" className="brand-logo" /></span>
          <span className="brand-copy">
            <strong>电网资产运营</strong>
            <small>ASSET OPERATIONS</small>
          </span>
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
            <button
              type="button"
              className="mobile-menu-btn"
              aria-label="打开导航"
              onClick={() => setMobileNavOpen(true)}
            >
              <span />
              <span />
              <span />
            </button>
            <span className="topbar-title">电网资产及其配件数字化运营系统</span>
            {currentItem && (
              <>
                <span className="topbar-sep">/</span>
                <span className="topbar-breadcrumb">{currentItem.label}</span>
              </>
            )}
          </div>
          <div className="topbar-right">
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
              <Route path="/asset-categories" element={<AssetCategories />} />
              <Route path="/brands" element={<Brands />} />
              <Route path="/users" element={<Users />} />
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
              <Route path="/devices" element={<Servers />} />
              <Route path="/devices/:id" element={<ServerDetail />} />
              <Route path="/servers" element={<Navigate to="/devices" replace />} />
              <Route path="/servers/:id" element={<Navigate to="/devices" replace />} />
              <Route path="/locations" element={<Locations />} />
              <Route path="/allocatable" element={<AllocatableSummary />} />
              <Route path="/login" element={<Login onLogin={setUser} />} />
            </Routes>
          </AuthGuard>
        </main>
      </div>
    </div>
  )
}
