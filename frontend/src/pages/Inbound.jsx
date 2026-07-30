import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api'

export default function Inbound() {
  const nav = useNavigate()
  const [models, setModels] = useState([])
  const [locs, setLocs] = useState([])
  const [form, setForm] = useState({
    model_id: '',
    fixed_asset_no: '',
    storage_location_id: '',
    source_type: '单独合同',
    responsible_group: '基础组',
    serial_no: '',
    remark: '',
  })
  const [error, setError] = useState('')
  const [ok, setOk] = useState('')

  useEffect(() => {
    Promise.all([api.get('/part-models'), api.get('/storage-locations')]).then(
      ([m, l]) => {
        setModels(m)
        setLocs(l)
        setForm((f) => ({
          ...f,
          model_id: String(m[0]?.id || ''),
          storage_location_id: String(l[0]?.id || ''),
        }))
      },
    )
  }, [])

  async function onSubmit(e) {
    e.preventDefault()
    setError('')
    setOk('')
    try {
      const part = await api.post('/parts/inbound', {
        ...form,
        model_id: Number(form.model_id),
        storage_location_id: Number(form.storage_location_id),
        serial_no: form.serial_no || null,
        remark: form.remark || null,
      })
      setOk(`入库成功：${part.fixed_asset_no}`)
      setTimeout(() => nav('/'), 800)
    } catch (err) {
      setError(err.message)
    }
  }

  return (
    <div className="panel">
      <h2>入库</h2>
      {error && <div className="error">{error}</div>}
      {ok && <div className="ok-msg">{ok}</div>}
      <form onSubmit={onSubmit}>
        <label>
          型号
          <select
            value={form.model_id}
            onChange={(e) => setForm({ ...form, model_id: e.target.value })}
            required
          >
            {models.map((m) => (
              <option key={m.id} value={m.id}>
                [{m.category}] {m.model_name}
              </option>
            ))}
          </select>
        </label>
        <label>
          固定资产编号
          <input
            value={form.fixed_asset_no}
            onChange={(e) => setForm({ ...form, fixed_asset_no: e.target.value })}
            required
            placeholder="FA-XXX-0000"
          />
        </label>
        <label>
          库位
          <select
            value={form.storage_location_id}
            onChange={(e) => setForm({ ...form, storage_location_id: e.target.value })}
            required
          >
            {locs.map((l) => (
              <option key={l.id} value={l.id}>
                {l.warehouse} / {l.slot}
              </option>
            ))}
          </select>
        </label>
        <label>
          来源
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
          责任组
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
          序列号（可选）
          <input
            value={form.serial_no}
            onChange={(e) => setForm({ ...form, serial_no: e.target.value })}
          />
        </label>
        <label>
          备注
          <textarea
            value={form.remark}
            onChange={(e) => setForm({ ...form, remark: e.target.value })}
            rows={2}
          />
        </label>
        <button type="submit">确认入库</button>
      </form>
    </div>
  )
}
