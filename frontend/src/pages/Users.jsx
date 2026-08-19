import { useEffect, useMemo, useState } from 'react'
import { api, getStoredUser } from '../api'
import ListToolbar from '../components/ListToolbar'
import Pagination from '../components/Pagination'
import { usePagination } from '../hooks/usePagination'
import { filterByQuery } from '../lib/fuzzy'

const ROLE_DESC = {
  领导: '全部权限，含审批、基础数据和用户管理',
  主业运维: '入库、装机、借出、调拨、报废、盘点和可调余量',
  外委运维: '与主业运维权限对等，不可审批',
  设备供应商: '分类入库，不可查看配件列表和可调余量',
}
const ROLES = Object.keys(ROLE_DESC)
const emptyCreate = { name: '', username: '', password: '', role: '主业运维' }

export default function Users() {
  const me = getStoredUser()
  const [users, setUsers] = useState([])
  const [createForm, setCreateForm] = useState(emptyCreate)
  const [editForm, setEditForm] = useState(null)
  const [showCreate, setShowCreate] = useState(false)
  const [error, setError] = useState('')
  const [msg, setMsg] = useState('')
  const [busy, setBusy] = useState(false)
  const [query, setQuery] = useState('')
  const [roleFilter, setRoleFilter] = useState('')
  const [statusFilter, setStatusFilter] = useState('')

  function load() { return api.get('/auth/users').then(setUsers).catch((e) => setError(e.message)) }
  useEffect(() => { load() }, [])

  const stats = useMemo(() => ({
    active: users.filter((user) => user.status === '正常').length,
    disabled: users.filter((user) => user.status === '停用').length,
    pending: users.filter((user) => user.status === '待审核').length,
    leaders: users.filter((user) => user.role === '领导' && user.status === '正常').length,
  }), [users])
  const visibleUsers = useMemo(() => {
    const scoped = users.filter((user) => (!roleFilter || user.role === roleFilter) && (!statusFilter || user.status === statusFilter))
    return filterByQuery(scoped, query, (user) => [user.name, user.username, user.role, user.status, user.applied_role])
  }, [query, roleFilter, statusFilter, users])
  const pagination = usePagination(visibleUsers)

  function closeCreate() { setShowCreate(false); setCreateForm(emptyCreate) }
  function openEdit(user) { setEditForm({ id: user.id, username: user.username, name: user.name, role: user.role, password: '' }); setError(''); setMsg('') }

  async function createUser(event) {
    event.preventDefault(); setError(''); setMsg(''); setBusy(true)
    try { await api.post('/auth/users', createForm); setMsg(`已创建账号 ${createForm.username}（${createForm.role}）`); await load(); closeCreate() }
    catch (err) { setError(err.message) }
    finally { setBusy(false) }
  }

  async function saveUser(event) {
    event.preventDefault(); setError(''); setMsg(''); setBusy(true)
    const body = { name: editForm.name, role: editForm.role }
    if (editForm.password) body.password = editForm.password
    try { await api.patch(`/auth/users/${editForm.id}`, body); setMsg(`已更新用户「${editForm.name}」`); await load(); setEditForm(null) }
    catch (err) { setError(err.message) }
    finally { setBusy(false) }
  }

  async function toggleStatus(user) {
    const next = user.status === '正常' ? '停用' : '正常'
    if (next === '停用' && !window.confirm(`确定停用 ${user.name}（${user.username}）？停用后立即无法登录。`)) return
    setError(''); setMsg('')
    try { await api.patch(`/auth/users/${user.id}`, { status: next }); setMsg(`${user.name} 已${next}`); await load() }
    catch (err) { setError(err.message) }
  }

  return (
    <div className="panel user-workbench">
      <header className="user-header"><div><span className="user-kicker">系统权限 · USER & ACCESS</span><h2>用户管理</h2><p className="muted">统一管理系统账号、角色权限、账号状态和密码重置。</p></div><button type="button" className="user-add-button" onClick={() => setShowCreate(true)}>+ 新增用户</button></header>
      {error && <div className="error">{error}</div>}{msg && <div className="ok-msg">{msg}</div>}
      <section className="user-stats"><button type="button" className={!statusFilter ? 'active' : ''} onClick={() => setStatusFilter('')}><span>▣</span><p><strong>{users.length}</strong><small>用户总数</small></p></button><button type="button" className={statusFilter === '正常' ? 'active' : ''} onClick={() => setStatusFilter('正常')}><span className="is-active">✓</span><p><strong>{stats.active}</strong><small>正常账号</small></p></button><button type="button" className={statusFilter === '停用' ? 'active' : ''} onClick={() => setStatusFilter('停用')}><span className="is-disabled">×</span><p><strong>{stats.disabled}</strong><small>停用账号</small></p></button><button type="button" className={statusFilter === '待审核' ? 'active' : ''} onClick={() => setStatusFilter('待审核')}><span className="is-pending">!</span><p><strong>{stats.pending}</strong><small>待审核</small></p></button><div><span className="is-leader">◆</span><p><strong>{stats.leaders}</strong><small>在用领导</small></p></div></section>

      <section className="user-role-browser"><div className="user-section-head"><div><span>01</span><h3>按角色筛选</h3></div><p>角色决定菜单、业务操作和审批权限</p></div><div className="user-role-cards"><button type="button" className={!roleFilter ? 'active' : ''} onClick={() => setRoleFilter('')}><span>全</span><div><strong>全部角色</strong><small>{users.length} 人</small></div></button>{ROLES.map((role) => <button key={role} type="button" className={roleFilter === role ? 'active' : ''} onClick={() => setRoleFilter(role)}><span>{role.slice(0, 1)}</span><div><strong>{role}</strong><small>{users.filter((user) => user.role === role).length} 人</small></div></button>)}</div></section>

      <section className="user-list-card"><div className="user-section-head"><div><span>02</span><h3>{roleFilter ? `${roleFilter}用户` : '全部系统用户'}</h3></div><p>账号停用代替物理删除，以保留历史审计记录</p></div><ListToolbar query={query} onQueryChange={setQuery} placeholder="搜索姓名 / 用户名 / 角色 / 状态…" resultText={<> 显示 <strong>{visibleUsers.length}</strong> / {users.length}</>} />
        <div className="user-table-wrap"><table className="user-table"><thead><tr><th>用户</th><th>登录账号</th><th>角色权限</th><th>账号状态</th><th>账号来源</th><th>操作</th></tr></thead><tbody>{pagination.pageItems.map((user) => {
          const isSelf = user.id === me?.user_id
          return <tr key={user.id}><td><div className="user-name-cell"><span>{user.name.slice(0, 1)}</span><div><strong>{user.name}{isSelf && <em>本人</em>}{user.is_super_admin && <em className="is-super-admin">超级管理员</em>}</strong><small>用户编号 #{user.id}</small></div></div></td><td><code>{user.username || '—'}</code></td><td><span className={`user-role-badge role-${ROLES.indexOf(user.role)}`}>{user.role}</span></td><td><span className={`user-status-badge ${user.status === '正常' ? 'is-active' : user.status === '停用' ? 'is-disabled' : 'is-pending'}`}><i />{user.status}</span></td><td><div className="user-source"><strong>{user.applied_role ? '自助注册' : '系统创建'}</strong><small>{user.is_super_admin ? '系统内置 · 业务免审批' : user.applied_role ? `申请角色：${user.applied_role}` : '管理员直接建立'}</small></div></td><td>{isSelf ? <span className="user-self-tip">请在个人账号中维护</span> : user.status === '待审核' || user.status === '驳回' ? <span className="user-self-tip">请在审批中心处理</span> : <div className="row-actions user-row-actions"><button type="button" className="secondary" onClick={() => openEdit(user)}>编辑</button><button type="button" className={`secondary ${user.status === '正常' ? 'danger-outline' : ''}`} onClick={() => toggleStatus(user)}>{user.status === '正常' ? '停用' : '启用'}</button></div>}</td></tr>
        })}{!visibleUsers.length && <tr><td colSpan={6}><div className="user-empty"><span>◇</span><strong>暂无匹配用户</strong></div></td></tr>}</tbody></table></div><Pagination pagination={pagination} />
      </section>

      {showCreate && <div className="user-modal-overlay" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) closeCreate() }}><form className="user-modal" onSubmit={createUser}><div className="user-modal-head"><div><span>新增账号</span><h3>建立系统用户</h3></div><button type="button" onClick={closeCreate} aria-label="关闭">×</button></div><div className="user-form-grid"><label>姓名 *<input value={createForm.name} onChange={(e) => setCreateForm({ ...createForm, name: e.target.value })} required autoFocus placeholder="真实姓名" /></label><label>用户名 *<input value={createForm.username} onChange={(e) => setCreateForm({ ...createForm, username: e.target.value })} required minLength={3} placeholder="字母、数字、下划线" /></label><label>初始密码 *<input type="password" value={createForm.password} onChange={(e) => setCreateForm({ ...createForm, password: e.target.value })} required minLength={6} placeholder="至少 6 位" /></label><label>用户角色 *<select value={createForm.role} onChange={(e) => setCreateForm({ ...createForm, role: e.target.value })}>{ROLES.map((role) => <option key={role}>{role}</option>)}</select></label></div><div className="user-role-description"><strong>{createForm.role}</strong><span>{ROLE_DESC[createForm.role]}</span></div><div className="user-modal-actions"><button type="button" className="secondary" onClick={closeCreate}>取消</button><button type="submit" disabled={busy}>{busy ? '创建中…' : '创建账号'}</button></div></form></div>}

      {editForm && <div className="user-modal-overlay" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) setEditForm(null) }}><form className="user-modal" onSubmit={saveUser}><div className="user-modal-head"><div><span>编辑账号</span><h3>{editForm.username}</h3></div><button type="button" onClick={() => setEditForm(null)} aria-label="关闭">×</button></div><div className="user-form-grid"><label>姓名 *<input value={editForm.name} onChange={(e) => setEditForm({ ...editForm, name: e.target.value })} required autoFocus /></label><label>用户角色 *<select value={editForm.role} onChange={(e) => setEditForm({ ...editForm, role: e.target.value })}>{ROLES.map((role) => <option key={role}>{role}</option>)}</select></label><label className="field-full">重置密码<input type="password" value={editForm.password} onChange={(e) => setEditForm({ ...editForm, password: e.target.value })} minLength={6} placeholder="不修改请留空；新密码至少 6 位" /></label></div><div className="user-role-description"><strong>{editForm.role}</strong><span>{ROLE_DESC[editForm.role]}</span></div><div className="user-modal-actions"><button type="button" className="secondary" onClick={() => setEditForm(null)}>取消</button><button type="submit" disabled={busy}>{busy ? '保存中…' : '保存修改'}</button></div></form></div>}
    </div>
  )
}
