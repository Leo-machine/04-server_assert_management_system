export function level2Categories(tree) {
  return (tree || []).flatMap((root) =>
    (root.children || [])
      .filter((child) => child.enabled)
      .map((child) => ({ ...child, domain: root.name, domainId: root.id })),
  )
}

export function assetScopeLabel(ids, tree) {
  if (!ids?.length) return '通用（全部专业与类别）'
  const selected = new Set(ids.map(Number))
  return level2Categories(tree)
    .filter((item) => selected.has(item.id))
    .map((item) => `${item.domain} / ${item.name}`)
    .join('、') || '未匹配目录'
}
