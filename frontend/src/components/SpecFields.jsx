import { useState } from 'react'

/** 按后端类别字段定义渲染规格表单项 */
export default function SpecFields({ fields, values, onChange, disabled = false }) {
  if (!fields?.length) return null

  return (
    <div className="spec-fields">
      {fields.map((f) => {
        const id = `spec-${f.key}`
        const val = values[f.key] ?? ''
        const label = `${f.label}${f.unit ? `（${f.unit}）` : ''}${f.required ? ' *' : ''}`

        if (f.type === 'number') {
          return (
            <label key={f.key} htmlFor={id}>
              {label}
              <input
                id={id}
                type="number"
                min="0"
                step="any"
                value={val}
                disabled={disabled}
                required={!!f.required}
                placeholder={f.placeholder || ''}
                onChange={(e) => onChange(f.key, e.target.value)}
              />
            </label>
          )
        }

        if (f.type === 'enum') {
          const options = f.options || []
          const strict = !!f.strict
          const isCustom = !strict && val !== '' && !options.includes(String(val))
          return (
            <EnumField
              key={f.key}
              id={id}
              label={label}
              options={options}
              value={val}
              isCustom={isCustom}
              strict={strict}
              disabled={disabled}
              required={!!f.required}
              onChange={(v) => onChange(f.key, v)}
            />
          )
        }

        return (
          <label key={f.key} htmlFor={id}>
            {label}
            <input
              id={id}
              type="text"
              value={val}
              disabled={disabled}
              required={!!f.required}
              placeholder={f.placeholder || ''}
              onChange={(e) => onChange(f.key, e.target.value)}
            />
          </label>
        )
      })}
    </div>
  )
}

/** enum：strict 仅下拉；非 strict 允许「其他」自定义 */
function EnumField({ id, label, options, value, isCustom, strict, disabled, required, onChange }) {
  const [inCustom, setInCustom] = useState(isCustom)
  const [customText, setCustomText] = useState(isCustom ? String(value) : '')
  const showCustom = !strict && (inCustom || isCustom)
  const selectValue = showCustom
    ? '__custom__'
    : (options.includes(String(value)) ? value : '')

  function handleSelect(e) {
    const v = e.target.value
    if (v === '__custom__') {
      setInCustom(true)
      if (customText) onChange(customText)
      return
    }
    setInCustom(false)
    onChange(v)
  }

  function handleCustomChange(e) {
    const v = e.target.value
    setCustomText(v)
    onChange(v)
  }

  return (
    <div className="spec-enum-field">
      <label htmlFor={id}>{label}</label>
      <select
        id={id}
        value={selectValue}
        disabled={disabled}
        required={required && !showCustom}
        onChange={handleSelect}
      >
        <option value="">请选择</option>
        {options.map((opt) => (
          <option key={opt} value={opt}>{opt}</option>
        ))}
        {!strict && <option value="__custom__">其他（自定义）</option>}
      </select>
      {showCustom && (
        <input
          type="text"
          className="spec-custom-input"
          value={inCustom ? customText : String(value)}
          disabled={disabled}
          required={required}
          placeholder="输入自定义值"
          onChange={inCustom ? handleCustomChange : (e) => onChange(e.target.value)}
        />
      )}
    </div>
  )
}

export function formatSpec(spec) {
  if (!spec || typeof spec !== 'object') return '—'
  return Object.entries(spec)
    .map(([k, v]) => `${k}=${v}`)
    .join(' · ')
}
