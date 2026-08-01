/**
 * 列表通用工具条：模糊搜索 + 可选批量操作区。
 */
export default function ListToolbar({
  query,
  onQueryChange,
  placeholder = '模糊搜索…',
  resultText,
  selectedCount = 0,
  onClearSelection,
  batchActions,
  children,
}) {
  return (
    <div className="lt-bar">
      <div className="lt-search">
        <input
          type="search"
          value={query}
          onChange={(e) => onQueryChange(e.target.value)}
          placeholder={placeholder}
          aria-label="模糊搜索"
        />
        {query && (
          <button
            type="button"
            className="lt-clear-q"
            onClick={() => onQueryChange('')}
            title="清除搜索"
          >
            ×
          </button>
        )}
      </div>
      <div className="lt-meta">
        {resultText}
        {children}
      </div>
      {selectedCount > 0 && (
        <div className="lt-batch">
          <span className="lt-batch-count">已选 {selectedCount}</span>
          {batchActions}
          {onClearSelection && (
            <button type="button" className="secondary" onClick={onClearSelection}>
              取消选择
            </button>
          )}
        </div>
      )}
    </div>
  )
}
