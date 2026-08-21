export function level2Categories(tree) {
  return (tree || []).flatMap((root) =>
    (root.children || [])
      .filter((child) => child.enabled)
      .map((child) => ({ ...child, domain: root.name, domainId: root.id })),
  )
}

/** 根据一级专业筛选其二级设备类别，兼容表单中的字符串 id。 */
export function level2CategoriesForDomain(tree, domainId) {
  const scopes = level2Categories(tree)
  return domainId
    ? scopes.filter((scope) => String(scope.domainId) === String(domainId))
    : scopes
}

/**
 * 从二级资产目录派生当前已接入业务的具体类型。
 *
 * 三级目录通过 business_category 与型号/品牌等业务类型关联；服务器整机
 * 是二级“服务器类”自身承载的特殊类型。品牌管理和型号管理必须共用这套
 * 规则，避免切换专业后仍显示固定的全量类别。
 */
export function managedCategoriesForScopes(scopes) {
  return [...new Set((scopes || []).flatMap((scope) => [
    ...(scope.code === 'DIGITAL_SERVER' ? ['服务器'] : []),
    ...managedLeafCategoriesForScopes([scope]),
  ]))]
}

/** 仅返回三级目录已关联的配件/具体类型，不混入二级设备整机。 */
export function managedLeafCategoriesForScopes(scopes) {
  return [...new Set((scopes || []).flatMap((scope) =>
    (scope.children || [])
      .filter((child) => child.enabled)
      .map((child) => child.business_category)
      .filter(Boolean),
  ))]
}

export function assetScopeLabel(ids, tree) {
  if (!ids?.length) return '通用（全部专业与类别）'
  const selected = new Set(ids.map(Number))
  return level2Categories(tree)
    .filter((item) => selected.has(item.id))
    .map((item) => `${item.domain} / ${item.name}`)
    .join('、') || '未匹配目录'
}
