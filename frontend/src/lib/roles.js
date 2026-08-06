/** 与后端 enums 对齐的角色常量（前端门禁唯一来源） */
export const ROLE_SUPPLIER = '设备供应商'
export const ROLE_MAINTENANCE = '外委运维'
export const ROLE_OPERATIONS = '主业运维'
export const ROLE_LEADER = '领导'

/** 业务运维：外委 = 主业；领导具备同等业务权限 */
export const OPS_ROLES = new Set([ROLE_MAINTENANCE, ROLE_OPERATIONS, ROLE_LEADER])
/** 仅领导可审批 */
export const APPROVER_ROLES = new Set([ROLE_LEADER])
/** 基础数据写（型号/品牌/供应商/库位/服务器建档） */
export const MASTER_DATA_ROLES = new Set([ROLE_LEADER])
/** 入库 */
export const INBOUND_ROLES = new Set([
  ROLE_SUPPLIER,
  ROLE_MAINTENANCE,
  ROLE_OPERATIONS,
  ROLE_LEADER,
])

export function hasRole(user, allowed) {
  const role = user?.role || ''
  if (allowed instanceof Set) return allowed.has(role)
  return (allowed || []).includes(role)
}

export function isSupplier(user) {
  return (user?.role || '') === ROLE_SUPPLIER
}

export function isLeader(user) {
  return (user?.role || '') === ROLE_LEADER
}

/** 登录后默认落地页 */
export function homePathFor(user) {
  if (isSupplier(user)) return '/inbound'
  return '/dashboard'
}
