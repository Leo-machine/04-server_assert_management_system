import { useEffect, useMemo, useState } from 'react'
import { api, getStoredUser } from '../api'
import ListToolbar from '../components/ListToolbar'
import ImportWizard from '../components/ImportWizard'
import { useSelection } from '../hooks/useSelection'
import { filterByQuery } from '../lib/fuzzy'

const EMPTY_FORM = {
  asset_no: '',
  model: '',
  serial_no: '',
  room: '',
  rack: '',
  u_position: '',
  responsible_group: '基础组',
  supplier: '',
  contract_no: '',
  project: '',
  owner_unit: '本单位信息中心',
  warranty_expiry: '',
  arrival_date: '',
  purchase_amount: '',
  run_status: '未投运',
}

const GROUPS = ['基础组', '运营组', '网络组', '平台组']

function ServerForm({ initial, onSubmit, onCancel, busy, title, suppliers, serverModels }) {
  const [form, setForm] = useState(initial)
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value })
  return (
    <form
      className="panel"
      style={{ marginTop: '0.75rem' }}
      onSubmit={(e) => {
        e.preventDefault()
        onSubmit(form)
      }}
    >
      <h3>{title}</h3>
      <fieldset className="fields-2col">
        <legend>基本信息</legend>
        <label>
          资产编号 *
          <input value={form.asset_no} onChange={set('asset_no')} required />
        </label>
        <label>
          型号
          <select value={form.model || ''} onChange={set('model')}>
            <option value="">— 请选择 —</option>
            {serverModels.map((m) => (
              <option key={m.id} value={m.model_name}>
                {m.brand ? `${m.brand} · ` : ''}{m.model_name}
              </option>
            ))}
          </select>
          {!serverModels.length && (
            <span className="muted"> 暂无服务器型号，请先到「型号管理」新增（类型选「服务器」）</span>
          )}
        </label>
        <label>
          SN
          <input value={form.serial_no || ''} onChange={set('serial_no')} />
        </label>
        <label>
          机房
          <input value={form.room || ''} onChange={set('room')} />
        </label>
        <label>
          机柜
          <input value={form.rack || ''} onChange={set('rack')} />
        </label>
        <label>
          U 位
          <input value={form.u_position || ''} onChange={set('u_position')} />
        </label>
        <label>
          运维部门
          <select value={form.responsible_group || '基础组'} onChange={set('responsible_group')}>
            {GROUPS.map((g) => (
              <option key={g}>{g}</option>
            ))}
          </select>
        </label>
        {'run_status' in form && (
          <label>
            运行状态
            <select value={form.run_status} onChange={set('run_status')}>
              <option>未投运</option>
              <option>投运</option>
            </select>
          </label>
        )}
      </fieldset>
      <fieldset className="fields-2col">
        <legend>合同与采购</legend>
        <label>
          供应商
          <select value={form.supplier || ''} onChange={set('supplier')}>
            <option value="">— 请选择 —</option>
            {suppliers.map((s) => (
              <option key={s.id} value={s.name}>{s.name}</option>
            ))}
          </select>
        </label>
        <label>
          合同号
          <input value={form.contract_no || ''} onChange={set('contract_no')} />
        </label>
        <label>
          所属项目
          <input value={form.project || ''} onChange={set('project')} />
        </label>
        <label>
          产权单位
          <input value={form.owner_unit || ''} onChange={set('owner_unit')} />
        </label>
        <label>
          维保到位时间
          <input type="date" value={form.warranty_expiry || ''} onChange={set('warranty_expiry')} />
        </label>
        <label>
          设备到货日期
          <input type="date" value={form.arrival_date || ''} onChange={set('arrival_date')} />
        </label>
        <label>
          采购金额
          <input
            type="number"
            min="0"
            step="0.01"
            value={form.purchase_amount || ''}
            onChange={set('purchase_amount')}
          />
        </label>
      </fieldset>
      <div className="row-actions">
        <button type="submit" disabled={busy}>{busy ? '提交中…' : '保存'}</button>
        <button type="button" className="secondary" onClick={onCancel}>取消</button>
      </div>
    </form>
  )
}

export default function Servers() {
  const me = getStoredUser()
  const isAdmin = me?.role === '管理员'
  const [servers, setServers] = useState([])
  const [suppliers, setSuppliers] = useState([])
  const [serverModels, setServerModels] = useState([])
  const [error, setError] = useState('')
  const [msg, setMsg] = useState('')
  const [query, setQuery] = useState('')
  const [batchBusy, setBatchBusy] = useState(false)
  const [showCreate, setShowCreate] = useState(false)
  const [editing, setEditing] = useState(null) // server object
  const [showImport, setShowImport] = useState(false)
  const [busy, setBusy] = useState(false)

  function load() {
    return api.get('/servers').then(setServers).catch((e) => setError(e.message))
  }

  useEffect(() => {
    load()
    api.get('/suppliers').then(setSuppliers).catch(() => {})
    api.get('/part-models?category=' + encodeURIComponent('服务器')).then(setServerModels).catch(() => {})
  }, [])

  const visible = useMemo(
    () =>
      filterByQuery(servers, query, (s) => [
        s.asset_no,
        s.model,
        s.room,
        s.rack,
        s.u_position,
        s.run_status,
        s.responsible_group,
        s.contract_no,
        s.supplier,
        s.project,
      ]),
    [servers, query],
  )
  const visibleIds = useMemo(() => visible.map((s) => s.id), [visible])
  const sel = useSelection(visibleIds)

  async function toggle(server) {
    setError('')
    setMsg('')
    const next = server.run_status === '投运' ? '未投运' : '投运'
    try {
      await api.patch(`/servers/${server.id}/run-status`, { run_status: next })
      setMsg(`${server.asset_no} → ${next}`)
      await load()
    } catch (err) {
      setError(err.message)
    }
  }

  async function batchSetStatus(run_status) {
    const targets = visible.filter(
      (s) => sel.isSelected(s.id) && s.run_status !== '退役' && s.run_status !== run_status,
    )
    if (!targets.length) {
      setError(`所选服务器中没有可切换为「${run_status}」的项`)
      return
    }
    if (!window.confirm(`将 ${targets.length} 台服务器设为「${run_status}」？`)) return
    setBatchBusy(true)
    setError('')
    setMsg('')
    let okN = 0
    const errors = []
    for (const s of targets) {
      try {
        await api.patch(`/servers/${s.id}/run-status`, { run_status })
        okN += 1
      } catch (e) {
        errors.push(`${s.asset_no}: ${e.message}`)
      }
    }
    await load()
    sel.clear()
    setBatchBusy(false)
    if (errors.length) setError(errors.slice(0, 3).join('；'))
    if (okN) setMsg(`已更新 ${okN} 台 → ${run_status}`)
  }

  async function submitCreate(form) {
    setBusy(true)
    setError('')
    try {
      await api.post('/servers', {
        ...form,
        purchase_amount: form.purchase_amount ? Number(form.purchase_amount) : null,
      })
      setShowCreate(false)
      setMsg(`服务器 ${form.asset_no} 已创建`)
      await load()
    } catch (e) {
      setError(e.message)
    } finally {
      setBusy(false)
    }
  }

  async function submitEdit(form) {
    setBusy(true)
    setError('')
    try {
      await api.put(`/servers/${editing.id}`, {
        ...form,
        purchase_amount: form.purchase_amount ? Number(form.purchase_amount) : null,
        run_status: undefined, // 运行状态走切换按钮，避免误改
      })
      setEditing(null)
      setMsg(`服务器 ${form.asset_no} 已更新`)
      await load()
    } catch (e) {
      setError(e.message)
    } finally {
      setBusy(false)
    }
  }

  async function remove(server) {
    if (!window.confirm(`确认删除服务器 ${server.asset_no}？（有配件安装关系的会被拦截）`)) return
    setError('')
    setMsg('')
    try {
      await api.delete(`/servers/${server.id}`)
      setMsg(`${server.asset_no} 已删除`)
      await load()
    } catch (e) {
      setError(e.message)
    }
  }

  return (
    <div className="panel">
      <h2>服务器管理</h2>
      <p className="muted">
        维护服务器信息与合同采购信息（供「服务器原装」入库自动带出）；可在「未投运 / 投运」间切换。
      </p>
      {error && <div className="error">{error}</div>}
      {msg && <div className="ok-msg">{msg}</div>}

      <ListToolbar
        query={query}
        onQueryChange={(q) => {
          setQuery(q)
          sel.clear()
        }}
        placeholder="搜索资产编号 / 型号 / 合同号 / 供应商…"
        resultText={
          <>
            显示 <strong>{visible.length}</strong> / {servers.length}
          </>
        }
        selectedCount={sel.selectedCount}
        onClearSelection={sel.clear}
        batchActions={
          <>
            <button type="button" disabled={batchBusy} onClick={() => batchSetStatus('投运')}>
              批量·投运
            </button>
            <button
              type="button"
              className="secondary"
              disabled={batchBusy}
              onClick={() => batchSetStatus('未投运')}
            >
              批量·未投运
            </button>
          </>
        }
      />

      {isAdmin && (
        <div className="row-actions" style={{ marginBottom: '0.5rem' }}>
          <button type="button" onClick={() => { setShowCreate(true); setEditing(null); setShowImport(false) }}>
            + 新增服务器
          </button>
          <button
            type="button"
            className="secondary"
            onClick={() => { setShowImport((v) => !v); setShowCreate(false); setEditing(null) }}
          >
            {showImport ? '收起批量导入' : '批量导入 / 导出'}
          </button>
        </div>
      )}
      {showImport && (
        <div className="panel" style={{ marginTop: '0.25rem' }}>
          <h3>批量导入 / 导出</h3>
          <p className="muted">
            先下载模板填写，上传后系统逐行校验并列表预览；全部通过才能确认导入，任一行有错整批不入库。
          </p>
          <ImportWizard
            templateUrl="/servers/import-template.csv"
            exportUrl="/servers/export.csv"
            importUrl="/servers/batch-import"
            previewCols={[
              { key: 'asset_no', label: '资产编号' },
              { key: 'model', label: '型号' },
              { key: 'room', label: '机房' },
              { key: 'responsible_group', label: '运维部门' },
              { key: 'supplier', label: '供应商' },
              { key: 'run_status', label: '运行状态' },
            ]}
            onCommitted={load}
          />
        </div>
      )}
      {showCreate && (
        <ServerForm
          initial={EMPTY_FORM}
          onSubmit={submitCreate}
          onCancel={() => setShowCreate(false)}
          busy={busy}
          title="新增服务器"
          suppliers={suppliers}
          serverModels={serverModels}
        />
      )}
      {editing && (
        <ServerForm
          initial={{
            ...EMPTY_FORM,
            ...editing,
            warranty_expiry: editing.warranty_expiry || '',
            arrival_date: editing.arrival_date || '',
            purchase_amount: editing.purchase_amount ?? '',
          }}
          onSubmit={submitEdit}
          onCancel={() => setEditing(null)}
          busy={busy}
          title={`编辑 ${editing.asset_no}`}
          suppliers={suppliers}
          serverModels={serverModels}
        />
      )}

      <table>
        <thead>
          <tr>
            <th className="lt-check-col">
              <input
                type="checkbox"
                checked={sel.allVisibleSelected}
                ref={(el) => {
                  if (el) el.indeterminate = sel.someVisibleSelected
                }}
                onChange={sel.toggleAllVisible}
                aria-label="全选"
              />
            </th>
            <th>资产编号</th>
            <th>型号</th>
            <th>机房/机柜</th>
            <th>运维部门</th>
            <th>合同号</th>
            <th>供应商</th>
            <th>维保到位</th>
            <th>运行状态</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          {visible.map((s) => (
            <tr key={s.id} className={sel.isSelected(s.id) ? 'is-selected' : ''}>
              <td className="lt-check-col">
                <input
                  type="checkbox"
                  checked={sel.isSelected(s.id)}
                  onChange={() => sel.toggle(s.id)}
                  aria-label={`选择 ${s.asset_no}`}
                />
              </td>
              <td>{s.asset_no}</td>
              <td>{s.model}</td>
              <td>{s.room} / {s.rack}</td>
              <td>{s.responsible_group}</td>
              <td>{s.contract_no || '-'}</td>
              <td>{s.supplier || '-'}</td>
              <td>{s.warranty_expiry || '-'}</td>
              <td>
                <span className={`badge ${s.run_status === '投运' ? 'warn' : 'ok'}`}>
                  {s.run_status}
                </span>
              </td>
              <td>
                <div className="row-actions">
                  {s.run_status !== '退役' && (
                    <button type="button" className="secondary" onClick={() => toggle(s)}>
                      切为{s.run_status === '投运' ? '未投运' : '投运'}
                    </button>
                  )}
                  {isAdmin && (
                    <>
                      <button type="button" className="secondary" onClick={() => { setEditing(s); setShowCreate(false) }}>
                        编辑
                      </button>
                      <button type="button" className="secondary" onClick={() => remove(s)}>
                        删除
                      </button>
                    </>
                  )}
                </div>
              </td>
            </tr>
          ))}
          {!visible.length && (
            <tr>
              <td colSpan={10} className="muted" style={{ textAlign: 'center', padding: '1.5rem' }}>
                无匹配服务器
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  )
}
