import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api, getStoredUser, getToken, setStoredUser, setToken } from '../api'

const DEMO_ACCOUNTS = [
  { user: 'zhangyw', tip: '操作员 · 日常流转' },
  { user: 'lizz', tip: '审批人 · 一级审批/盘点' },
  { user: 'admin', tip: '管理员 · 基础数据' },
]

export default function Login() {
  const nav = useNavigate()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    if (getStoredUser() && getToken()) {
      nav('/dashboard', { replace: true })
    }
  }, [nav])

  async function onSubmit(e) {
    e.preventDefault()
    setError('')
    setBusy(true)
    try {
      const data = await api.post('/auth/login', { username: username.trim(), password })
      setToken(data.token)
      setStoredUser({
        user_id: data.user_id,
        username: data.username,
        name: data.name,
        role: data.role,
      })
      nav('/dashboard', { replace: true })
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
