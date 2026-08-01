const OPERATOR_KEY = 'demo_operator_id'

export function getOperatorId() {
  return Number(localStorage.getItem(OPERATOR_KEY) || '1')
}

export function setOperatorId(id) {
  localStorage.setItem(OPERATOR_KEY, String(id))
}

async function request(path, options = {}) {
  const headers = {
    'Content-Type': 'application/json',
    'X-Operator-Id': String(getOperatorId()),
    ...(options.headers || {}),
  }
  const res = await fetch(`/api${path}`, { ...options, headers })
  const text = await res.text()
  let data = null
  try {
    data = text ? JSON.parse(text) : null
  } catch {
    data = text
  }
  if (!res.ok) {
    const detail = data?.detail
    const msg = typeof detail === 'string'
      ? detail
      : Array.isArray(detail)
        ? detail.map((d) => d.msg || JSON.stringify(d)).join('; ')
        : res.statusText
    throw new Error(msg || '请求失败')
  }
  return data
}

export const api = {
  get: (path) => request(path),
  post: (path, body) => request(path, { method: 'POST', body: JSON.stringify(body ?? {}) }),
  put: (path, body) => request(path, { method: 'PUT', body: JSON.stringify(body ?? {}) }),
  patch: (path, body) => request(path, { method: 'PATCH', body: JSON.stringify(body ?? {}) }),
  delete: (path) => request(path, { method: 'DELETE' }),
}
