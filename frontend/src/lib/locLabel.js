/** 配件当前位置展示文案 */
export function locLabel(part, servers = [], locs = [], orgs = []) {
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
