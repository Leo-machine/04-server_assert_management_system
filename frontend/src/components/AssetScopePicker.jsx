export default function AssetScopePicker({ tree, value = [], onChange, single = false }) {
  const selected = new Set((value || []).map(Number))
  function toggle(id) {
    if (single) {
      onChange(selected.has(id) ? [] : [id])
      return
    }
    const next = new Set(selected)
    if (next.has(id)) next.delete(id)
    else next.add(id)
    onChange([...next])
  }
  return (
    <div className="asset-scope-picker">
      {(tree || []).filter((root) => root.enabled).map((root) => (
        <section key={root.id}>
          <strong>{root.name}</strong>
          <div className="chip-row">
            {(root.children || []).filter((child) => child.enabled).map((child) => (
              <button key={child.id} type="button" className={`chip ${selected.has(child.id) ? 'active' : ''}`} onClick={() => toggle(child.id)}>
                {child.name}
              </button>
            ))}
            {!(root.children || []).some((child) => child.enabled) && <small>暂无二级类别</small>}
          </div>
        </section>
      ))}
    </div>
  )
}
