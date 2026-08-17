import { useEffect, useMemo, useState } from 'react'

export function usePagination(items, initialPageSize = 10) {
  const [page, setPage] = useState(1)
  const [pageSize, setPageSizeState] = useState(initialPageSize)
  const total = items.length
  const pageCount = Math.max(1, Math.ceil(total / pageSize))

  useEffect(() => { setPage(1) }, [items])
  useEffect(() => { setPage((current) => Math.min(current, pageCount)) }, [pageCount])

  const pageItems = useMemo(() => {
    const start = (page - 1) * pageSize
    return items.slice(start, start + pageSize)
  }, [items, page, pageSize])

  function setPageSize(nextSize) {
    setPageSizeState(Number(nextSize))
    setPage(1)
  }

  return {
    page,
    pageSize,
    pageCount,
    pageItems,
    total,
    from: total ? (page - 1) * pageSize + 1 : 0,
    to: Math.min(page * pageSize, total),
    setPage,
    setPageSize,
  }
}
