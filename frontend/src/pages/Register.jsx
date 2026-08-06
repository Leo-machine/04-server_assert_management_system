import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api } from '../api'

const ROLE_OPTIONS = [
  { value: '主业运维', desc: '入库/装机/借出/调拨/报废/盘点（不可审批）' },
  { value: '外委运维', desc: '与主业运维权限对等（不可审批）' },
  { value: '设备供应商', desc: '仅分类入库' },
]

export default function Register() {
  const nav = useNavigate()
  const [form, setForm] = useState({
    name: '',
    username: '',
    password: '',
    confirm: '',
    applied_role: '主业运维',
    apply_reason: '',
  })
  const [error, setError] = useState('')
  const [done, setDone] = useState(false)
  const [busy, setBusy] = useState(false)

  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value })

  async function onSubmit(e) {
    e.preventDefault()
    setError('')
    if (form.password !== form.confirm) {
      setError('两次输入的密码不一致')
      return
    }
    setBusy(true)
    try {
      await api.post('/auth/register', {
        username: form.username.trim(),
        password: form.password,
        name: form.name.trim(),
        applied_role: form.applied_role,
        apply_reason: form.apply_reason.trim(),
      })
      setDone(true)
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  if (done) {
    return (
      <div className="login-page">
        <div className="login-card">
          <div className="login-brand">
            <img src="/logo.webp" alt="Logo" className="login-logo" />
            <h1>注册申请已提交</h1>
          </div>
          <div className="ok-msg">
            你的账号「{form.username}」已提交审批（申请角色：{form.applied_role}）。
            领导在「审批中心 → 注册审批」通过后，即可登录使用。
          </div>
          <button type="button" onClick={() => nav('/login', { replace: true })}>
            返回登录
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="login-page">
      <div className="login-card">
        <div className="login-brand">
          <img src="/logo.webp" alt="Logo" className="login-logo" />
          <h1>注册新账号</h1>
        </div>
        <p className="muted" style={{ marginTop: 0 }}>
          提交后需经领导审批通过方可登录；角色权限按审批结果生效。
        </p>
        <form onSubmit={onSubmit}>
          {error && <div className="error">{error}</div>}
          <label>
            姓名
            <input value={form.name} onChange={set('name')} required placeholder="真实姓名" autoFocus />
          </label>
          <label>
            用户名（登录账号）
            <input
              value={form.username}
              onChange={set('username')}
              required
              minLength={3}
              placeholder="字母/数字/下划线，至少 3 位"
            />
          </label>
          <label>
            密码
            <input type="password" value={form.password} onChange={set('password')} required minLength={6} placeholder="至少 6 位" />
          </label>
          <label>
            确认密码
            <input type="password" value={form.confirm} onChange={set('confirm')} required placeholder="再次输入密码" />
          </label>
          <label>
            申请角色
            <select value={form.applied_role} onChange={set('applied_role')}>
              {ROLE_OPTIONS.map((r) => (
                <option key={r.value} value={r.value}>
                  {r.value}（{r.desc}）
                </option>
              ))}
            </select>
          </label>
          <label>
            申请理由
            <textarea
              value={form.apply_reason}
              onChange={set('apply_reason')}
              rows={2}
              required
              placeholder="如：新入职，负责备件调配工作"
            />
          </label>
          <button type="submit" disabled={busy}>
            {busy ? '提交中…' : '提交注册申请'}
          </button>
        </form>
        <p className="muted" style={{ textAlign: 'center' }}>
          已有账号？<Link to="/login">直接登录</Link>
        </p>
      </div>
    </div>
  )
}
