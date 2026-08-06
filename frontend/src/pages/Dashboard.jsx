import { useEffect, useState } from 'react'
import { Navigate, useNavigate } from 'react-router-dom'
import { api, getStoredUser } from '../api'
import { homePathFor, isSupplier } from '../lib/roles'

const HOME_OWNER_UNIT = '本单位信息中心'

export default function Dashboard() {
  const nav = useNavigate()
  const me = getStoredUser()
  const [stats, setStats] = useState(null)
  const [error, setError] = useState('')
  const supplier = isSupplier(me)

  useEffect(() => {
    if (supplier) return undefined
    Promise.all([
      api.get('/parts'),
      api.get('/approvals'),
      api.get('/stocktakes'),
    ])
      .then(([parts, approvals, stocktakes]) => {
        const statusCounts = {}
        const byCategory = {}
        let occupied = 0
        let general = 0
        let reserved = 0

        for (const p of parts) {
          statusCounts[p.current_status] = (statusCounts[p.current_status] || 0) + 1
          if (p.current_status !== '在库') {
            occupied += 1
            continue
          }
          // 与 GET /inventory/allocatable-summary 同口径
          const isAlloc =
            p.owner_unit === HOME_OWNER_UNIT && p.allocatable_flag === '通用可调'
          if (isAlloc) general += 1
          else reserved += 1

          const cat = p.model?.category || '未分类'
          if (!byCategory[cat]) byCategory[cat] = { total: 0, general: 0, reserved: 0 }
          byCategory[cat].total += 1
          if (isAlloc) byCategory[cat].general += 1
          else byCategory[cat].reserved += 1
        }

        setStats({
          total: parts.length,
          inStock: statusCounts['在库'] || 0,
          inUse: statusCounts['在用'] || 0,
          loaned: statusCounts['借出'] || 0,
          overdue: parts.filter((p) => p.is_overdue).length,
          pendingApprovals: approvals.filter((a) => a.overall_status === '审批中').length,
          activeStocktakes: stocktakes.filter((s) => s.status === '进行中').length,
          alloc: { general, reserved, occupied },
          byCategory,
        })
      })
      .catch((e) => setError(e.message))
  }, [supplier])

  if (supplier) {
    return <Navigate to={homePathFor(me)} replace />
  }

  return (
    <div>
      <h2 className="page-title">首页概览</h2>
      <p className="muted">配件资产实时状态一览，快速掌握库存、可调余量与待办事项。</p>
      {error && <div className="error">{error}</div>}

      <h3 style={{ marginTop: '1.25rem', color: '#003e7e' }}>资产状态</h3>
      <div className="stat-grid">
        {stats && [
          { label: '配件总数', value: stats.total, color: '#005a9c' },
          { label: '在库', value: stats.inStock, color: '#00695c', hint: '可装机 / 可借出' },
          { label: '在用', value: stats.inUse, color: '#0078c8', hint: '已安装到服务器' },
          { label: '借出', value: stats.loaned, color: '#e67e22', alert: stats.overdue > 0, alertHint: stats.overdue ? `${stats.overdue} 件超期` : '' },
          { label: '待审批', value: stats.pendingApprovals, color: '#8e44ad', hint: '审批中的借出/调拨/报废单' },
          { label: '盘点中', value: stats.activeStocktakes, color: '#2c3e50', hint: '进行中的盘点任务' },
        ].map((c) => (
          <div
            key={c.label}
            className={`stat-card ${c.alert ? 'alert' : ''}`}
            style={{ borderTopColor: c.color }}
          >
            <div className="stat-value">{c.value}</div>
            <div className="stat-label">{c.label}</div>
            {c.alert && c.alertHint && <div className="stat-alert">{c.alertHint}</div>}
            {c.hint && !c.alert && <div className="stat-hint">{c.hint}</div>}
          </div>
        ))}
      </div>

      <h3 style={{ marginTop: '1.5rem', color: '#003e7e' }}>可调余量</h3>
      <p className="muted">
        口径与接口一致：在库 ∩ {HOME_OWNER_UNIT} ∩ 通用可调。
        按规格细分见「可调余量」页（当前支持内存）。
      </p>
      <div className="stat-grid">
        {stats && [
          { label: '在库总量', value: stats.inStock, color: '#005a9c', hint: '库房中所有配件' },
          { label: '通用可调', value: stats.alloc.general, color: '#0f766e', hint: '本单位可自由调配' },
          { label: '保留/其他', value: stats.alloc.reserved, color: '#c2410c', hint: '保留标记或非本单位产权' },
          { label: '已占用', value: stats.alloc.occupied, color: '#64748b', hint: '在用/借出/损坏/报废等' },
        ].map((c) => (
          <div
            key={c.label}
            className="stat-card"
            style={{ borderTopColor: c.color }}
          >
            <div className="stat-value">{c.value}</div>
            <div className="stat-label">{c.label}</div>
            <div className="stat-hint">{c.hint}</div>
          </div>
        ))}
      </div>

      {stats && stats.inStock > 0 && (
        <div className="alloc-bar-wrap">
          <div className="alloc-bar">
            <div
              className="alloc-bar-seg alloc-bar-general"
              style={{ flex: Math.max(stats.alloc.general, 0.001) }}
              title={`通用可调 ${stats.alloc.general}`}
            />
            <div
              className="alloc-bar-seg alloc-bar-reserved"
              style={{ flex: Math.max(stats.alloc.reserved, 0.001) }}
              title={`保留/其他 ${stats.alloc.reserved}`}
            />
          </div>
          <div className="alloc-bar-legend">
            <span><i className="dot-general" />通用可调 {stats.alloc.general}</span>
            <span><i className="dot-reserved" />保留/其他 {stats.alloc.reserved}</span>
          </div>
        </div>
      )}

      {stats && Object.keys(stats.byCategory).length > 0 && (
        <>
          <h3 style={{ marginTop: '1.5rem', color: '#003e7e' }}>在库配件分类明细</h3>
          <div className="cat-breakdown">
            <table>
              <thead>
                <tr>
                  <th>配件类型</th>
                  <th>在库</th>
                  <th>通用可调</th>
                  <th>保留/其他</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(stats.byCategory)
                  .filter(([, c]) => c.total > 0)
                  .sort((a, b) => b[1].total - a[1].total)
                  .map(([cat, c]) => (
                    <tr key={cat}>
                      <td><strong>{cat}</strong></td>
                      <td><span className="badge">{c.total}</span></td>
                      <td><span className="badge ok">{c.general}</span></td>
                      <td><span className="badge warn">{c.reserved}</span></td>
                    </tr>
                  ))}
              </tbody>
            </table>
          </div>
        </>
      )}

      <h3 style={{ marginTop: '1.5rem', color: '#003e7e' }}>快捷操作</h3>
      <div className="quick-actions">
        <button type="button" className="action-card" onClick={() => nav('/inbound')}>
          <span className="action-icon">📥</span>
          <strong>分类入库</strong>
          <span className="muted">按配件类型入库登记</span>
        </button>
        <button type="button" className="action-card" onClick={() => nav('/')}>
          <span className="action-icon">📋</span>
          <strong>配件列表</strong>
          <span className="muted">查看和管理所有配件</span>
        </button>
        <button type="button" className="action-card" onClick={() => nav('/approvals')}>
          <span className="action-icon">✅</span>
          <strong>审批中心</strong>
          <span className="muted">{stats ? `${stats.pendingApprovals} 单待审` : '处理借出/调拨/报废审批'}</span>
        </button>
        <button type="button" className="action-card" onClick={() => nav('/stocktakes')}>
          <span className="action-icon">🔍</span>
          <strong>盘点管理</strong>
          <span className="muted">{stats ? `${stats.activeStocktakes} 个进行中` : '发起或查看盘点'}</span>
        </button>
      </div>
    </div>
  )
}
