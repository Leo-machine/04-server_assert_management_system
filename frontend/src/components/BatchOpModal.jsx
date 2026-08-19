import { useEffect, useState } from 'react'
import { api, getStoredUser } from '../api'
import ApproverSelects, { useDefaultApprovers } from './ApproverSelects'
import { SCRAP_REASONS } from '../lib/categories'
import { isSuperAdmin } from '../lib/roles'

const OP_META = {
  install: { title: '批量装机', need: null },
  uninstall: { title: '批量拆下', need: null },
  loan: { title: '批量借出（三级审批）', need: 'approval' },
  transfer: { title: '批量调拨（三级审批）', need: 'approval' },
  scrap: { title: '批量报废（三级审批）', need: 'approval' },
  damage: { title: '批量报损', need: null },
}

// props: op, targets(已按状态过滤), servers, orgs, users, onClose, onDone(summary)
function locLabel(server, locs) {
  if (!server?.location_id || !locs) return ''
  const l = locs.find((x) => x.id === server.location_id)
  return l ? `${l.warehouse}/${l.slot}` : ''
}

export default function BatchOpModal({ op, targets: targetsProp, servers, orgs, users, locs, onClose, onDone }) {
  const meta = OP_META[op]
  const superAdmin = isSuperAdmin(getStoredUser())
  const displayTitle = superAdmin && meta.need === 'approval'
    ? meta.title.replace('（三级审批）', '（超级管理员免审批）')
    : meta.title
  const [frozenTargets] = useState(() => [...(targetsProp || [])])
  const targets = frozenTargets
  const [serverId, setServerId] = useState('')
  const [storageLocationId, setStorageLocationId] = useState('')
  const [damaged, setDamaged] = useState(false)
  const [orgId, setOrgId] = useState('')
  const [date, setDate] = useState(() => {
    const d = new Date()
    d.setDate(d.getDate() + 14)
    return d.toISOString().slice(0, 10)
  })
  const [reasonCode, setReasonCode] = useState(SCRAP_REASONS[0])
  const [attachment, setAttachment] = useState('')
  const [remark, setRemark] = useState('')
  const [approvers, setApprovers] = useDefaultApprovers(users)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    if (servers.length && !serverId) setServerId(String(servers[0].id))
    if (orgs.length && !orgId) setOrgId(String(orgs[0].id))
    if (locs.length && !storageLocationId) setStorageLocationId(String(locs[0].id))
  }, [servers, orgs, locs, serverId, orgId, storageLocationId])

  const gpuCount = targets.filter((p) => p.model?.category === '算力卡').length

  async function submit() {
    setError('')
    if (op === 'install') {
      if (!Number(serverId)) {
        setError('请选择目标服务器')
        return
      }
    }
    if (op === 'uninstall' && !Number(storageLocationId)) {
      setError('请选择拆下后的目标库位')
      return
    }
    if ((op === 'loan' || op === 'transfer') && !Number(orgId)) {
      setError('请选择外单位')
      return
    }
    if (op === 'damage' && !remark.trim()) {
      setError('报损必须填写损坏情况说明')
      return
    }
    if (meta.need === 'approval' && !superAdmin) {
      const ids = approvers.map(Number)
      if (ids.some((n) => !n) || new Set(ids).size !== 3) {
        setError('请选择三位互不相同的审批人（须为领导）')
        return
      }
    }
    if (op === 'scrap' && gpuCount > 0 && !attachment.trim()) {
      setError(`所选含 ${gpuCount} 件算力卡，报废必须提供影像证据（attachment_ref）`)
      return
    }
    setBusy(true)
    let okN = 0
    const errors = []
    for (const p of targets) {
      try {
        if (op === 'install') {
          await api.post(`/parts/${p.id}/install`, { server_id: Number(serverId), remark: remark || null })
        } else if (op === 'uninstall') {
          await api.post(`/parts/${p.id}/uninstall`, {
            storage_location_id: Number(storageLocationId),
            damaged,
            remark: remark || null,
          })
        } else if (op === 'damage') {
          await api.post(`/parts/${p.id}/damage`, { remark: remark.trim() })
        } else if (op === 'loan') {
          await api.post('/approvals/loan', {
            part_id: p.id,
            dest_org_id: Number(orgId),
            expected_return_date: date,
            approver_ids: superAdmin ? [] : approvers.map(Number),
            remark: remark || null,
          })
        } else if (op === 'transfer') {
          await api.post('/approvals/transfer', {
            part_id: p.id,
            dest_org_id: Number(orgId),
            approver_ids: superAdmin ? [] : approvers.map(Number),
            remark: remark || null,
          })
        } else if (op === 'scrap') {
          await api.post('/approvals/scrap', {
            part_id: p.id,
            reason_code: reasonCode,
            approver_ids: superAdmin ? [] : approvers.map(Number),
            attachment_ref: attachment || null,
            remark: remark || null,
          })
        }
        okN += 1
      } catch (e) {
        errors.push(`${p.fixed_asset_no}: ${e.message}`)
      }
    }
    setBusy(false)
    onDone({ okN, errors, opTitle: meta.title })
  }

  return (
    <div className="pl-modal-mask" onClick={busy ? undefined : onClose}>
      <div className="pl-modal" onClick={(e) => e.stopPropagation()}>
        <h3>{displayTitle}</h3>
        <p className="muted">
          将处理 <strong>{targets.length}</strong> 件：
          {targets.slice(0, 6).map((p) => p.fixed_asset_no).join('、')}
          {targets.length > 6 ? ` 等 ${targets.length} 件` : ''}
        </p>
        {error && <div className="error">{error}</div>}
        {superAdmin && meta.need === 'approval' && <div className="super-admin-bypass"><strong>超级管理员直通</strong><span>所选业务将逐项立即生效并保留完整操作履历。</span></div>}

        {op === 'install' && (
          <label>
            目标服务器
            <select value={serverId} onChange={(e) => setServerId(e.target.value)} disabled={busy}>
              {!servers.length && <option value="">暂无服务器</option>}
              {servers.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.asset_no}（{locLabel(s, locs) || s.location_id} · {s.run_status}）
                </option>
              ))}
            </select>
          </label>
        )}
        {op === 'uninstall' && (
          <>
            <label>
              拆下后存放位置
              <select value={storageLocationId} onChange={(e) => setStorageLocationId(e.target.value)} disabled={busy}>
                {!locs.length && <option value="">暂无可用库位</option>}
                {locs.map((loc) => <option key={loc.id} value={loc.id}>{loc.warehouse}/{loc.slot}{loc.location_type ? ` · ${loc.location_type}` : ''}</option>)}
              </select>
            </label>
            <label className="batch-uninstall-damaged">
              <input type="checkbox" checked={damaged} onChange={(e) => setDamaged(e.target.checked)} disabled={busy} />
              <span><strong>拆下后标记为损坏</strong><small>不勾选则恢复为“在库”状态</small></span>
            </label>
          </>
        )}
        {(op === 'loan' || op === 'transfer') && (
          <label>
            外单位
            <select value={orgId} onChange={(e) => setOrgId(e.target.value)} disabled={busy}>
              {!orgs.length && <option value="">暂无外单位</option>}
              {orgs.map((o) => (
                <option key={o.id} value={o.id}>{o.org_name}</option>
              ))}
            </select>
          </label>
        )}
        {op === 'loan' && (
          <label>
            预期归还日
            <input type="date" value={date} onChange={(e) => setDate(e.target.value)} />
          </label>
        )}
        {op === 'scrap' && (
          <>
            <label>
              报废缘由
              <select value={reasonCode} onChange={(e) => setReasonCode(e.target.value)}>
                {SCRAP_REASONS.map((r) => (
                  <option key={r}>{r}</option>
                ))}
              </select>
            </label>
            <label>
              影像证据（算力卡必填）
              <input value={attachment} onChange={(e) => setAttachment(e.target.value)} placeholder="如：WO-2026-0805-照片.zip" />
            </label>
          </>
        )}
        {meta.need === 'approval' && !superAdmin && (
          <ApproverSelects users={users} value={approvers} onChange={setApprovers} />
        )}
        <label>
          备注{op === 'damage' ? '（损坏情况说明，必填）' : '（可选）'}
          <textarea value={remark} onChange={(e) => setRemark(e.target.value)} rows={2} />
        </label>
        <div className="row-actions" style={{ marginTop: '0.5rem' }}>
          <button type="button" disabled={busy} onClick={submit}>
            {busy ? `处理中…（${targets.length} 件）` : `确认${displayTitle.split('（')[0]} ${targets.length} 件`}
          </button>
          <button type="button" className="secondary" disabled={busy} onClick={onClose}>取消</button>
        </div>
      </div>
    </div>
  )
}
