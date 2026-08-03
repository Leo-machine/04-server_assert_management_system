import { useEffect, useMemo, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { api } from '../api'
import { formatSpec } from '../components/SpecFields'

function Field({ label, children }) {
  return (
    <div className="pd-field">
      <dt>{label}</dt>
      <dd>{children ?? '—'}</dd>
    </div>
  )
}

function locLabel(part, servers, locs, orgs) {
  if (!part?.current_loc_kind) return '—'
  if (part.current_loc_kind === '库位') {
    const loc = locs.find((l) => l.id === part.current_loc_id)
    return loc ? `${loc.warehouse}/${loc.slot}` : `库位#${part.current_loc_id}`
  }
  if (part.current_loc_kind === '服务器') {
    const s = servers.find((x) => x.id === part.current_loc_id)
    return s ? `${s.asset_no}（${s.run_status}）` : `服务器#${part.current_loc_id}`
  }
  if (part.current_loc_kind === '外单位') {
    const o = orgs.find((x) => x.id === part.current_loc_id)
    return o ? o.org_name : `外单位#${part.current_loc_id}`
  }
  return part.current_loc_kind
}

export default function PartDetail() {
  const { id } = useParams()
  const nav = useNavigate()
  const [part, setPart] = useState(null)
  const [moves, setMoves] = useState([])
  const [servers, setServers] = useState([])
  const [locs, setLocs] = useState([])
  const [orgs, setOrgs] = useState([])
  const [error, setError] = useState('')

  useEffect(() => {
    Promise.all([
      api.get(`/parts/${id}`),
      api.get(`/parts/${id}/movements`),
      api.get('/servers'),
      api.get('/storage-locations'),
      api.get('/external-orgs'),
    ])
      .then(([p, m, s, l, o]) => {
        setPart(p)
        setMoves(m)
        setServers(s)
        setLocs(l)
        setOrgs(o)
      })
      .catch((e) => setError(e.message))
  }, [id])

  const actions = useMemo(() => {
    if (!part) return []
    const links = [{ to: `/parts/${id}/history`, label: '查看履历' }]
    if (part.current_status === '在库') {
      links.push(
        { to: `/parts/${id}/install`, label: '装机' },
        { to: `/parts/${id}/loan`, label: '借出' },
        { to: `/parts/${id}/transfer`, label: '调拨' },
        { to: `/parts/${id}/scrap`, label: '报废' },
        { to: `/parts/${id}/damage`, label: '报损' },
      )
    } else if (part.current_status === '在用') {
      links.push({ to: `/parts/${id}/uninstall`, label: '拆下' })
    } else if (part.current_status === '损坏') {
      links.push({ to: `/parts/${id}/scrap`, label: '报废' })
    } else if (part.current_status === '借出') {
      links.push({ to: `/parts/${id}/return`, label: '归还' })
    }
    return links
  }, [part, id])

  const recentMoves = moves.slice(-8).reverse()

  return (
    <div className="pd-page">
      <button type="button" className="back-link" onClick={() => nav('/')}>
        返回配件列表
      </button>

      {error && <div className="error">{error}</div>}

      {!part ? (
        !error && <p className="muted">加载中…</p>
      ) : (
        <>
          <header className="pd-header">
            <div>
              <p className="pd-kicker">{part.model?.category || '配件'}详情</p>
              <h2>{part.fixed_asset_no}</h2>
              <p className="muted">
                {part.model?.model_name || `型号#${part.model_id}`}
                {part.model?.brand ? ` · ${part.model.brand}` : ''}
                {part.is_overdue ? ' · 借出超期' : ''}
              </p>
            </div>
            <div className="pd-badges">
              <span className="pl-badge pl-badge-info">{part.current_status}</span>
              <span className="pl-badge">{part.allocatable_flag || '—'}</span>
            </div>
          </header>

          <div className="pd-actions">
            {actions.map((a) => (
              <Link key={a.to} className="pd-action" to={a.to}>
                {a.label}
              </Link>
            ))}
          </div>

          <section className="pd-section">
            <h3>当前状态</h3>
            <dl className="pd-grid">
              <Field label="状态">{part.current_status}</Field>
              <Field label="可调配">{part.allocatable_flag}</Field>
              <Field label="位置种类">{part.current_loc_kind || '—'}</Field>
              <Field label="当前位置">{locLabel(part, servers, locs, orgs)}</Field>
              <Field label="产权单位">{part.owner_unit}</Field>
              <Field label="运维部门">{part.responsible_group}</Field>
            </dl>
          </section>

          <section className="pd-section">
            <h3>型号规格</h3>
            <dl className="pd-grid">
              <Field label="类型">{part.model?.category}</Field>
              <Field label="型号">{part.model?.model_name}</Field>
              <Field label="品牌">{part.model?.brand}</Field>
              <Field label="厂商料号 PN">{part.model?.pn}</Field>
              <Field label="规格">{formatSpec(part.model?.spec)}</Field>
            </dl>
          </section>

          <section className="pd-section">
            <h3>采购与公共信息</h3>
            <dl className="pd-grid">
              <Field label="序列号 SN">{part.serial_no}</Field>
              <Field label="来源">{part.source_type}</Field>
              <Field label="供应商">{part.supplier}</Field>
              <Field label="合同号">{part.contract_no}</Field>
              <Field label="所属项目">{part.project}</Field>
              <Field label="采购金额">
                {part.purchase_amount != null ? String(part.purchase_amount) : '—'}
              </Field>
              <Field label="采购日期">{part.purchase_date}</Field>
              <Field label="维保到期">{part.warranty_expiry}</Field>
              <Field label="敏感标记">{part.sensitivity || '无'}</Field>
            </dl>
          </section>

          <section className="pd-section">
            <div className="pd-section-head">
              <h3>最近履历</h3>
              <Link to={`/parts/${id}/history`}>全部履历 →</Link>
            </div>
            {recentMoves.length ? (
              <ul className="timeline">
                {recentMoves.map((m) => (
                  <li key={m.id}>
                    <strong>{m.event_type}</strong> {m.status_from || '∅'} → {m.status_to}
                    <div className="muted">
                      {m.occurred_at}
                      {m.remark ? ` · ${m.remark}` : ''}
                    </div>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="muted">暂无履历</p>
            )}
          </section>
        </>
      )}
    </div>
  )
}
