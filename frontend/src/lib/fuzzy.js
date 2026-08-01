/** 轻量模糊匹配：忽略大小写/空白，按字符子序列匹配中文与编号。 */
export function normalizeQuery(q) {
  return String(q || '')
    .trim()
    .toLowerCase()
    .replace(/\s+/g, '')
}

export function fuzzyMatch(text, query) {
  const q = normalizeQuery(query)
  if (!q) return true
  const hay = String(text ?? '')
    .toLowerCase()
    .replace(/\s+/g, '')
  if (!hay) return false
  if (hay.includes(q)) return true
  // 子序列：支持「三星32」命中「三星 32GB DDR4」
  let i = 0
  for (const ch of hay) {
    if (ch === q[i]) i += 1
    if (i >= q.length) return true
  }
  return false
}

/** fields: string[] 或 (row) => string[] */
export function filterByQuery(rows, query, fields) {
  const q = normalizeQuery(query)
  if (!q) return rows
  return rows.filter((row) => {
    const values = typeof fields === 'function' ? fields(row) : fields.map((k) => row[k])
    return values.some((v) => fuzzyMatch(v, q))
  })
}
