import { useEffect, useMemo, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { api, downloadCsv, getStoredUser } from '../api'
import { isLeader } from '../lib/roles'
import { RESPONSIBLE_GROUPS } from '../lib/categories'
import { formatSpec } from '../components/SpecFields'
import ImportWizard from '../components/ImportWizard'

const CATEGORY_META = {
  内存: { desc: '容量 / 类型 / 频率', tone: 'c1' },
  机械硬盘: { desc: '容量 / 接口 / 转速', tone: 'c2' },
  固态硬盘: { desc: '容量 / 协议 / 形态', tone: 'c3' },
  RAID卡: { desc: '通道 / 缓存 / RAID 级别', tone: 'c4' },
  光模块: { desc: '速率 / 类型 / 兼容', tone: 'c5' },
  网卡: { desc: '速率 / 口型 / 端口', tone: 'c6' },
  HBA卡: { desc: '子类型 / 速率 / 端口', tone: 'c7' },
  算力卡: { desc: '显存 / 封装 / 架构', tone: 'c8' },
}

const SOURCES = ['服务器原装', '独立合同采购', '框招正偏移']
const GROUPS = RESPONSIBLE_GROUPS

const emptyCommon = {
  model_id: '',
  fixed_asset_no: '',
  serial_no: '',
  source_type: '独立合同采购',
  server_id: '',
  storage_location_id: '',
  responsible_group: '基础组',
  supplier: '',
  contract_no: '',
  purchase_amount: '',
  purchase_date: '',
  project: '',
  owner_unit: '本单位信息中心',
  warranty_expiry: '',
  allocatable_flag: '通用可调',
  remark: '',
}

function RoField({ label, value }) {
  return (
    <label>
      {label}
      <input value={value || '—'} readOnly disabled style={{ background: 'var(--bg-muted, #f5f5f5)' }} />
    </label>
  )
}

function serverLocLabel(s, locs) {
  if (!s?.location_id || !locs) return '-'
  const l = locs.find((x) => x.id === s.location_id)
  return l ? `${l.warehouse}/${l.slot}` : `ID#${s.location_id}`
}

export default function Inbound() {
  const nav = useNavigate()
  const [params, setParams] = useSearchParams()
  const category = params.get('category') || ''

  const [schemas, setSchemas] = useState([])
  const [models, setModels] = useState([])
  const [locs, setLocs] = useState([])
  const [suppliers, setSuppliers] = useState([])
  const [servers, setServers] = useState([])
  const [assetTree, setAssetTree] = useState([])
  const [level1Id, setLevel1Id] = useState('')
  const [level2Id, setLevel2Id] = useState('')
  const [form, setForm] = useState(emptyCommon)
  const [error, setError] = useState('')
  const [ok, setOk] = useState('')
  const [showImport, setShowImport] = useState(false)
  const isAdmin = isLeader(getStoredUser())

  const schema = useMemo(
    () => schemas.find((s) => s.category === category),
    [schemas, category],
  )
  const categoryModels = useMemo(
    () => models.filter((m) => m.category === category),
    [models, category],
  )
  const selectedModel = useMemo(
    () => categoryModels.find((m) => String(m.id) === String(form.model_id)),
    [categoryModels, form.model_id],
  )
  const selectedServer = useMemo(
    () => servers.find((s) => String(s.id) === String(form.server_id)),
    [servers, form.server_id],
  )
  const isOriginal = form.source_type === '服务器原装'

  useEffect(() => {
    const locUrl = category
      ? `/storage-locations?category=${encodeURIComponent(category)}`
      : '/storage-locations'
    Promise.all([
      api.get('/categories'),
      api.get('/part-models'),
      api.get(locUrl),
      api.get('/suppliers'),
      api.get('/servers'),
      api.get('/asset-categories?tree=true'),
    ])
      .then(([cats, ms, ls, sps, srvs, tree]) => {
        setSchemas(cats)
        setModels(ms)
        setLocs(ls)
        setSuppliers(sps)
        setServers(srvs)
        setAssetTree(tree)
        const firstLocId = ls[0]?.id ? String(ls[0].id) : ''
        setForm((f) => ({
          ...f,
          storage_location_id: f.storage_location_id || firstLocId,
        }))
      })
      .catch((e) => setError(e.message))
  }, [category])

  useEffect(() => {
    if (!assetTree.length) return
    setLevel1Id((current) => current || String(assetTree.find((node) => node.enabled)?.id || ''))
  }, [assetTree])

  const selectedLevel1 = useMemo(
    () => assetTree.find((node) => String(node.id) === level1Id),
    [assetTree, level1Id],
  )
  const level2Options = useMemo(
    () => (selectedLevel1?.children || []).filter((node) => node.enabled),
    [selectedLevel1],
  )
  const selectedLevel2 = useMemo(
    () => level2Options.find((node) => String(node.id) === level2Id),
    [level2Options, level2Id],
  )
  const level3Options = useMemo(
    () => (selectedLevel2?.children || []).filter((node) => node.enabled),
    [selectedLevel2],
  )
  const scopedSuppliers = useMemo(() => suppliers.filter((supplier) => {
    const scopes = supplier.asset_category_ids || []
    return !scopes.length || (selectedLevel2 && scopes.includes(selectedLevel2.id))
  }), [suppliers, selectedLevel2])

  useEffect(() => {
    if (!level2Options.length) {
      setLevel2Id('')
      return
    }
    if (!level2Options.some((node) => String(node.id) === level2Id)) {
      setLevel2Id(String(level2Options[0].id))
    }
  }, [level2Options, level2Id])

  function fetchNextAssetNo(cat) {
    if (!cat) return
    api.get(`/parts/next-asset-no?category=${encodeURIComponent(cat)}`)
      .then((data) => setForm((f) => ({ ...f, fixed_asset_no: data.fixed_asset_no })))
      .catch(() => {}) // 静默失败，用户可手动输入
  }

  useEffect(() => {
    if (!category) return
    const first = models.find((m) => m.category === category)
    setForm((f) => ({
      ...emptyCommon,
      source_type: f.source_type,
      storage_location_id: f.storage_location_id || String(locs[0]?.id || ''),
      model_id: first ? String(first.id) : '',
    }))
    setError('')
    setOk('')
    fetchNextAssetNo(category)
  }, [category, models])

  function chooseCategory(cat) {
    setParams({ category: cat })
  }

  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value })

  async function onSubmit(e) {
    e.preventDefault()
    setError('')
    setOk('')
    try {
      const payload = {
        model_id: Number(form.model_id),
        fixed_asset_no: form.fixed_asset_no,
        serial_no: form.serial_no,
        source_type: form.source_type,
        purchase_amount: Number(form.purchase_amount),
        allocatable_flag: form.allocatable_flag,
        remark: form.remark,
      }
      if (isOriginal) {
        payload.server_id = Number(form.server_id)
      } else {
        Object.assign(payload, {
          storage_location_id: Number(form.storage_location_id),
          responsible_group: form.responsible_group,
          supplier: form.supplier,
          contract_no: form.contract_no,
          purchase_date: form.purchase_date,
          project: form.project,
          owner_unit: form.owner_unit,
          warranty_expiry: form.warranty_expiry,
        })
      }
      const part = await api.post('/parts/inbound', payload)
      setOk(`入库成功：${part.fixed_asset_no}（${part.current_status}）`)
      setTimeout(() => nav('/'), 900)
    } catch (err) {
      setError(err.message)
    }
  }

  if (!category) {
    return (
      <div className="panel">
        <h2>分类入库</h2>
        <p className="muted">
          请按专业域、资产大类和具体类别逐级选择。已接入的三级类别可进入入库表单，其余类别将随系统建设逐步开放。
          型号不足时请先联系领导在「型号管理」中维护
          {isAdmin && (
            <>（<Link to="/part-models">打开型号管理</Link>）</>
          )}
          。
        </p>
        {error && <div className="error">{error}</div>}
        <div className="inb-category-path">
          <section className="inb-level-column">
            <div className="inb-level-head"><span>01</span><strong>专业域</strong></div>
            <div className="inb-level-options">
              {assetTree.filter((node) => node.enabled).map((node) => (
                <button key={node.id} type="button" className={level1Id === String(node.id) ? 'is-active' : ''} onClick={() => setLevel1Id(String(node.id))}>
                  <strong>{node.name}</strong><small>{node.children?.length || 0} 个下级</small>
                </button>
              ))}
            </div>
          </section>
          <section className="inb-level-column">
            <div className="inb-level-head"><span>02</span><strong>资产大类</strong></div>
            <div className="inb-level-options">
              {!level2Options.length && <div className="inb-level-empty">该专业域暂无下级目录</div>}
              {level2Options.map((node) => (
                <button key={node.id} type="button" className={level2Id === String(node.id) ? 'is-active' : ''} onClick={() => setLevel2Id(String(node.id))}>
                  <strong>{node.name}</strong><small>{node.children?.length || 0} 个具体类别</small>
                </button>
              ))}
            </div>
          </section>
          <section className="inb-level-column is-leaf">
            <div className="inb-level-head"><span>03</span><strong>具体类别</strong></div>
            <div className="inb-leaf-grid">
              {!level3Options.length && <div className="inb-level-empty">目录已建立，具体类别待扩展</div>}
              {level3Options.map((node) => {
                const cat = node.business_category
                const meta = CATEGORY_META[cat] || { desc: '业务能力待接入', tone: 'c1' }
                const count = cat ? models.filter((m) => m.category === cat).length : 0
                return (
                  <button key={node.id} type="button" disabled={!cat} className={`inb-leaf-card ${cat ? 'is-ready' : ''}`} onClick={() => cat && chooseCategory(cat)}>
                    <strong>{node.name}</strong>
                    <span>{meta.desc}</span>
                    <em>{cat ? `${count} 个可用型号` : '待扩展'}</em>
                  </button>
                )
              })}
            </div>
          </section>
        </div>
      </div>
    )
  }

  return (
    <div className="panel">
      <div className="inb-head">
        <button type="button" className="inb-back" onClick={() => setParams({})}>
          <span className="inb-back-arrow">‹</span> 返回分类选择
        </button>
        <div className="inb-title">
          <h2>{category} · 入库</h2>
          <span className="inb-sub">来源先行 · 逐件录入 / 批量导入</span>
        </div>
        <div className="inb-actions">
          {isAdmin && (
            <Link
              className="inb-btn"
              to={`/part-models?category=${encodeURIComponent(category)}`}
            >
              ⚙ 管理本类型号
            </Link>
          )}
          <button
            type="button"
            className="inb-btn"
            onClick={() =>
              downloadCsv(
                `/parts/import-template.csv?category=${encodeURIComponent(category)}`,
                `${category}_入库模板.csv`,
              ).catch((e) => setError(e.message))
            }
          >
            📄 下载模板
          </button>
          <button
            type="button"
            className={`inb-btn ${showImport ? 'is-on' : ''}`}
            onClick={() => setShowImport((v) => !v)}
          >
            📥 {showImport ? '收起批量导入' : '批量导入（CSV）'}
          </button>
        </div>
      </div>
      {showImport && (
        <div className="panel" style={{ marginTop: '0.25rem' }}>
          <h3>{category} · 批量入库</h3>
          <p className="muted">
            下载本类模板填写（服务器原装行只需关联服务器，合同信息自动带出）；上传后逐行校验预览，全部通过才能确认入库。
          </p>
          <ImportWizard
            templateUrl={`/parts/import-template.csv?category=${encodeURIComponent(category)}`}
            importUrl="/parts/batch-import"
            previewCols={[
              { key: 'fixed_asset_no', label: '固定资产编号' },
              { key: 'model_name', label: '型号名称' },
              { key: 'source_type', label: '来源' },
              { key: 'server_asset_no', label: '关联服务器' },
              { key: 'location', label: '存放位置' },
            ]}
            onCommitted={() => {
              setOk('批量入库成功')
              setShowImport(false)
              setTimeout(() => nav('/'), 800)
            }}
          />
        </div>
      )}
      {error && <div className="error">{error}</div>}
      {ok && <div className="ok-msg">{ok}</div>}

      {!categoryModels.length ? (
        <div className="error">
          当前类型暂无型号，请先联系领导在型号管理中新增
          {isAdmin && (
            <>
              （
              <Link to={`/part-models?category=${encodeURIComponent(category)}`}>
                打开型号管理
              </Link>
              ）
            </>
          )}
          后再入库。
        </div>
      ) : (
        <form onSubmit={onSubmit} className="inbound-form">
          <fieldset className="fields-2col">
            <legend>来源（先选来源，再填其余信息）</legend>
            <label>
              来源 *
              <select value={form.source_type} onChange={set('source_type')} required>
                {SOURCES.map((s) => (
                  <option key={s}>{s}</option>
                ))}
              </select>
            </label>
            {isOriginal ? (
              <label>
                关联服务器 *
                <select value={form.server_id} onChange={set('server_id')} required>
                  <option value="">— 请选择服务器资产编号 —</option>
                  {servers.map((s) => (
                    <option key={s.id} value={s.id}>
                      {s.asset_no}（{s.run_status}）
                    </option>
                  ))}
                </select>
              </label>
            ) : (
              <label>
                存放位置 *
                <select value={form.storage_location_id} onChange={set('storage_location_id')} required>
                  {locs.map((l) => (
                    <option key={l.id} value={l.id}>
                      {l.warehouse}/{l.slot}{l.location_type ? `（${l.location_type}）` : ''}
                    </option>
                  ))}
                </select>
              </label>
            )}
          </fieldset>

          {isOriginal && selectedServer && (
            <fieldset className="fields-2col">
              <legend>由服务器档案带出（只读）</legend>
              <RoField label="部署位置" value={serverLocLabel(selectedServer, locs)} />
              <RoField label="运维部门" value={selectedServer.responsible_group} />
              <RoField label="供应商" value={selectedServer.supplier} />
              <RoField label="所属项目" value={selectedServer.project} />
              <RoField label="产权单位" value={selectedServer.owner_unit} />
              <RoField label="维保到位时间" value={selectedServer.warranty_expiry} />
              <RoField label="合同号" value={selectedServer.contract_no} />
              <RoField label="设备到货日期" value={selectedServer.arrival_date} />
            </fieldset>
          )}

          {!isOriginal && (
            <fieldset className="fields-2col">
              <legend>采购与归属</legend>
              <label>
                运维部门 *
                <select value={form.responsible_group} onChange={set('responsible_group')}>
                  {GROUPS.map((g) => (
                    <option key={g}>{g}</option>
                  ))}
                </select>
              </label>
              <label>
                供应商 *
                <select value={form.supplier} onChange={set('supplier')} required>
                  <option value="">— 请选择 —</option>
                  {scopedSuppliers.map((s) => (
                    <option key={s.id} value={s.name}>{s.name}</option>
                  ))}
                </select>
                {!suppliers.length && (
                  <span className="muted">
                    {' '}暂无名录，请先到 <Link to="/suppliers">供应商</Link> 维护
                  </span>
                )}
              </label>
              <label>
                合同号 *
                <input value={form.contract_no} onChange={set('contract_no')} required placeholder="如：HT-2026-001" />
              </label>
              <label>
                所属项目 *
                <input value={form.project} onChange={set('project')} required placeholder="如：2026年基础资源扩容" />
              </label>
              <label>
                产权单位 *
                <input value={form.owner_unit} onChange={set('owner_unit')} required placeholder="本单位信息中心" />
              </label>
              <label>
                到货验收日期 *
                <input type="date" value={form.purchase_date} onChange={set('purchase_date')} required />
              </label>
              <label>
                维保到位时间 *
                <input type="date" value={form.warranty_expiry} onChange={set('warranty_expiry')} required />
              </label>
            </fieldset>
          )}

          <fieldset className="fields-1col">
            <legend>型号与规格</legend>
            <label>
              选择型号 *
              <select value={form.model_id} onChange={set('model_id')} required>
                <option value="">请选择</option>
                {categoryModels.map((m) => (
                  <option key={m.id} value={m.id}>
                    {m.brand ? `${m.brand} · ` : ''}{m.model_name}
                  </option>
                ))}
              </select>
            </label>
            {selectedModel && (
              <div className="spec-readonly">
                <div className="muted">已选型号规格（来自型号库，入库时随型号确定）</div>
                <div>{formatSpec(selectedModel.spec)}</div>
                {selectedModel.pn && <div className="muted">PN：{selectedModel.pn}</div>}
              </div>
            )}
            {schema && (
              <details className="muted-details">
                <summary>本类规格字段说明</summary>
                <ul>
                  {schema.fields.map((f) => (
                    <li key={f.key}>
                      {f.label}
                      {f.required ? '（必填）' : '（可选）'}
                      {f.options ? `：${f.options.join('/')}` : ''}
                    </li>
                  ))}
                </ul>
              </details>
            )}
          </fieldset>

          <fieldset className="fields-2col">
            <legend>实物信息</legend>
            <label>
              固定资产编号 *
              <div style={{ display: 'flex', gap: 4 }}>
                <input value={form.fixed_asset_no} onChange={set('fixed_asset_no')} required
                  placeholder="自动生成，可手动修改" style={{ flex: 1 }} />
                <button type="button" className="secondary"
                  style={{ padding: '0 0.6rem', fontSize: '0.85rem', whiteSpace: 'nowrap' }}
                  title="重新生成编号"
                  onClick={() => fetchNextAssetNo(category)}>
                  ↻ 生成
                </button>
              </div>
            </label>
            <label>
              设备序列（SN）号 *
              <input value={form.serial_no} onChange={set('serial_no')} required placeholder="如：SN-MEM-1001" />
            </label>
            <label>
              采购金额 *
              <input type="number" min="0" step="0.01" value={form.purchase_amount} onChange={set('purchase_amount')} required placeholder="0.00" />
            </label>
            <label>
              可调配标记 *
              <select value={form.allocatable_flag} onChange={set('allocatable_flag')}>
                <option>通用可调</option>
                <option>保留</option>
              </select>
            </label>
            <label className="field-full">
              备注 *
              <textarea value={form.remark} onChange={set('remark')} rows={2} required placeholder="入库事由/工单号等" />
            </label>
          </fieldset>

          <div className="field-full">
            <button type="submit">确认入库</button>
          </div>
        </form>
      )}
    </div>
  )
}
