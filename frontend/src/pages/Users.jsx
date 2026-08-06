import { useEffect, useState } from 'react'
import { api, getStoredUser } from '../api'

const ROLE_DESC = {
  领导: '全部权限（含审批、基础数据、用户管理）',
  主业运维: '入库/装机/借出/调拨/报废/盘点/可调余量（不可审批）',
  外委运维: '与主业运维权限对等（不可审批）',
  设备供应商: '分类入库（不可查看配件列表与可调余量）',
}
const ROLES = ['领导', '主业运维', '外委运维', '设备供应商']

const emptyForm = { name: '', username: '', password: '', role: '主业运维' }

export default function Users() {
  const me = getStoredUser()
  const [users, setUsers] = useState([])
  const [form, setForm] = useState(emptyForm)
  const [showCreate, setShowCreate] = useState(false)
  const [error, setError] = useState('')
  const [msg, setMsg] = useState('')
  const [busy, setBusy] = useState(false)

  function load() {
    return api.get('/auth/users').then(setUsers).catch((e) => setError(e.message))
  }

  useEffect(() => { load() }, [])

  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value })

  async function createUser(e) {
    e.preventDefault()
    setError('')
    setMsg('')
    setBusy(true)
    try {
      await api.post('/auth/users', form)
      setMsg(`已创建账号 ${form.username}（${form.role}），立即可登录`)
      setForm(emptyForm)
      setShowCreate(false)
      await load()
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  async function patchUser(u, patch, label) {
    setError('')
    setMsg('')
    try {
      await api.patch(`/auth/users/${u.id}`, patch)
      setMsg(label)
      await load()
    } catch (err) {
      setError(err.message)
    }
  }

  function changeRole(u, role) {
    if (role === u.role) return
    if (!window.confirm(`将 ${u.name}（${u.username}）的角色从「${u.role}」调整为「${role}」？`)) return
    patchUser(u, { role }, `${u.name} 角色已调整为「${role}」`)
  }

  function toggleStatus(u) {
    const next = u.status === '正常' ? '停用' : '正常'
    if (next === '停用' && !window.confirm(`确定停用 ${u.name}（${u.username}）？停用后立即无法登录。`)) return
    patchUser(u, { status: next }, `${u.name} 已${next}`)
  }

  return (
    <div className="panel">
      <h2>用户管理</h2>
      <p className="muted">
        领导可直接创建账号（立即生效，无需审批）或调整角色/停用。不能修改自己；系统至少保留一名在用的领导。
      </p>
      {error && <div className="error">{error}</div>}
      {msg && <div className="ok-msg">{msg}</div>}

      <div className="row-actions" style={{ marginBottom: '0.5rem' }}>
        <button type="button" onClick={() => setShowCreate((v) => !v)}>
          {showCreate ? '收起' : '+ 新增用户'}
        </button>
      </div>

      {showCreate && (
        <form onSubmit={createUser} className="fields-2col" style={{ maxWidth: '720px' }}>
          <label>
            姓名 *
            <input value={form.name} onChange={set('name')} required placeholder="真实姓名" />
          </label>
          <label>
            用户名（登录账号）*
            <input value={form.username} onChange={set('username')} required minLength={3} placeholder="字母/数字/下划线" />
          </label>
          <label>
            初始密码 *
            <input type="password" value={form.password} onChange={set('password')} required minLength={6} placeholder="至少 6 位" />
          </label>
          <label>
            角色 *
            <select value={form.role} onChange={set('role')}>
              {ROLES.map((r) => (
                <option key={r} value={r}>{r}（{ROLE_DESC[r]}）</option>
              ))}
            </select>
          </label>
          <div className="field-full">
            <button type="submit" disabled={busy}>{busy ? '创建中…' : '创建账号'}</button>
          </div>
        </form>
      )}

      <table>
        <thead>
          <tr>
            <th>姓名</th>
            <th>用户名</th>
            <th>角色</th>
            <th>状态</th>
            <th>来源</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          {users.map((u) => {
            const isSelf = u.id === me?.user_id
            return (
              <tr key={u.id}>
                <td>{u.name}{isSelf && <span className="muted">（本人）</span>}</td>
                <td>{u.username || '—'}</td>
                <td>
                  {isSelf ? (
                    <span className="badge warn">{u.role}</span>
                  ) : (
                    <select value={u.role} onChange={(e) => changeRole(u, e.target.value)}>
                      {ROLES.map((r) => (
                        <option key={r} value={r}>{r}</option>
                      ))}
                    </select>
                  )}
                </td>
                <td>
                  <span className={`badge ${u.status === '正常' ? 'ok' : 'danger'}`}>{u.status}</span>
                </td>
                <td className="muted">
                  {u.applied_role ? `自助注册（申请${u.applied_role}）` : '系统创建'}
                </td>
                <td>
                  {isSelf ? (
                    <span className="muted">—</span>
                  ) : u.status === '待审核' || u.status === '驳回' ? (
                    <span className="muted">注册审批中处理</span>
                  ) : (
                    <button type="button" className="secondary" onClick={() => toggleStatus(u)}>
                      {u.status === '正常' ? '停用' : '启用'}
                    </button>
                  )}
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
