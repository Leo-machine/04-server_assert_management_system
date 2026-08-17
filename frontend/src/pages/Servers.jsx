import { useEffect, useMemo, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api, getStoredUser } from '../api'
import { isLeader } from '../lib/roles'
import { RESPONSIBLE_GROUPS } from '../lib/categories'
import HeaderFilter from '../components/HeaderFilter'
import ListToolbar from '../components/ListToolbar'
import ImportWizard from '../components/ImportWizard'
import { useSelection } from '../hooks/useSelection'
import { filterByQuery } from '../lib/fuzzy'
import Pagination from '../components/Pagination'
import { usePagination } from '../hooks/usePagination'

const EMPTY_FORM = {
  asset_no: '', model: '', serial_no: '', location_id: '',
  responsible_group: '基础组', run_status: '未投运',
  supplier: '', contract_no: '', project: '', owner_unit: '本单位信息中心',
  warranty_expiry: '', arrival_date: '', purchase_amount: '',
  disk_slot_count: '', disk_interface: '', mem_slot_count: '', mem_ddr_gens: '',
  pcie_slot_count: '', nvme_slot_count: '', nvme_interface: '',
}

const GROUPS = RESPONSIBLE_GROUPS
const RUN_STATUS_OPTIONS = ['未投运', '投运', '退役']
const DISK_IFACES = ['SATA', 'SAS', '混插', '其他']
const NVME_IFACES = ['U.2', 'M.2', 'AIC', 'E1.S', '混插', '其他']
const DDR_OPTIONS = ['DDR4', 'DDR5']

function parseSlotPayload(form) {
  const intOrNull = (v) => (v === '' || v == null ? null : Number(v))
  return {
    disk_slot_count: intOrNull(form.disk_slot_count),
    disk_interface: form.disk_interface || null,
    mem_slot_count: intOrNull(form.mem_slot_count),
    mem_ddr_gens: form.mem_ddr_gens || null,
    pcie_slot_count: intOrNull(form.pcie_slot_count),
    nvme_slot_count: intOrNull(form.nvme_slot_count),
    nvme_interface: form.nvme_interface || null,
  }
}

function locLabel(s, locs) {
  const l = locs.find((x) => x.id === s.location_id)
  return l ? `${l.warehouse}/${l.slot}` : '-'
}

function modelLabel(s) { return s.model || '-' }
function roomRackLabel(s, locs) { return locLabel(s, locs) }
function contractLabel(s) { return s.contract_no || '-' }
function supplierLabel(s) { return s.supplier || '-' }
function warrantyLabel(s) { return s.warranty_expiry || '-' }

function ServerForm({ initial, onSubmit, onCancel, busy, title, suppliers, serverModels, locs }) {
  const [form, setForm] = useState(initial)
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value })
  const gens = (form.mem_ddr_gens || '').split('/').filter(Boolean)
  function toggleGen(g) {
    const next = gens.includes(g) ? gens.filter((x) => x !== g) : [...gens, g]
    setForm({ ...form, mem_ddr_gens: DDR_OPTIONS.filter((x) => next.includes(x)).join('/') })
  }
  return (
    <div className="import-overlay" onClick={onCancel}>
      <form className="srv-modal" onClick={(e) => e.stopPropagation()}
        onSubmit={(e) => { e.preventDefault(); onSubmit(form) }}>
        <h3>{title}</h3>

        <fieldset className="fields-2col">
          <legend>基本信息</legend>
          <label>资产编号 * <input value={form.asset_no} onChange={set('asset_no')} required /></label>
          <label>型号 *
            <select value={form.model || ''} onChange={set('model')} required>
              <option value="">— 请选择 —</option>
              {serverModels.map((m) => (<option key={m.id} value={m.model_name}>{m.brand ? `${m.brand} · ` : ''}{m.model_name}</option>))}
            </select>
          </label>
          <label>序列号 SN * <input value={form.serial_no || ''} onChange={set('serial_no')} required /></label>
          <label>部署位置 *
            <select value={form.location_id} onChange={set('location_id')} required>
              <option value="">— 请选择 —</option>
              {locs.map((l) => (<option key={l.id} value={l.id}>{l.warehouse}/{l.slot}{l.location_type ? `（${l.location_type}）` : ''}</option>))}
            </select>
          </label>
          <label>运维部门 *
            <select value={form.responsible_group || '基础组'} onChange={set('responsible_group')} required>
              {GROUPS.map((g) => (<option key={g}>{g}</option>))}
            </select>
          </label>
          {'run_status' in form && (
            <label>运行状态
              <select value={form.run_status} onChange={set('run_status')}>
                <option>未投运</option><option>投运</option>
              </select>
            </label>
          )}
        </fieldset>

        <fieldset className="fields-3col">
          <legend>机箱插槽规格（以下均为必填）</legend>
          <label>硬盘插槽数 * <span className="muted">（个）</span>
            <input type="number" min="1" step="1" value={form.disk_slot_count ?? ''} onChange={set('disk_slot_count')} required /></label>
          <label>硬盘接口 *
            <select value={form.disk_interface || ''} onChange={set('disk_interface')} required>
              <option value="">— 请选择 —</option>
              {DISK_IFACES.map((x) => <option key={x}>{x}</option>)}
            </select>
          </label>
          <label>内存插槽数 * <span className="muted">（个）</span>
            <input type="number" min="1" step="1" value={form.mem_slot_count ?? ''} onChange={set('mem_slot_count')} required /></label>
          <label>PCIe 插槽数 * <span className="muted">（个）</span>
            <input type="number" min="0" step="1" value={form.pcie_slot_count ?? ''} onChange={set('pcie_slot_count')} required /></label>
          <label>NVMe 插槽数 * <span className="muted">（个）</span>
            <input type="number" min="0" step="1" value={form.nvme_slot_count ?? ''} onChange={set('nvme_slot_count')} required /></label>
          <label>NVMe 接口 *
            <select value={form.nvme_interface || ''} onChange={set('nvme_interface')} required>
              <option value="">— 请选择 —</option>
              {NVME_IFACES.map((x) => <option key={x}>{x}</option>)}
            </select>
          </label>
          <label className="field-full">内存支持代际 * <span className="muted">（可多选）</span>
            <span className="chip-row" style={{ margin: '0.35rem 0 0' }}>
              {DDR_OPTIONS.map((g) => (
                <button key={g} type="button" className={`chip ${gens.includes(g) ? 'active' : ''}`} onClick={() => toggleGen(g)}>{g}</button>
              ))}
            </span>
          </label>
        </fieldset>

        <fieldset className="fields-3col">
          <legend>合同与采购（以下均为必填）</legend>
          <label>供应商 *
            <select value={form.supplier || ''} onChange={set('supplier')} required>
              <option value="">— 请选择 —</option>
              {suppliers.map((s) => (<option key={s.id} value={s.name}>{s.name}</option>))}
            </select>
          </label>
          <label>合同号 * <input value={form.contract_no || ''} onChange={set('contract_no')} required /></label>
          <label>所属项目 * <input value={form.project || ''} onChange={set('project')} required /></label>
          <label>产权单位 * <input value={form.owner_unit || ''} onChange={set('owner_unit')} required /></label>
          <label>维保到位 * <input type="date" value={form.warranty_expiry || ''} onChange={set('warranty_expiry')} required /></label>
          <label>到货日期 * <input type="date" value={form.arrival_date || ''} onChange={set('arrival_date')} required /></label>
          <label>采购金额 * <span className="muted">（元）</span>
            <input type="number" min="0" step="0.01" value={form.purchase_amount || ''} onChange={set('purchase_amount')} required /></label>
        </fieldset>

        <div className="row-actions">
          <button type="submit" disabled={busy}>{busy ? '提交中…' : '保存'}</button>
          <button type="button" className="secondary" onClick={onCancel}>取消</button>
        </div>
      </form>
    </div>
  )
}

function countBy(list, keyFn) {
  const m = {}
  for (const item of list) {
    const k = keyFn(item)
    m[k] = (m[k] || 0) + 1
  }
  return m
}

function sortedKeys(totals) {
  return Object.keys(totals).sort((a, b) => {
    if (a === '-') return 1
    if (b === '-') return -1
    return a.localeCompare(b, 'zh')
  })
}

export default function Servers() {
  const nav = useNavigate()
  const me = getStoredUser()
  const isAdmin = isLeader(me)
  const [servers, setServers] = useState([])
  const [suppliers, setSuppliers] = useState([])
  const [serverModels, setServerModels] = useState([])
  const [locs, setLocs] = useState([])
  const [error, setError] = useState('')
  const [msg, setMsg] = useState('')
  const [query, setQuery] = useState('')
  const [batchBusy, setBatchBusy] = useState(false)
  const [showCreate, setShowCreate] = useState(false)
  const [editing, setEditing] = useState(null) // server object
  const [showImport, setShowImport] = useState(false)
  const [busy, setBusy] = useState(false)
  const [woPrompt, setWoPrompt] = useState(null) // { mode:'single'|'batch', ... }
  const [assetTree, setAssetTree] = useState([])
  const [domainId, setDomainId] = useState('')
  const [deviceCategoryId, setDeviceCategoryId] = useState('')

  const [filterModel, setFilterModel] = useState('')
  const [filterLocation, setFilterLocation] = useState('')
  const [filterGroup, setFilterGroup] = useState('')
  const [filterRunStatus, setFilterRunStatus] = useState('')
  const [openFilter, setOpenFilter] = useState('')

  function load() {
    return api.get('/servers').then(setServers).catch((e) => setError(e.message))
  }

  useEffect(() => {
    load()
    api.get('/suppliers').then(setSuppliers).catch(() => {})
    api.get('/part-models?category=' + encodeURIComponent('服务器')).then(setServerModels).catch(() => {})
    api.get('/storage-locations').then(setLocs).catch(() => {})
    api.get('/asset-categories?tree=true').then((tree) => {
      const enabledRoots = tree.filter((node) => node.enabled)
      setAssetTree(enabledRoots)
      const serverParent = enabledRoots
        .flatMap((node) => (node.children || []).map((child) => ({ root: node, child })))
        .find(({ child }) => child.enabled && child.code === 'DIGITAL_SERVER')
      const initialRoot = serverParent?.root || enabledRoots[0]
      const initialChild = serverParent?.child || initialRoot?.children?.find((child) => child.enabled)
      setDomainId(initialRoot ? String(initialRoot.id) : '')
      setDeviceCategoryId(initialChild ? String(initialChild.id) : '')
    }).catch((e) => setError(e.message))
  }, [])

  const selectedDomain = assetTree.find((node) => String(node.id) === domainId)
  const deviceCategories = (selectedDomain?.children || []).filter((node) => node.enabled)
  const selectedDeviceCategory = deviceCategories.find((node) => String(node.id) === deviceCategoryId)
  const serverCategoryReady = selectedDeviceCategory?.code === 'DIGITAL_SERVER'
  const scopedSuppliers = suppliers.filter((supplier) => {
    const scopes = supplier.asset_category_ids || []
    return !scopes.length || (selectedDeviceCategory && scopes.includes(selectedDeviceCategory.id))
  })

  function chooseDomain(root) {
    const children = (root.children || []).filter((node) => node.enabled)
    setDomainId(String(root.id))
    setDeviceCategoryId(children[0] ? String(children[0].id) : '')
  }

  const searched = useMemo(
    () =>
      filterByQuery(servers, query, (s) => [
        s.asset_no,
        s.model,
        s.serial_no,
        s.run_status,
        s.responsible_group,
        s.contract_no,
        s.supplier,
        s.project,
      ]),
    [servers, query],
  )

  function applyColumnFilters(list, skip = '') {
    return list.filter((s) => {
      if (skip !== 'model' && filterModel && modelLabel(s) !== filterModel) return false
      if (skip !== 'roomRack' && filterLocation && locLabel(s, locs) !== filterLocation) return false
      if (skip !== 'group' && filterGroup && (s.responsible_group || '') !== filterGroup) return false
      if (skip !== 'runStatus' && filterRunStatus && (s.run_status || '') !== filterRunStatus) return false
      return true
    })
  }

  const visible = useMemo(
    () => applyColumnFilters(searched),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [searched, filterModel, filterLocation, filterGroup, filterRunStatus],
  )

  const modelTotals = useMemo(
    () => countBy(applyColumnFilters(searched, 'model'), modelLabel),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [searched, filterLocation, filterGroup, filterRunStatus],
  )
  const roomRackTotals = useMemo(
    () => countBy(applyColumnFilters(searched, 'roomRack'), (s) => locLabel(s, locs)),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [searched, filterModel, filterGroup, filterRunStatus, locs],
  )
  const groupTotals = useMemo(
    () => countBy(applyColumnFilters(searched, 'group'), (s) => s.responsible_group || '-'),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [searched, filterModel, filterLocation, filterRunStatus],
  )
  const contractTotals = useMemo(
    () => countBy(applyColumnFilters(searched, 'contract'), contractLabel),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [searched, filterModel, filterLocation, filterGroup, filterRunStatus],
  )
  const supplierTotals = useMemo(
    () => countBy(applyColumnFilters(searched, 'supplier'), supplierLabel),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [searched, filterModel, filterLocation, filterGroup, filterRunStatus],
  )
  const warrantyTotals = useMemo(
    () => countBy(applyColumnFilters(searched, 'warranty'), warrantyLabel),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [searched, filterModel, filterLocation, filterGroup, filterRunStatus],
  )
  const runStatusTotals = useMemo(
    () => countBy(applyColumnFilters(searched, 'runStatus'), (s) => s.run_status || '-'),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [searched, filterModel, filterLocation, filterGroup],
  )

  const pagination = usePagination(visible)
  const visibleIds = useMemo(() => pagination.pageItems.map((s) => s.id), [pagination.pageItems])
  const sel = useSelection(visibleIds)

  const hasColFilters = !!(
    filterModel || filterLocation || filterGroup || filterRunStatus
  )

  function setFilter(key, value) {
    const setters = {
      model: setFilterModel,
      roomRack: setFilterLocation,
      group: setFilterGroup,
      runStatus: setFilterRunStatus,
    }
    setters[key]?.(value)
    sel.clear()
  }

  async function toggle(server) {
    const next = server.run_status === '投运' ? '未投运' : '投运'
    setWoPrompt({ mode: 'single', server, next })
  }

  async function confirmToggle(wo) {
    const prompt = woPrompt
    if (!prompt || batchBusy) return
    const workOrder = (wo || '').trim()
    if (!workOrder) {
      setError('请填写工作票工单号')
      return
    }
    setWoPrompt(null)
    setError('')
    setMsg('')

    if (prompt.mode === 'batch') {
      setBatchBusy(true)
      let okN = 0
      const errors = []
      for (const s of prompt.targets) {
        try {
          await api.patch(`/servers/${s.id}/run-status`, {
            run_status: prompt.run_status,
            work_order_no: workOrder,
          })
          okN += 1
        } catch (e) {
          errors.push(`${s.asset_no}: ${e.message}`)
        }
      }
      await load()
      sel.clear()
      setBatchBusy(false)
      if (errors.length) setError(errors.slice(0, 3).join('；'))
      if (okN) setMsg(`已更新 ${okN} 台 → ${prompt.run_status}（工单 ${workOrder}）`)
      return
    }

    const { server, next } = prompt
    try {
      await api.patch(`/servers/${server.id}/run-status`, {
        run_status: next,
        work_order_no: workOrder,
      })
      setMsg(`${server.asset_no} → ${next}（工单 ${workOrder}）`)
      await load()
    } catch (err) {
      setError(err.message)
    }
  }

  async function batchDelete() {
    const targets = visible.filter((s) => sel.isSelected(s.id))
    if (!targets.length) return
    if (!window.confirm(`确认删除选中的 ${targets.length} 台服务器？（有配件安装关系的会被拦截）`)) return
    setBatchBusy(true)
    setError('')
    setMsg('')
    let okN = 0
    const errors = []
    for (const s of targets) {
      try {
        await api.delete(`/servers/${s.id}`)
        okN += 1
      } catch (e) {
        errors.push(`${s.asset_no}: ${e.message}`)
      }
    }
    await load()
    sel.clear()
    setBatchBusy(false)
    if (errors.length) setError(errors.slice(0, 3).join('；'))
    if (okN) setMsg(`已删除 ${okN} 台服务器`)
  }

  function batchSetStatus(run_status) {
    const targets = visible.filter(
      (s) => sel.isSelected(s.id) && s.run_status !== '退役' && s.run_status !== run_status,
    )
    if (!targets.length) {
      setError(`所选服务器中没有可切换为「${run_status}」的项`)
      return
    }
    setWoPrompt({ mode: 'batch', targets: [...targets], run_status })
  }

  async function submitCreate(form) {
    setBusy(true)
    setError('')
    try {
      await api.post('/servers', {
        ...form,
        purchase_amount: form.purchase_amount ? Number(form.purchase_amount) : null,
        ...parseSlotPayload(form),
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
      const { run_status: _rs, ...rest } = form
      await api.put(`/servers/${editing.id}`, {
        ...rest,
        purchase_amount: form.purchase_amount ? Number(form.purchase_amount) : null,
        ...parseSlotPayload(form),
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
      <h2>设备管理</h2>
      <p className="muted">
        设备专业与类别同步自「资产类别管理」。请先选择数字化、计量或调度等专业，再进入对应的二级设备类别。
      </p>
      <div className="device-domain-tabs" role="tablist" aria-label="资产专业">
        {assetTree.map((root) => (
          <button key={root.id} type="button" role="tab" aria-selected={domainId === String(root.id)}
            className={domainId === String(root.id) ? 'is-active' : ''} onClick={() => chooseDomain(root)}>
            {root.name}<small>{(root.children || []).filter((node) => node.enabled).length}</small>
          </button>
        ))}
      </div>
      <div className="device-type-tabs" role="tablist" aria-label="设备类别">
        {!deviceCategories.length && <div className="device-category-empty">该专业暂未配置二级设备类别</div>}
        {deviceCategories.map((category) => {
          const ready = category.code === 'DIGITAL_SERVER'
          return (
            <button key={category.id} type="button" role="tab" aria-selected={deviceCategoryId === String(category.id)}
              className={deviceCategoryId === String(category.id) ? 'is-active' : ''} onClick={() => setDeviceCategoryId(String(category.id))}>
              <span><strong>{category.name}</strong><small>{ready ? `${servers.length} 台设备` : category.code || '未设置编码'}</small></span>
              {!ready && <em>待接入</em>}
            </button>
          )
        })}
      </div>
      {error && <div className="error">{error}</div>}
      {msg && <div className="ok-msg">{msg}</div>}

      {!serverCategoryReady ? (
        <div className="device-empty-state">
          <span>◇</span>
          <strong>{selectedDeviceCategory ? `${selectedDeviceCategory.name}管理能力待接入` : '请选择设备类别'}</strong>
          <p>{selectedDomain?.name || '当前专业'}的二级目录由资产类别管理统一维护，后续可在此扩展档案字段、导入模板和设备流转能力。</p>
        </div>
      ) : <>

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
            {filterModel ? ` · ${filterModel}` : ''}
            {filterLocation ? ` · ${filterLocation}` : ''}
            {filterGroup ? ` · ${filterGroup}` : ''}
            {filterRunStatus ? ` · ${filterRunStatus}` : ''}
            {hasColFilters && (
              <button type="button" className="linkish" onClick={() => {
                setFilterModel(''); setFilterLocation(''); setFilterGroup('')
                setFilterRunStatus(''); sel.clear()
              }}>清除筛选</button>
            )}
          </>
        }
        selectedCount={sel.selectedCount}
        onClearSelection={sel.clear}
        batchActions={
          <>
            <button type="button" disabled={batchBusy} onClick={() => batchSetStatus('投运')}>批量·投运</button>
            <button type="button" className="secondary" disabled={batchBusy} onClick={() => batchSetStatus('未投运')}>批量·未投运</button>
            {isAdmin && (
              <button type="button" className="secondary" disabled={batchBusy} onClick={batchDelete}
                style={{ color: '#b91c1c', borderColor: '#fca5a5' }}>批量·删除</button>
            )}
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
        <div className="import-overlay" onClick={() => setShowImport(false)}>
          <div className="srv-modal" onClick={(e) => e.stopPropagation()}>
            <h3>批量导入 / 导出</h3>
            <p className="muted">下载模板填写后上传 CSV，逐行校验预览；全部通过才能确认导入。</p>
            <ImportWizard
              templateUrl="/servers/import-template.csv"
              exportUrl="/servers/export.csv"
              importUrl="/servers/batch-import"
              previewCols={[
                { key: 'asset_no', label: '资产编号' },
                { key: 'model', label: '型号' },
                { key: 'location_id', label: '部署位置ID' },
                { key: 'responsible_group', label: '运维部门' },
                { key: 'supplier', label: '供应商' },
                { key: 'run_status', label: '运行状态' },
              ]}
              onCommitted={() => { load(); setShowImport(false) }}
            />
          </div>
        </div>
      )}
      {showCreate && (
        <ServerForm
          initial={EMPTY_FORM}
          onSubmit={submitCreate}
          onCancel={() => setShowCreate(false)}
          busy={busy}
          title="新增服务器"
          suppliers={scopedSuppliers}
          serverModels={serverModels}
          locs={locs}
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
            disk_slot_count: editing.disk_slot_count ?? '',
            disk_interface: editing.disk_interface || '',
            mem_slot_count: editing.mem_slot_count ?? '',
            mem_ddr_gens: editing.mem_ddr_gens || '',
            pcie_slot_count: editing.pcie_slot_count ?? '',
            nvme_slot_count: editing.nvme_slot_count ?? '',
            nvme_interface: editing.nvme_interface || '',
          }}
          onSubmit={submitEdit}
          onCancel={() => setEditing(null)}
          busy={busy}
          title={`编辑 ${editing.asset_no}`}
          suppliers={scopedSuppliers}
          serverModels={serverModels}
          locs={locs}
        />
      )}

      <div className="srv-table-wrap">
        <table className="srv-table">
          <thead>
            <tr>
              <th className="lt-check-col"><input type="checkbox" checked={sel.allVisibleSelected}
                ref={(el) => { if (el) el.indeterminate = sel.someVisibleSelected }}
                onChange={sel.toggleAllVisible} aria-label="全选" /></th>
              <th>资产编号</th>
              <HeaderFilter label="型号" value={filterModel} options={sortedKeys(modelTotals)} totals={modelTotals}
                open={openFilter === 'model'} onToggle={(v) => setOpenFilter(v ? 'model' : '')} onSelect={(v) => setFilter('model', v)} />
              <HeaderFilter label="部署位置" value={filterLocation} options={sortedKeys(roomRackTotals)} totals={roomRackTotals}
                open={openFilter === 'roomRack'} onToggle={(v) => setOpenFilter(v ? 'roomRack' : '')} onSelect={(v) => setFilter('roomRack', v)} />
              <HeaderFilter label="运维部门" value={filterGroup}
                options={GROUPS.filter((g) => groupTotals[g] || filterGroup === g)} totals={groupTotals}
                open={openFilter === 'group'} onToggle={(v) => setOpenFilter(v ? 'group' : '')} onSelect={(v) => setFilter('group', v)} />
              <HeaderFilter label="运行状态" value={filterRunStatus}
                options={RUN_STATUS_OPTIONS.filter((s) => runStatusTotals[s] || filterRunStatus === s)} totals={runStatusTotals}
                open={openFilter === 'runStatus'} onToggle={(v) => setOpenFilter(v ? 'runStatus' : '')} onSelect={(v) => setFilter('runStatus', v)} />
              <th>供应商 / 合同</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            {pagination.pageItems.map((s) => (
              <tr key={s.id} className={sel.isSelected(s.id) ? 'is-selected' : ''}
                style={{ cursor: 'pointer' }} onClick={() => nav(`/devices/${s.id}`)}>
                <td className="lt-check-col" onClick={(e) => e.stopPropagation()}>
                  <input type="checkbox" checked={sel.isSelected(s.id)}
                    onChange={() => sel.toggle(s.id)} aria-label={`选择 ${s.asset_no}`} />
                </td>
                <td><Link to={`/devices/${s.id}`} onClick={(e) => e.stopPropagation()} className="srv-name">{s.asset_no}</Link></td>
                <td>{s.model || '-'}</td>
                <td>{locLabel(s, locs)}</td>
                <td>{s.responsible_group || '-'}</td>
                <td onClick={(e) => e.stopPropagation()}>
                  {s.run_status === '退役' ? (
                    <span className="badge danger">{s.run_status}</span>
                  ) : (
                    <button type="button"
                      className={`srv-status-btn ${s.run_status === '投运' ? 'is-live' : 'is-idle'}`}
                      onClick={() => toggle(s)}>
                      {s.run_status}
                    </button>
                  )}
                </td>
                <td className="wrap">
                  <div>{s.supplier || '-'}</div>
                  <div className="muted" style={{ fontSize: '0.75rem' }}>{s.contract_no || '-'}</div>
                </td>
                <td onClick={(e) => e.stopPropagation()}>
                  <div className="row-actions">
                    {isAdmin && (<>
                      <button type="button" className="secondary" onClick={() => { setEditing(s); setShowCreate(false) }}>编辑</button>
                      <button type="button" className="secondary" onClick={() => remove(s)}>删除</button>
                    </>)}
                  </div>
                </td>
              </tr>
            ))}
            {!visible.length && (
              <tr><td colSpan={7} className="muted" style={{ textAlign: 'center', padding: '2rem' }}>无匹配服务器</td></tr>
            )}
          </tbody>
        </table>
      </div>
      <Pagination pagination={pagination} />

      {/* 工单号输入弹窗 */}
      {woPrompt && (
        <WoPromptModal
          prompt={woPrompt}
          busy={batchBusy}
          onSubmit={confirmToggle}
          onCancel={() => !batchBusy && setWoPrompt(null)}
        />
      )}
      </>}
    </div>
  )
}

function WoPromptModal({ prompt, busy, onSubmit, onCancel }) {
  const [wo, setWo] = useState('')
  const isBatch = prompt.mode === 'batch'
  const title = isBatch
    ? `批量切换为「${prompt.run_status}」`
    : '切换运行状态'
  const hint = isBatch
    ? `将对 ${prompt.targets.length} 台服务器统一填写工单号并切换状态`
    : `将 ${prompt.server.asset_no} 从「${prompt.server.run_status}」切换为「${prompt.next}」`

  return (
    <div className="import-overlay" onClick={busy ? undefined : onCancel}>
      <div className="import-modal" onClick={(e) => e.stopPropagation()} style={{ width: 400 }}>
        <h3>{title}</h3>
        <p className="muted">{hint}</p>
        <label>
          工作票工单号 *
          <input
            value={wo}
            onChange={(e) => setWo(e.target.value)}
            disabled={busy}
            required
            placeholder="如 WO-2026-0803-001"
            autoFocus
          />
        </label>
        <div className="row-actions" style={{ marginTop: '0.75rem' }}>
          <button type="button" disabled={!wo.trim() || busy} onClick={() => onSubmit(wo.trim())}>
            {busy ? '提交中…' : '确认切换'}
          </button>
          <button type="button" className="secondary" disabled={busy} onClick={onCancel}>取消</button>
        </div>
      </div>
    </div>
  )
}
