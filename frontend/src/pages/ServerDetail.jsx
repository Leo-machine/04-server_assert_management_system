import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { api } from '../api'

function Field({ label, children }) {
  return (
    <div className="pd-field">
      <dt>{label}</dt>
      <dd>{children ?? '—'}</dd>
    </div>
  )
}

export default function ServerDetail() {
  const { id } = useParams()
  const nav = useNavigate()
  const [server, setServer] = useState(null)
  const [locs, setLocs] = useState([])
  const [error, setError] = useState('')

  function locName(s) {
    if (!s?.location_id) return '-'
    const l = locs.find((x) => x.id === s.location_id)
    return l ? `${l.warehouse}/${l.slot}` : `ID#${s.location_id}`
  }

  useEffect(() => {
    Promise.all([
      api.get(`/servers/${id}`),
      api.get('/storage-locations'),
    ])
      .then(([srv, ls]) => {
        setServer(srv)
        setLocs(ls)
      })
      .catch((e) => setError(e.message))
  }, [id])

  const parts = server?.installed_parts || []
  const byCat = server?.installed_by_category || {}

  return (
    <div className="pd-page">
      <button type="button" className="back-link" onClick={() => nav('/devices')}>
        返回设备管理
      </button>

      {error && <div className="error">{error}</div>}

      {!server ? (
        !error && <p className="muted">加载中…</p>
      ) : (
        <>
          <header className="pd-header">
            <div>
              <p className="pd-kicker">服务器详情</p>
              <h2>{server.asset_no}</h2>
              <p className="muted">
                {server.model || '未填型号'}
                {' · '}{locName(server)}
              </p>
            </div>
            <div className="pd-badges">
              <span className={`badge ${server.run_status === '投运' ? 'warn' : 'ok'}`}>
                {server.run_status}
              </span>
              <span className="pl-badge pl-badge-info">
                已装 {server.installed_count ?? parts.length} 件
              </span>
            </div>
          </header>

          <section className="pd-section">
            <h3>基本信息</h3>
            <dl className="pd-grid">
              <Field label="资产编号">{server.asset_no}</Field>
              <Field label="型号">{server.model}</Field>
              <Field label="SN">{server.serial_no}</Field>
              <Field label="部署位置">{locName(server)}</Field>
              <Field label="运维部门">{server.responsible_group}</Field>
              <Field label="运行状态">{server.run_status}</Field>
            </dl>
          </section>

          <section className="pd-section">
            <h3>机箱插槽规格</h3>
            <dl className="pd-grid">
              <Field label="硬盘插槽数">{server.disk_slot_count}</Field>
              <Field label="硬盘接口">{server.disk_interface}</Field>
              <Field label="内存插槽数">{server.mem_slot_count}</Field>
              <Field label="内存支持代际">{server.mem_ddr_gens}</Field>
              <Field label="PCIe 插槽数">{server.pcie_slot_count}</Field>
              <Field label="NVMe 插槽数">{server.nvme_slot_count}</Field>
              <Field label="NVMe 接口">{server.nvme_interface}</Field>
            </dl>
          </section>

          <section className="pd-section">
            <h3>合同与采购</h3>
            <dl className="pd-grid">
              <Field label="供应商">{server.supplier}</Field>
              <Field label="合同号">{server.contract_no}</Field>
              <Field label="所属项目">{server.project}</Field>
              <Field label="产权单位">{server.owner_unit}</Field>
              <Field label="维保到位">{server.warranty_expiry}</Field>
              <Field label="设备到货日期">{server.arrival_date}</Field>
              <Field label="采购金额">
                {server.purchase_amount != null ? `¥ ${server.purchase_amount}` : '—'}
              </Field>
            </dl>
          </section>

          <section className="pd-section">
            <h3>
              已装配件
              {Object.keys(byCat).length > 0 && (
                <span className="muted" style={{ fontWeight: 400, marginLeft: '0.5rem' }}>
                  （
                  {Object.entries(byCat)
                    .map(([c, n]) => `${c} ${n}`)
                    .join(' · ')}
                  ）
                </span>
              )}
            </h3>
            {parts.length === 0 ? (
              <p className="muted">当前无配件安装在此服务器上。</p>
            ) : (
              <table className="pl-table">
                <thead>
                  <tr>
                    <th>资产编号</th>
                    <th>类型</th>
                    <th>型号</th>
                    <th>插槽</th>
                    <th>状态</th>
                    <th>来源</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {parts.map((p) => (
                    <tr key={p.id}>
                      <td>
                        <Link to={`/parts/${p.id}`}>{p.fixed_asset_no}</Link>
                      </td>
                      <td>{p.category || '—'}</td>
                      <td>
                        {p.brand ? `${p.brand} · ` : ''}
                        {p.model_name || '—'}
                      </td>
                      <td>{p.slot || '—'}</td>
                      <td>{p.current_status}</td>
                      <td>{p.source_type || '—'}</td>
                      <td>
                        <Link to={`/parts/${p.id}`}>详情</Link>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </section>
        </>
      )}
    </div>
  )
}
