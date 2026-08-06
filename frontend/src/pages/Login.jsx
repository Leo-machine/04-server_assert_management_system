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
      <div className="login-card">
        <div className="login-brand">
          <img src="/logo.webp" alt="Logo" className="login-logo" />
          <h1>服务器配件资产管理系统</h1>
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
            {busy ? '登录中…' : '登 录'}
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
  )
}
