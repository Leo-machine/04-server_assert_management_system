import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api, getStoredUser, getToken, setStoredUser, setToken } from '../api'
import { homePathFor } from '../lib/roles'

const DEMO_ACCOUNTS = [
  { user: 'qiancg', tip: '设备供应商 · 仅入库' },
  { user: 'wawei', tip: '外委运维 · 与主业权限对等（不可审批）' },
  { user: 'zhangyw', tip: '主业运维 · 流转/盘点（不可审批）' },
  { user: 'admin', tip: '领导 · 全部权限含审批' },
]

export default function Login() {
  const nav = useNavigate()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    const u = getStoredUser()
    if (u && getToken()) {
      nav(homePathFor(u), { replace: true })
    }
  }, [nav])

  async function onSubmit(e) {
    e.preventDefault()
    setError('')
    setBusy(true)
    try {
      const data = await api.post('/auth/login', { username: username.trim(), password })
      setToken(data.token)
      const user = {
        user_id: data.user_id,
        username: data.username,
        name: data.name,
        role: data.role,
      }
      setStoredUser(user)
      nav(homePathFor(user), { replace: true })
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="login-page">
      <div className="login-showcase">
        <div className="login-showcase-brand">
          <span className="login-showcase-mark"><img src="/logo.webp" alt="" /></span>
          <span>数字化资产运营平台</span>
        </div>
        <div className="login-showcase-content">
          <p className="login-eyebrow">ASSET OPERATIONS</p>
          <h2>让每一件配件<br />都可查、可控、可追溯</h2>
          <p>一体化管理入库、装机、调拨、审批与盘点，统一资产口径，提升运维效率。</p>
        </div>
        <div className="login-showcase-foot">资产全生命周期管理 · 履历全程留痕</div>
      </div>
      <div className="login-card-wrap">
      <div className="login-card">
        <div className="login-brand">
          <img src="/logo.webp" alt="Logo" className="login-logo" />
          <h1>服务器配件资产管理系统</h1>
          <p>欢迎回来，请登录您的账号</p>
        </div>
        <form onSubmit={onSubmit}>
          {error && <div className="error">{error}</div>}
          <label>
            用户名
            <input
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              required
              placeholder="zhangyw 或 张运维"
              autoFocus
            />
          </label>
          <label>
            密码
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              placeholder="123456"
            />
          </label>
          <button type="submit" disabled={busy}>
            {busy ? '正在验证…' : '登录系统'}
          </button>
        </form>
        <p className="muted" style={{ textAlign: 'center' }}>
          没有账号？<Link to="/register">注册新账号（需领导审批）</Link>
        </p>
        <div className="login-hint muted">
          <p>演示账号（密码均为 123456）：</p>
          <ul>
            {DEMO_ACCOUNTS.map((a) => (
              <li key={a.user}>
                <button
                  type="button"
                  className="linkish"
                  onClick={() => {
                    setUsername(a.user)
                    setPassword('123456')
                  }}
                >
                  {a.user}
                </button>
                {' — '}
                {a.tip}
              </li>
            ))}
          </ul>
        </div>
      </div>
      </div>
    </div>
  )
}
