import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api'

export default function Dashboard() {
  const nav = useNavigate()
  const [stats, setStats] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    Promise.all([
      api.get('/parts'),
      api.get('/approvals'),
      api.get('/stocktakes'),
    ])
      .then(([parts, approvals, stocktakes]) => {
        const statusCounts = {}
        for (const p of parts) {
          statusCounts[p.current_status] = (statusCounts[p.current_status] || 0) + 1
        }
        const pendingApprovals = approvals.filter((a) => a.overall_status === '审批中').length
        const activeStocktakes = stocktakes.filter((s) => s.status === '进行中').length

        setStats({
          total: parts.length,
          inStock: statusCounts['在库'] || 0,
          inUse: statusCounts['在用'] || 0,
          loaned: statusCounts['借出'] || 0,
          overdue: parts.filter((p) => p.is_overdue).length,
          pendingApprovals,
          activeStocktakes,
        })
      })
      .catch((e) => setError(e.message))
  }, [])

  const cards = stats
    ? [
        { label: '配件总数', value: stats.total, color: '#005a9c' },
        { label: '在库', value: stats.inStock, color: '#00695c', hint: '可装机 / 可借出' },
        { label: '在用', value: stats.inUse, color: '#0078c8', hint: '已安装到服务器' },
        { label: '借出', value: stats.loaned, color: '#e67e22', alert: stats.overdue > 0, alertHint: `${stats.overdue} 件超期` },
        { label: '待审批', value: stats.pendingApprovals, color: '#8e44ad', hint: '审批中的借出单' },
        { label: '盘点中', value: stats.activeStocktakes, color: '#2c3e50', hint: '进行中的盘点任务' },
      ]
    : []

  return (
    <div>
      <h2 className="page-title">首页概览</h2>
      <p className="muted">配件资产实时状态一览，快速掌握库存、流转与待办。</p>
      {error && <div className="error">{error}</div>}

      <div className="stat-grid">
        {cards.map((c) => (
          <div
            key={c.label}
            className={`stat-card ${c.alert ? 'alert' : ''}`}
            style={{ borderTopColor: c.color }}
          >
            <div className="stat-value">{c.value}</div>
            <div className="stat-label">{c.label}</div>
            {c.alert && c.alertHint && (
              <div className="stat-alert">{c.alertHint}</div>
            )}
            {c.hint && !c.alert && <div className="stat-hint">{c.hint}</div>}
          </div>
        ))}
      </div>

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
          <span className="muted">{stats ? `${stats.pendingApprovals} 单待审` : '处理借出审批'}</span>
        </button>
        <button type="button" className="action-card" onClick={() => nav('/allocatable')}>
          <span className="action-icon">📊</span>
          <strong>可调余量</strong>
          <span className="muted">本单位通用可调库存聚合</span>
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
