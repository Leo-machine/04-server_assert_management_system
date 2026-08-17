function pageNumbers(page, pageCount) {
  if (pageCount <= 7) return Array.from({ length: pageCount }, (_, index) => index + 1)
  const values = new Set([1, pageCount, page - 1, page, page + 1])
  const sorted = [...values].filter((value) => value >= 1 && value <= pageCount).sort((a, b) => a - b)
  const result = []
  sorted.forEach((value, index) => {
    if (index && value - sorted[index - 1] > 1) result.push(`ellipsis-${value}`)
    result.push(value)
  })
  return result
}

export default function Pagination({ pagination, pageSizeOptions = [10, 20, 50] }) {
  const { page, pageSize, pageCount, total, from, to, setPage, setPageSize } = pagination
  if (!total) return null

  return (
    <nav className="pagination" aria-label="分页导航">
      <div className="pagination-summary">
        第 <strong>{from}</strong>–<strong>{to}</strong> 条，共 <strong>{total}</strong> 条
      </div>
      <div className="pagination-controls">
        <button type="button" className="pagination-arrow" disabled={page === 1} onClick={() => setPage(page - 1)} aria-label="上一页">‹</button>
        {pageNumbers(page, pageCount).map((value) => typeof value === 'string'
          ? <span key={value} className="pagination-ellipsis">…</span>
          : <button key={value} type="button" className={page === value ? 'active' : ''} onClick={() => setPage(value)} aria-current={page === value ? 'page' : undefined}>{value}</button>)}
        <button type="button" className="pagination-arrow" disabled={page === pageCount} onClick={() => setPage(page + 1)} aria-label="下一页">›</button>
      </div>
      <label className="pagination-size">
        每页
        <select value={pageSize} onChange={(event) => setPageSize(event.target.value)}>
          {pageSizeOptions.map((size) => <option key={size} value={size}>{size} 条</option>)}
        </select>
      </label>
    </nav>
  )
}
