import { useCallback, useMemo, useState } from 'react'

/** 表格行多选：id 为 string|number */
export function useSelection(visibleIds) {
  const [selected, setSelected] = useState(() => new Set())

  const visibleSet = useMemo(() => new Set(visibleIds), [visibleIds])

  const selectedVisible = useMemo(
    () => [...selected].filter((id) => visibleSet.has(id)),
    [selected, visibleSet],
  )

  const allVisibleSelected =
    visibleIds.length > 0 && visibleIds.every((id) => selected.has(id))

  const someVisibleSelected =
    visibleIds.some((id) => selected.has(id)) && !allVisibleSelected

  const toggle = useCallback((id) => {
    setSelected((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }, [])

  const toggleAllVisible = useCallback(() => {
    setSelected((prev) => {
      const next = new Set(prev)
      if (visibleIds.length && visibleIds.every((id) => next.has(id))) {
        for (const id of visibleIds) next.delete(id)
      } else {
        for (const id of visibleIds) next.add(id)
      }
      return next
    })
  }, [visibleIds])

  const clear = useCallback(() => setSelected(new Set()), [])

  const isSelected = useCallback((id) => selected.has(id), [selected])

  return {
    selected,
    selectedVisible,
    selectedCount: selectedVisible.length,
    allVisibleSelected,
    someVisibleSelected,
    toggle,
    toggleAllVisible,
    clear,
    isSelected,
  }
}
