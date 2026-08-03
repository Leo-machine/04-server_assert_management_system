import { useEffect, useRef } from 'react'

/** 表头点击筛选下拉（配件列表 / 服务器管理共用） */
export default function HeaderFilter({ label, value, options, totals, open, onToggle, onSelect }) {
  const ref = useRef(null)
  useEffect(() => {
    if (!open) return undefined
    function onDoc(e) {
      if (ref.current && !ref.current.contains(e.target)) onToggle(false)
    }
    document.addEventListener('mousedown', onDoc)
    return () => document.removeEventListener('mousedown', onDoc)
  }, [open, onToggle])

  return (
    <th className={`pl-th-filter ${value ? 'is-filtered' : ''}`} ref={ref}>
      <button
        type="button"
        className="pl-th-btn"
        onClick={() => onToggle(!open)}
        aria-haspopup="listbox"
        aria-expanded={open}
      >
        <span>{label}</span>
        {value ? <em className="pl-th-val">{value}</em> : null}
        <span className="pl-th-caret" aria-hidden>▾</span>
      </button>
      {open && (
        <div className="pl-th-menu" role="listbox">
          <button
            type="button"
            className={!value ? 'is-on' : ''}
            onClick={() => {
              onSelect('')
              onToggle(false)
            }}
          >
            全部
          </button>
          {options.map((opt) => {
            const n = totals[opt] || 0
            if (!n && value !== opt) return null
            return (
              <button
                key={opt}
                type="button"
                className={value === opt ? 'is-on' : ''}
                onClick={() => {
                  onSelect(value === opt ? '' : opt)
                  onToggle(false)
                }}
              >
                <span>{opt}</span>
                <em>{n}</em>
              </button>
            )
          })}
        </div>
      )}
    </th>
  )
}
