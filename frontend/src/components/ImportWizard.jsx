import { useRef, useState } from 'react'
import { api, downloadCsv } from '../api'

// 通用两段式批量导入向导：下载模板/导出 → 上传 CSV → 表格化校验预览 → 确认导入
// props:
//   templateUrl  模板下载地址（必填，如 /servers/import-template.csv）
//   exportUrl    数据导出地址（可选）
//   importUrl    批量导入地址（如 /servers/batch-import，内部自动拼 dry_run）
//   previewCols  预览表格列 [{key, label}]（key 对应行 data 字段）
//   onCommitted  导入成功后回调
export default function ImportWizard({ templateUrl, exportUrl, importUrl, previewCols, onCommitted }) {
  const fileRef = useRef(null)
  const [fileContent, setFileContent] = useState('')
  const [fileName, setFileName] = useState('')
  const [report, setReport] = useState(null) // {rows, total, valid, committed, created}
  const [error, setError] = useState('')
  const [msg, setMsg] = useState('')
  const [busy, setBusy] = useState(false)

  function download(url, fallbackName) {
    downloadCsv(url, fallbackName).catch((e) => setError(e.message))
  }

  function pickFile(e) {
    const f = e.target.files?.[0]
    setReport(null)
    setMsg('')
    setError('')
    if (!f) return
    setFileName(f.name)
    const reader = new FileReader()
    reader.onload = () => {
      setFileContent(String(reader.result || ''))
    }
    reader.readAsText(f, 'utf-8')
  }

  async function preview() {
    if (!fileContent) return
    setBusy(true)
    setError('')
    try {
      const r = await api.post(`${importUrl}?dry_run=true`, { content: fileContent })
      setReport(r)
      setMsg('')
    } catch (e) {
      setError(e.message)
      setReport(null)
    } finally {
      setBusy(false)
    }
  }

  async function commit() {
    setBusy(true)
    setError('')
    try {
      const r = await api.post(`${importUrl}?dry_run=false`, { content: fileContent })
      setReport(null)
      setFileContent('')
      setFileName('')
      if (fileRef.current) fileRef.current.value = ''
      setMsg(`导入完成：成功 ${r.created} 条`)
      onCommitted?.()
    } catch (e) {
      setError(e.message)
    } finally {
      setBusy(false)
    }
  }

  function reset() {
    setReport(null)
    setFileContent('')
    setFileName('')
    setError('')
    if (fileRef.current) fileRef.current.value = ''
  }

  function cellHasError(colLabel, errors) {
    if (!errors?.length) return false
    return errors.some((e) => e.includes(`【${colLabel}】`) || e.includes(colLabel))
  }

  return (
    <div className="import-wizard">
      <div className="row-actions">
        <button type="button" className="secondary" onClick={() => download(templateUrl, 'import_template.csv')}>
          下载导入模板
        </button>
        {exportUrl && (
          <button type="button" className="secondary" onClick={() => download(exportUrl, 'export.csv')}>
            导出 CSV
          </button>
        )}
        <label className="secondary" style={{ display: 'inline-flex', alignItems: 'center', gap: '0.4rem', cursor: 'pointer', padding: '0.35rem 0.75rem', border: '1px solid var(--border, #d0d0d0)', borderRadius: '6px' }}>
          选择 CSV 文件
          <input ref={fileRef} type="file" accept=".csv,text/csv,text/plain" style={{ display: 'none' }} onChange={pickFile} />
        </label>
        {fileName && <span className="muted">{fileName}</span>}
        {fileContent && !report && (
          <button type="button" disabled={busy} onClick={preview}>
            {busy ? '校验中…' : '开始校验'}
          </button>
        )}
        {fileContent && (
          <button type="button" className="secondary" onClick={reset}>清除</button>
        )}
      </div>

      {error && <div className="error">{error}</div>}
      {msg && <div className="ok-msg">{msg}</div>}

      {report && (
        <div className="import-report" style={{ marginTop: '0.75rem' }}>
          <p className="muted">
            校验结果：共 <strong>{report.total}</strong> 行，
            <strong style={{ color: report.valid === report.total ? 'green' : '#b00020' }}>
              通过 {report.valid} 行
            </strong>
            {report.valid !== report.total && (
              <>，未通过 {report.total - report.valid} 行（整批不入库，请按【字段】提示修正 CSV 后重新上传）</>
            )}
          </p>
          <table>
            <thead>
              <tr>
                <th>行号</th>
                {previewCols.map((c) => (
                  <th key={c.key}>{c.label}</th>
                ))}
                <th>校验</th>
              </tr>
            </thead>
            <tbody>
              {report.rows.map((r) => (
                <tr key={r.line} className={r.ok ? '' : 'is-invalid'}>
                  <td>{r.line}</td>
                  {previewCols.map((c) => (
                    <td
                      key={c.key}
                      className={
                        !r.ok && cellHasError(c.label, r.errors) ? 'import-cell-err' : ''
                      }
                    >
                      {r.data?.[c.key] || '—'}
                    </td>
                  ))}
                  <td>
                    {r.ok ? (
                      <span className="badge ok">通过</span>
                    ) : (
                      <ul className="import-err-list">
                        {(r.errors || []).map((e) => (
                          <li key={e}>{e}</li>
                        ))}
                      </ul>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="row-actions" style={{ marginTop: '0.5rem' }}>
            <button
              type="button"
              disabled={busy || report.valid !== report.total}
              title={report.valid !== report.total ? '存在未通过行，不能导入' : ''}
              onClick={commit}
            >
              {busy ? '导入中…' : `确认导入 ${report.valid} 行`}
            </button>
            <button type="button" className="secondary" onClick={reset}>取消</button>
          </div>
        </div>
      )}
    </div>
  )
}
