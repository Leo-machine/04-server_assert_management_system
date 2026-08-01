import { useEffect, useMemo, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { api } from '../api'
import { formatSpec } from '../components/SpecFields'

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

const emptyCommon = {
  model_id: '',
  fixed_asset_no: '',
  storage_location_id: '',
  source_type: '单独合同',
  responsible_group: '基础组',
  serial_no: '',
  contract_no: '',
  purchase_amount: '',
  purchase_date: '',
  sensitivity: '',
  supplier: '',
  project: '',
  owner_unit: '本单位信息中心',
  warranty_expiry: '',
  allocatable_flag: '通用可调',
  remark: '',
}

export default function Inbound() {
  const nav = useNavigate()
  const [params, setParams] = useSearchParams()
  const category = params.get('category') || ''

  const [schemas, setSchemas] = useState([])
  const [models, setModels] = useState([])
  const [locs, setLocs] = useState([])
  const [suppliers, setSuppliers] = useState([])
  const [form, setForm] = useState(emptyCommon)
  const [error, setError] = useState('')
  const [ok, setOk] = useState('')

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

  // 按当前配件类型加载兼容库位
  useEffect(() => {
    const locUrl = category
      ? `/storage-locations?category=${encodeURIComponent(category)}`
      : '/storage-locations'
    Promise.all([
      api.get('/categories'),
      api.get('/part-models'),
      api.get(locUrl),
      api.get('/suppliers'),
    ])
      .then(([cats, ms, ls, sps]) => {
        setSchemas(cats)
        setModels(ms)
        setLocs(ls)
        setSuppliers(sps)
        const firstLocId = ls[0]?.id ? String(ls[0].id) : ''
        setForm((f) => ({
          ...f,
          storage_location_id: f.storage_location_id || firstLocId,
        }))
      })
      .catch((e) => setError(e.message))
  }, [category])

  useEffect(() => {
    if (!category) return
    const first = models.find((m) => m.category === category)
    setForm((f) => ({
      ...emptyCommon,
      storage_location_id: f.storage_location_id || String(locs[0]?.id || ''),
      model_id: first ? String(first.id) : '',
      sensitivity: category === '算力卡' ? '管控' : '',
    }))
    setError('')
    setOk('')
  }, [category, models])

  function chooseCategory(cat) {
    setParams({ category: cat })
  }

  async function onSubmit(e) {
    e.preventDefault()
    setError('')
    setOk('')
    try {
      const part = await api.post('/parts/inbound', {
        model_id: Number(form.model_id),
        fixed_asset_no: form.fixed_asset_no,
        storage_location_id: Number(form.storage_location_id),
        source_type: form.source_type,
        responsible_group: form.responsible_group,
        serial_no: form.serial_no,
        contract_no: form.contract_no,
        purchase_amount: Number(form.purchase_amount),
        purchase_date: form.purchase_date,
        sensitivity: form.sensitivity,
        supplier: form.supplier,
        project: form.project,
        owner_unit: form.owner_unit,
        warranty_expiry: form.warranty_expiry,
        allocatable_flag: form.allocatable_flag,
        remark: form.remark,
      })
      setOk(`入库成功：${part.fixed_asset_no}`)
      setTimeout(() => nav('/'), 800)
    } catch (err) {
      setError(err.message)
    }
  }

  if (!category) {
    return (
      <div className="panel">
        <h2>分类入库</h2>
        <p className="muted">
          请选择配件类型进入对应入库表单。不同类型规格字段不同，保证入库数据可用、可检索。
          型号不足时请先到 <Link to="/part-models">型号管理</Link> 维护。
        </p>
        {error && <div className="error">{error}</div>}
        <div className="category-grid">
          {(schemas.length ? schemas.map((s) => s.category) : Object.keys(CATEGORY_META)).map(
            (cat) => {
              const meta = CATEGORY_META[cat] || { desc: cat, tone: 'c1' }
              const count = models.filter((m) => m.category === cat).length
              return (
                <button
                  key={cat}
                  type="button"
                  className={`category-card ${meta.tone}`}
                  onClick={() => chooseCategory(cat)}
                >
                  <strong>{cat}</strong>
                  <span>{meta.desc}</span>
                  <em>{count} 个可用型号</em>
                </button>
              )
            },
          )}
        </div>
      </div>
    )
  }

  return (
    <div className="panel">
      <h2>{category} · 入库</h2>
      <p className="muted">
        <button type="button" className="linkish" onClick={() => setParams({})}>
          ← 返回分类选择
        </button>
        {' · '}
        <Link to={`/part-models?category=${encodeURIComponent(category)}`}>管理本类型号</Link>
      </p>
      {error && <div className="error">{error}</div>}
      {ok && <div className="ok-msg">{ok}</div>}

      {!categoryModels.length ? (
        <div className="error">
          当前类型暂无型号，请先在
          <Link to={`/part-models?category=${encodeURIComponent(category)}`}> 型号管理 </Link>
          中新增后再入库。
        </div>
      ) : (
        <form onSubmit={onSubmit} className="inbound-form">
          <fieldset className="fields-1col">
            <legend>型号与规格</legend>
            <label>
              选择型号 *
              <select
                value={form.model_id}
                onChange={(e) => setForm({ ...form, model_id: e.target.value })}
                required
              >
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
              <input
                value={form.fixed_asset_no}
                onChange={(e) => setForm({ ...form, fixed_asset_no: e.target.value })}
                required
                placeholder="FA-XXX-0000"
              />
            </label>
            <label>
              厂商序列号 SN *
              <input
                value={form.serial_no}
                onChange={(e) => setForm({ ...form, serial_no: e.target.value })}
                required
                placeholder="如：SN-MEM-1001"
              />
            </label>
            <label>
              存放位置 *
              <select
                value={form.storage_location_id}
                onChange={(e) => setForm({ ...form, storage_location_id: e.target.value })}
                required
              >
                {locs.map((l) => (
                  <option key={l.id} value={l.id}>
                    {l.warehouse}/{l.slot}{l.location_type ? `（${l.location_type}）` : ''}
                  </option>
                ))}
              </select>
            </label>
            <label>
              来源 *
              <select
                value={form.source_type}
                onChange={(e) => setForm({ ...form, source_type: e.target.value })}
              >
                <option>随器采购</option>
                <option>单独合同</option>
                <option>维保换新</option>
              </select>
            </label>
            <label>
              运维部门 *
              <select
                value={form.responsible_group}
                onChange={(e) => setForm({ ...form, responsible_group: e.target.value })}
              >
                <option>基础组</option>
                <option>运营组</option>
                <option>网络组</option>
                <option>平台组</option>
              </select>
            </label>
            <label>
              供应商 *
              <select
                value={form.supplier}
                onChange={(e) => setForm({ ...form, supplier: e.target.value })}
                required
              >
                <option value="">— 请选择 —</option>
                {suppliers.map((s) => (
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
              所属项目 *
              <input
                value={form.project}
                onChange={(e) => setForm({ ...form, project: e.target.value })}
                required
                placeholder="如：2026年基础资源扩容"
              />
            </label>
            <label>
              产权单位 *
              <input
                value={form.owner_unit}
                onChange={(e) => setForm({ ...form, owner_unit: e.target.value })}
                required
                placeholder="本单位信息中心"
              />
            </label>
            <label>
              维保到期 *
              <input
                type="date"
                value={form.warranty_expiry}
                onChange={(e) => setForm({ ...form, warranty_expiry: e.target.value })}
                required
              />
            </label>
            <label>
              可调配标记 *
              <select
                value={form.allocatable_flag}
                onChange={(e) => setForm({ ...form, allocatable_flag: e.target.value })}
              >
                <option>通用可调</option>
                <option>保留</option>
              </select>
            </label>
            <label>
              合同号 *
              <input
                value={form.contract_no}
                onChange={(e) => setForm({ ...form, contract_no: e.target.value })}
                required
                placeholder="如：HT-2026-001"
              />
            </label>
            <label>
              采购金额 *
              <input
                type="number"
                min="0"
                step="0.01"
                value={form.purchase_amount}
                onChange={(e) => setForm({ ...form, purchase_amount: e.target.value })}
                required
                placeholder="0.00"
              />
            </label>
            <label>
              采购日期 *
              <input
                type="date"
                value={form.purchase_date}
                onChange={(e) => setForm({ ...form, purchase_date: e.target.value })}
                required
              />
            </label>
            <label>
              敏感标记 *
              <select
                value={form.sensitivity}
                onChange={(e) => setForm({ ...form, sensitivity: e.target.value })}
                required
              >
                <option value="">— 请选择 —</option>
                <option value="无">无</option>
                <option value="管控">管控</option>
                <option value="出口管制">出口管制</option>
              </select>
            </label>
            <label className="field-full">
              备注 *
              <textarea
                value={form.remark}
                onChange={(e) => setForm({ ...form, remark: e.target.value })}
                rows={2}
                required
                placeholder="入库事由/工单号等"
              />
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
